"""The ApoDesign Ascii renderer (torch only).

Pipeline (per frame, batch-vectorised, chunked to bound memory):
  cut the picture into character cells -> tone adjustments -> pick one glyph
  per cell (ramp / shape / braille) -> colour the glyph and its page ->
  stamp the glyphs from a font atlas.

Glyph choice
  ramp     the cell's brightness is matched to how much ink each glyph really
           has in the chosen font (measured, not guessed), optionally dithered
           and with | / - \\ drawn along strong edges.
  shape    each cell gets the glyph whose picture best matches the picture
           under it (least squares), so edges follow the drawing.
  braille  2x4 dots per cell, thresholded / dithered on the dot grid.
Ordered methods are anchored to the cell grid, so video stays steady.
"""
import math

import torch
import torch.nn.functional as F

from . import dither as D
from .ascii_specs import CHARSETS, EDGE_CHARS
from .bitmap_engine import preprocess, resolve_palette
from .colorspace import luma_cf, srgb_to_oklab
from .common import (fill_transparent, mask_to_grid_chunk, opacity_chunk, to_chw,
                     weighted_pool)
from .fonts import braille_atlas, get_atlas, resolve_font
from .mixing import blend, mix_weight
from .palettes import palette_to_string, sort_by_luma

SRC_BUDGET = 24e6     # source pixels converted per pass
OUT_BUDGET = 16e6     # output pixels composed per pass
SHAPE_BUDGET = 12e6   # cells x glyphs scored per pass
MAX_CHUNK = 8
BRAILLE_WEIGHTS = [[1, 8], [2, 16], [4, 32], [64, 128]]


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def cell_geometry(H, W, columns, aspect):
    """-> (cell_w, cell_h, cols, rows) in source pixels. The last column / row
    may hang over the picture edge; the output is cropped back to size."""
    cw = max(2, int(round(W / float(max(1, columns)))))
    ch = max(2, int(round(cw * float(aspect))))
    return cw, ch, -(-W // cw), -(-H // ch)


def pad_to(x, Hp, Wp):
    H, W = x.shape[-2:]
    if Hp != H or Wp != W:
        x = F.pad(x, (0, Wp - W, 0, Hp - H), mode="replicate")
    return x


def resolve_charset(v):
    if v["charset"] == "custom":
        chars = v["custom_charset"] or CHARSETS["standard"]
    else:
        chars = CHARSETS[v["charset"]]
    chars = "".join(dict.fromkeys(c for c in chars if c not in "\r\n\t"))
    if len(chars) < 2:
        chars = " ." if chars in ("", " ") else " " + chars
    return chars


def sobel_xy(lum):
    """(B,1,h,w) -> (gx, gy): brightness increase towards +x / +y (down)."""
    kx = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]],
                      dtype=lum.dtype, device=lum.device).view(1, 1, 3, 3)
    ky = kx.transpose(2, 3).contiguous()
    p = F.pad(lum, (1, 1, 1, 1), mode="replicate")
    return F.conv2d(p, kx), F.conv2d(p, ky)


# --------------------------------------------------------------------------
# the three ways of choosing glyphs. Each returns (n, rows, cols) atlas ids.
# --------------------------------------------------------------------------
def ramp_indices(tone, dn, method, T, strength):
    """tone (n,1,r,c) in 0..1 -> index into the density-sorted ramp (n,r,c).
    dn: ascending normalised glyph densities (G,). Glyphs are NOT evenly
    spaced in ink, so the dither works in density space."""
    G = dn.numel()
    tone = tone.clamp(0.0, 1.0).contiguous()
    if method in D.DIFFUSION:
        def quant(old):                                   # (B,1,n)
            idx = (old.unsqueeze(-1) - dn).abs().argmin(dim=-1)
            return dn[idx], idx
        _, idx = D.error_diffusion(tone, quant, method, strength)
        return idx[:, 0]
    Tt = D._soften(T[:1], strength)[None]
    k = (torch.bucketize(tone, dn, right=True) - 1).clamp(0, G - 2)
    lo, hi = dn[k], dn[k + 1]
    frac = (tone - lo) / (hi - lo).clamp_min(1e-6)
    return (k + (frac > Tt).long())[:, 0]


def edge_glyphs(lum, strength, aspect, edge_ids):
    """Where the picture has a strong edge, the | / - \\ glyph that follows it.
    lum (n,1,r,c). Returns (mask (n,r,c) bool, glyph ids (n,r,c))."""
    gx, gy = sobel_xy(lum)
    mag = torch.sqrt(gx * gx + gy * gy) / 4.0
    th = 0.02 + 0.5 * (1.0 - float(strength))
    # cells are `aspect` times taller than wide: undo that before measuring
    # the angle, so a 45 degree edge in the picture really picks / or \\
    ang = torch.remainder(torch.atan2(gy, gx * aspect), math.pi)
    b = torch.round(ang / (math.pi / 4.0)).long() % 4
    return (mag > th)[:, 0], edge_ids[b[:, 0]]


def shape_indices(ftone, feat, gsq, scale, rows, cols, mh, mw):
    """ftone (n,1,rows*mh,cols*mw): the picture's ink amount at match
    resolution. Least squares against every glyph: argmin |p - g|^2."""
    n = ftone.shape[0]
    p = (ftone * scale).reshape(n, rows, mh, cols, mw)
    p = p.permute(0, 1, 3, 2, 4).reshape(n * rows * cols, mh * mw)
    score = gsq.unsqueeze(0) - 2.0 * (p @ feat.t())
    return score.argmin(dim=1).reshape(n, rows, cols)


def braille_indices(tone, method, T, strength, rows, cols):
    """tone (n,1,rows*4,cols*2) -> braille pattern number 0..255 per cell."""
    tone = tone.clamp(0.0, 1.0).contiguous()
    if method in D.DIFFUSION:
        _, bits = D.error_diffusion(tone, D.level_quantizer(2), method, strength)
    else:
        bits = D.ordered_levels(tone, 2, T[:1], strength)
    n = tone.shape[0]
    b = bits[:, 0].reshape(n, rows, 4, cols, 2).permute(0, 1, 3, 2, 4)
    w = torch.tensor(BRAILLE_WEIGHTS, dtype=torch.long, device=tone.device)
    return (b * w).sum(dim=(-2, -1))


def gid_to_text(g, kept, braille, opaque=None):
    """glyph ids -> text. opaque: optional rows x cols of 0/1; transparent
    cells become blanks."""
    if opaque is None:
        lines = ["".join(kept[j] for j in row) for row in g]
    else:
        blank = "\u2800" if braille else " "
        lines = ["".join(kept[j] if o > 0.5 else blank for j, o in zip(row, orow))
                 for row, orow in zip(g, opaque)]
    if not braille:
        lines = [ln.rstrip(" ") for ln in lines]
    return "\n".join(lines)


def apply_text_order(gid, ink_g, seq_ids, blank_id, opaque, per_row):
    """Replace the glyph of every inked cell by the next letter of the text.
    gid (n,rows,cols) atlas ids; ink_g (G,) bool: which glyphs count as ink;
    seq_ids (L,) atlas id of each text position. Reading order = left to
    right, top to bottom; transparent cells never take a letter."""
    ink = ink_g[gid]
    if opaque is not None:
        ink = ink & (opaque[:, 0] > 0.5)
    n, rows, cols = ink.shape
    if per_row:
        k = torch.cumsum(ink.long(), dim=2) - 1
    else:
        k = (torch.cumsum(ink.reshape(n, -1).long(), dim=1) - 1).reshape(n, rows, cols)
    letters = seq_ids[k.clamp_min(0) % seq_ids.shape[0]]
    return torch.where(ink, letters, torch.full_like(gid, blank_id))


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
def render(image, mask, v, device, alpha=None, rgba=False):
    """image: ComfyUI IMAGE (B,H,W,C). Returns a dict of CPU tensors/strings.

    mask   colour-region MASK (used by mix_mode = mask), or None.
    alpha  transparency MASK (1 = transparent), or None. A character cell is
           transparent when most of its area is: no glyph, no page colour,
           and a blank in the text output.
    rgba   True: "image" gets a 4th (alpha) channel. False: "image" is RGB
           and "alpha" holds the transparency (1 = transparent)."""
    B, H, W = image.shape[0], image.shape[1], image.shape[2]
    s = int(v["output_scale"])
    cw0, ch0, cols, rows = cell_geometry(H, W, v["columns"], v["cell_aspect"])
    cw, ch = cw0 * s, ch0 * s                       # cell size in the output
    Hp, Wp = rows * ch0, cols * cw0                 # padded source size
    Hout, Wout = H * s, W * s
    match = v["glyph_match"]
    notes = []

    # ---- glyph atlas ---------------------------------------------------------
    font_path, note = resolve_font(v["font"], v["font_bold"], v["font_file"])
    if note:
        notes.append(note)
    smooth = v["glyph_style"] == "smooth"
    ramp_t = edge_ids = None
    order_on = False
    if match == "braille" and v["text_order"] != "off":
        notes.append("text_order does not work with braille; ignored")
    dens = None
    scale = 1.0
    if match == "braille":
        kept = [chr(0x2800 + i) for i in range(256)]
        atlas_np = braille_atlas(cw, ch)
    else:
        chars = resolve_charset(v)
        order_on = v["text_order"] != "off"
        phrase = "".join(" " if c in "\r\n\t" else c for c in str(v["order_text"]))
        if order_on and not phrase.strip():
            order_on = False
            notes.append("order_text is empty; text_order ignored")
        if order_on:
            phrase = phrase if phrase.endswith(" ") else phrase + " "
        want_edges = match == "ramp" and float(v["edge_strength"]) > 0.0 and not order_on
        extra = (EDGE_CHARS if want_edges else "") + (" " + phrase if order_on else "")
        kept, atlas_np = get_atlas(chars + extra, font_path, cw, ch, smooth)
        in_ramp = set(chars)
        ids = [i for i, c in enumerate(kept) if c in in_ramp]
        if len(ids) < 2:                            # the font lacked nearly all of them
            notes.append("charset not available in this font; using classic")
            kept, atlas_np = get_atlas(CHARSETS["classic"] + extra, font_path, cw, ch, smooth)
            in_ramp = set(CHARSETS["classic"])
            ids = [i for i, c in enumerate(kept) if c in in_ramp]
        dens = atlas_np.mean(axis=(1, 2))
        ids.sort(key=lambda i: (float(dens[i]), i))
        lo, hi = float(dens[ids[0]]), float(dens[ids[-1]])
        dn = torch.tensor([(float(dens[i]) - lo) / max(hi - lo, 1e-6) for i in ids],
                          dtype=torch.float32, device=device)
        ramp_t = torch.tensor(ids, dtype=torch.long, device=device)
        scale = max(hi, 1e-6)
        if order_on:
            blank_id = kept.index(" ") if " " in kept else 0
            ink_g = torch.zeros(len(kept), dtype=torch.bool, device=device)
            ink_g[ramp_t] = dn >= float(v["order_threshold"]) + 1e-6
            seq_ids = torch.tensor([kept.index(c) if c in kept else blank_id for c in phrase],
                                   dtype=torch.long, device=device)
        if want_edges and all(c in kept for c in EDGE_CHARS):
            edge_ids = torch.tensor([kept.index(c) for c in EDGE_CHARS],
                                    dtype=torch.long, device=device)
    atlas = torch.from_numpy(atlas_np).to(device)             # (G, ch, cw)
    G = atlas.shape[0]

    # ---- shape matching features ----------------------------------------------
    mh = mw = 0
    feat = gsq = None
    if match == "shape":
        mh = max(1, min(ch0, 16))
        mw = max(1, min(cw0, int(round(mh / float(v["cell_aspect"])))))
        feat = F.adaptive_avg_pool2d(atlas.unsqueeze(1), (mh, mw)).reshape(G, mh * mw)
        gsq = (feat * feat).sum(dim=1)
        feat = feat[ramp_t]                                  # only charset glyphs compete
        gsq = gsq[ramp_t]

    # ---- cell colours for the whole batch (tiny) -------------------------------
    nA = max(1, min(MAX_CHUNK, int(SRC_BUDGET // max(1, Hp * Wp))))
    def to_cells(t):
        return F.avg_pool2d(pad_to(t, Hp, Wp), (ch0, cw0))

    def stage_a(i):
        x = to_chw(image[i:i + nA]).to(device)
        if alpha is None:
            return preprocess(to_cells(x), v), None
        a = opacity_chunk(alpha, i, x.shape[0], H, W, device)
        colour, cover = weighted_pool(to_cells, x, a)
        opq = (cover >= 0.5).float()
        return preprocess(fill_transparent(colour, opq), v), opq

    parts = [stage_a(i) for i in range(0, B, nA)]
    low = torch.cat([p[0] for p in parts])                     # (B,3,rows,cols)
    opq_all = torch.cat([p[1] for p in parts]) if alpha is not None else None
    del parts

    pal = sort_by_luma(resolve_palette(v, low, opq_all))
    if len(pal) < 2:
        pal = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
    light_on_dark = v["polarity"] == "light_on_dark"
    fg_mono, bg_mono = (pal[-1], pal[0]) if light_on_dark else (pal[0], pal[-1])
    fg_m = torch.tensor(fg_mono, dtype=torch.float32, device=device).view(1, 3, 1, 1)
    bg_m = torch.tensor(bg_mono, dtype=torch.float32, device=device).view(1, 3, 1, 1)
    pal_t = torch.tensor(pal, dtype=torch.float32, device=device)
    pal_lab = srgb_to_oklab(pal_t)

    method = "threshold" if v["method"] == "none" else v["method"]
    strength = float(v["dither_strength"])
    bayer_size = int(v["bayer_size"])
    T_cell = D.make_threshold(method, rows, cols, device, bayer_size=bayer_size)
    T_dots = None
    if match == "braille":
        T_dots = D.make_threshold(method, rows * 4, cols * 2, device, bayer_size=bayer_size)

    mode = v["color_mode"]
    amount = float(v["color_mix"])
    want_colour = mode != "tonal" and amount > 0.0
    boost = float(v["color_boost"])
    tint = float(v["bg_tint"])
    aspect_eff = ch0 / float(cw0)

    # ---- outputs, written chunk by chunk ---------------------------------------
    want_mask = bool(v["glyph_mask_output"])
    use_alpha = alpha is not None
    out_img = torch.empty(B, Hout, Wout, 4 if (use_alpha and rgba) else 3)
    if use_alpha:               # filled in rgba mode too, so Join Image with Alpha works
        out_alpha = torch.empty(B, Hout, Wout)
    else:
        out_alpha = torch.zeros(1, Hout, Wout).expand(B, Hout, Wout)
    if want_mask:
        out_mask = torch.empty(B, Hout, Wout)
    else:   # all-black mask that costs no memory (one row, repeated)
        out_mask = torch.zeros(1, Hout, Wout).expand(B, Hout, Wout)
    tf = int(v["text_frame"])
    tf = B - 1 if tf >= B else tf
    texts = {}

    n_max = max(1, min(MAX_CHUNK, int(OUT_BUDGET // max(1, rows * ch * cols * cw))))
    if match == "shape":
        n_max = max(1, min(n_max, int(SHAPE_BUDGET // max(1, rows * cols * G))))

    for i in range(0, B, n_max):
        lb = low[i:i + n_max]
        n = lb.shape[0]
        ob = opq_all[i:i + n] if use_alpha else None           # (n,1,rows,cols)
        lum = luma_cf(lb)

        # -- choose a glyph for every cell
        if match == "ramp":
            tone = lum if light_on_dark else 1.0 - lum
            gid = ramp_t[ramp_indices(tone, dn, method, T_cell, strength)]
            if edge_ids is not None:
                emask, eg = edge_glyphs(lum, v["edge_strength"], aspect_eff, edge_ids)
                gid = torch.where(emask, eg, gid)
        else:
            x = pad_to(to_chw(image[i:i + n]).to(device), Hp, Wp)
            src = luma_cf(x)
            del x
            if match == "shape":
                fine = preprocess(F.adaptive_avg_pool2d(src, (rows * mh, cols * mw)), v)
                ftone = fine if light_on_dark else 1.0 - fine
                gid = ramp_t[shape_indices(ftone, feat, gsq, scale, rows, cols, mh, mw)]
            else:
                fine = preprocess(F.adaptive_avg_pool2d(src, (rows * 4, cols * 2)), v)
                ftone = fine if light_on_dark else 1.0 - fine
                gid = braille_indices(ftone, method, T_dots, strength, rows, cols)
            del src
        if order_on:
            gid = apply_text_order(gid, ink_g, seq_ids, blank_id, ob,
                                   v["text_order"] == "in_order_per_row")

        # -- colours: glyph colour (fg) and page colour (bg) per cell
        fg = fg_m.expand(n, 3, rows, cols)
        bg = bg_m.expand(n, 3, rows, cols)
        if want_colour:
            mb = None
            if mask is not None:
                mb = mask_to_grid_chunk(mask, i, n, rows, cols, device)
            if mode == "channels":
                col = D.dither_channels(lb, int(v["color_levels"]), method, T_cell, strength)
            else:
                col = D.dither_palette(lb, pal_t, pal_lab, method, T_cell, strength)
            col_fg = col
            if mode == "channels" and light_on_dark and boost > 0.0:
                peak = col.amax(dim=1, keepdim=True).clamp_min(1e-4)
                col_fg = col * (1.0 - boost) + (col / peak) * boost
            col_bg = bg_m + (col - bg_m) * tint if v["background"] == "tint" else bg
            wgt = mix_weight(v["mix_mode"], amount, lb, mb)
            fg = blend(fg, col_fg, wgt)
            bg = blend(bg, col_bg, wgt)

        # -- stamp the glyphs
        cov = atlas[gid]                                       # (n,rows,cols,ch,cw)
        fgp = fg.permute(0, 2, 3, 1)[:, :, :, None, None, :]
        bgp = bg.permute(0, 2, 3, 1)[:, :, :, None, None, :]
        img = bgp + (fgp - bgp) * cov.unsqueeze(-1)            # (n,rows,cols,ch,cw,3)
        img = img.permute(0, 1, 3, 2, 4, 5).reshape(n, rows * ch, cols * cw, 3)
        opx = None
        if ob is not None:                                     # per-pixel opacity
            opx = ob.repeat_interleave(ch, 2).repeat_interleave(cw, 3)[:, 0, :Hout, :Wout]
            img = img[:, :Hout, :Wout] * opx.unsqueeze(-1)     # transparent = black
        out_img[i:i + n, :, :, :3] = img[:, :Hout, :Wout].clamp(0.0, 1.0).cpu()
        del img
        if opx is not None:
            if rgba:
                out_img[i:i + n, :, :, 3] = opx.cpu()
            out_alpha[i:i + n] = (1.0 - opx).cpu()
        if want_mask:
            cm = cov.permute(0, 1, 3, 2, 4).reshape(n, rows * ch, cols * cw)[:, :Hout, :Wout]
            if opx is not None:
                cm = cm * opx
            out_mask[i:i + n] = cm.clamp(0.0, 1.0).cpu()

        # -- the text of the frame(s) asked for
        for k in range(n):
            if tf == -1 or i + k == tf:
                texts[i + k] = gid_to_text(gid[k].cpu().tolist(), kept, match == "braille",
                                           ob[k, 0].cpu().tolist() if ob is not None else None)

    text = "\n\f\n".join(texts[j] for j in sorted(texts)) if tf == -1 else texts.get(tf, "")
    return {
        "image": out_img,
        "mask": out_mask,
        "alpha": out_alpha,
        "text": text,
        "palette": palette_to_string(pal),
        "notes": notes,
    }
