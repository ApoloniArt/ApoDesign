"""The ApoDesign Pixel Art renderer (torch only).

Pipeline (per frame, batch-vectorised, chunked to bound memory):
  fine grid (a few samples per pixel) -> tone / saturation -> optional
  Kuwahara flattening -> pixel colour (dominant / average / nearest) ->
  palette -> stray-pixel cleanup -> outline -> crisp nearest upscale.

"dominant" is what makes it read as hand-made pixel art: every output pixel
takes the most common palette colour inside its block instead of a blurry
average, so edges stay crisp. The palette is shared by every frame of a
video, and nothing here is random, so video stays steady.
"""
import torch
import torch.nn.functional as F

from . import dither as D
from .bitmap_engine import preprocess, resolve_palette
from .colorspace import luma_cf, nearest_palette_idx, srgb_to_oklab
from .common import (downsample, fill_transparent, grid_size, nearest_up,
                     opacity_chunk, to_bhwc, to_chw, weighted_pool)
from .palettes import hex_to_rgb, palette_to_string, parse_palette, sort_by_luma

MAX_CHUNK = 8
FINE_BUDGET = 8e6        # fine-grid pixels per frame
PASS_BUDGET = 12e6       # fine-grid pixels per pass
PALETTE_FRAMES = 16      # frames sampled for an adaptive palette


# --------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------
def adjust(x, v):
    """Tone shaping plus saturation."""
    x = preprocess(x, v)
    sat = float(v["saturation"])
    if abs(sat - 1.0) > 1e-6:
        lum = luma_cf(x)
        x = (lum + (x - lum) * sat).clamp(0.0, 1.0)
    return x


def kuwahara(x, r):
    """Edge-preserving flattening: every pixel takes the mean of whichever of
    its four quadrants (radius r) is the least varied. x: (B,3,H,W)."""
    if r <= 0:
        return x
    H, W = x.shape[-2:]
    p = F.pad(x, (r, r, r, r), mode="replicate")
    m = F.avg_pool2d(p, r + 1, stride=1)                       # (B,3,H+r,W+r)
    m2 = F.avg_pool2d(p * p, r + 1, stride=1)
    var = (m2 - m * m).clamp_min(0.0).sum(dim=1, keepdim=True)
    offs = [(0, 0), (0, r), (r, 0), (r, r)]                    # TL TR BL BR
    means = torch.stack([m[:, :, dy:dy + H, dx:dx + W] for dy, dx in offs])
    vars_ = torch.stack([var[:, :, dy:dy + H, dx:dx + W] for dy, dx in offs])
    sel = vars_.argmin(dim=0)                                  # (B,1,H,W)
    idx = sel.unsqueeze(0).expand(1, -1, 3, -1, -1)
    return means.gather(0, idx)[0]


def fine_grid(x, h, w, S, ps, integer):
    """Area-average (B,3,H,W) down to (h*S, w*S): S x S samples per pixel."""
    if integer:
        H, W = x.shape[-2:]
        ph, pw = h * ps - H, w * ps - W
        if ph or pw:
            x = F.pad(x, (0, pw, 0, ph), mode="replicate")
    return F.adaptive_avg_pool2d(x, (h * S, w * S))


def dominant_indices(fine, avg, S, h, w, pal_lab, match, N, valid=None):
    """Most common palette index inside each S x S block -> (n,h,w). Ties go
    to the palette colour closest to the block's average. valid (n,1,hS,wS):
    only these samples vote (transparent ones do not)."""
    n = fine.shape[0]
    if match == "tone":
        idx = (luma_cf(fine)[:, 0].clamp(0.0, 1.0) * (N - 1)).round().long()
        avg_idx = (luma_cf(avg)[:, 0].clamp(0.0, 1.0) * (N - 1)).round().long()
    else:
        idx = nearest_palette_idx(fine.permute(0, 2, 3, 1), pal_lab)
        avg_idx = nearest_palette_idx(avg.permute(0, 2, 3, 1), pal_lab)
    idx = idx.reshape(n, h, S, w, S)
    vv = valid[:, 0].reshape(n, h, S, w, S) if valid is not None else None
    counts = torch.stack([((idx == k) if vv is None else ((idx == k) & vv)).sum(dim=(2, 4))
                          for k in range(N)], dim=1).float()
    counts = counts + 0.5 * F.one_hot(avg_idx, N).permute(0, 3, 1, 2).float()
    return counts.argmax(dim=1)


def cleanup_indices(idx, N, level, opq=None):
    """Replace stray pixels (few same-colour neighbours, a clear majority of
    another colour around them). idx: (n,h,w) palette indices. opq (n,1,h,w):
    transparent cells take no part."""
    oh = F.one_hot(idx, N).permute(0, 3, 1, 2).float()
    if opq is not None:
        oh = oh * opq
    neigh = (F.avg_pool2d(oh, 3, stride=1, padding=1) * 9.0 - oh).round()
    same = (neigh * oh).sum(dim=1)
    best_cnt, best = neigh.max(dim=1)
    repl = (same <= level - 1) & (best_cnt > same + 1)
    return torch.where(repl, best, idx)


def _neighbours(t):
    """The 4 neighbours (up, down, left, right) of every cell, edges repeated."""
    p = F.pad(t, (1, 1, 1, 1), mode="replicate")
    return torch.stack([p[..., :-2, 1:-1], p[..., 2:, 1:-1],
                        p[..., 1:-1, :-2], p[..., 1:-1, 2:]])


def outline_mask(rgb, thr, opq=None):
    """True where a pixel has a 4-neighbour brighter by more than thr, i.e.
    the dark side of an edge. rgb: (n,3,h,w) -> (n,1,h,w) bool. With opq
    (opacity, 1 = opaque) the silhouette is outlined too: opaque pixels next
    to a transparent one."""
    L = srgb_to_oklab(rgb.permute(0, 2, 3, 1))[..., 0].unsqueeze(1)
    if opq is None:
        return (_neighbours(L).max(dim=0).values - L) > thr
    Lm = torch.where(opq > 0.5, L, torch.full_like(L, -1e3))    # transparent never "brighter"
    step = (_neighbours(Lm).max(dim=0).values - L) > thr
    # outside the picture counts as opaque, so the picture edge is not outlined
    hole = (_neighbours(1.0 - opq).max(dim=0).values > 0.5)
    return (step | hole) & (opq > 0.5)


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
def render(image, v, device, alpha=None, rgba=False):
    """image: ComfyUI IMAGE (B,H,W,C). Returns a dict of CPU tensors/strings.

    alpha  transparency MASK (1 = transparent), or None. Transparent areas
           stay transparent: only opaque pixels vote for a block's colour or
           shape the palette, and a block is transparent when most of it is.
           Outlines also trace the silhouette.
    rgba   True: "image" gets a 4th (alpha) channel. False: "image" is RGB
           and "alpha" holds the transparency (1 = transparent)."""
    B, H, W = image.shape[0], image.shape[1], image.shape[2]
    sc = int(v["output_scale"])
    ps = max(1, int(v["pixel_size"]))
    h, w, integer = grid_size(H, W, ps, v["target_width"])
    Hout, Wout = H * sc, W * sc
    if integer:
        cy = cx = float(ps * sc)
    else:
        cy, cx = Hout / h, Wout / w

    mode = v["pixel_mode"]
    kr = int(round(float(v["simplify"]) * 3))
    needs_fine = mode in ("dominant", "nearest") or kr > 0
    S = 1
    if needs_fine:
        S = max(1, min(4, int(W / float(w))))
        while S > 1 and h * w * S * S > FINE_BUDGET:
            S -= 1
    match = v["match"]
    method = "threshold" if v["method"] == "none" else v["method"]
    strength = float(v["dither_strength"])
    use_alpha = alpha is not None

    def prepare(x, start):
        """-> (low, fine or None, avg, opq or None, fine_valid or None).
        All tone-adjusted. low / avg / opq are (n,*,h,w)."""
        n = x.shape[0]
        a = opacity_chunk(alpha, start, n, H, W, device) if use_alpha else None
        if not needs_fine:
            if a is None:
                low = adjust(downsample(x, h, w, ps, integer), v)
                return low, None, low, None, None
            colour, cover = weighted_pool(lambda t: downsample(t, h, w, ps, integer), x, a)
            opq = (cover >= 0.5).float()
            low = adjust(fill_transparent(colour, opq), v)
            return low, None, low, opq, None
        fvalid = opq = None
        if a is None:
            raw = fine_grid(x, h, w, S, ps, integer)
        else:
            raw, fcover = weighted_pool(lambda t: fine_grid(t, h, w, S, ps, integer), x, a)
            fvalid = fcover >= 0.5
            raw = fill_transparent(raw, fvalid.float())
            opq = ((F.avg_pool2d(fcover, S) if S > 1 else fcover) >= 0.5).float()
        fine = kuwahara(adjust(raw, v), kr)
        if S > 1 and fvalid is not None:
            fv = fvalid.float()
            avg = F.avg_pool2d(fine * fv, S) / F.avg_pool2d(fv, S).clamp_min(1e-4)
            avg = fill_transparent(avg, opq)
        else:
            avg = F.avg_pool2d(fine, S) if S > 1 else fine
        low = fine[..., S // 2::S, S // 2::S] if (mode == "nearest" and S > 1) else avg
        return low, (fine if S > 1 else None), avg, opq, fvalid

    # ---- palette ---------------------------------------------------------------
    preset = v["palette_preset"]
    custom = len(parse_palette(v["custom_palette"])) >= 2
    pal = pal_t = pal_lab = None
    if preset != "none" or custom:
        low_s = valid_s = None
        if preset == "adaptive_kmeans" and not custom:
            pick = sorted({int(round(j * (B - 1) / max(1, min(B, PALETTE_FRAMES) - 1)))
                           for j in range(min(B, PALETTE_FRAMES))})
            got = [prepare(to_chw(image[j:j + 1]).to(device), j) for j in pick]
            low_s = torch.cat([g[0] for g in got])
            if use_alpha:
                valid_s = torch.cat([g[3] for g in got])
        pal = sort_by_luma(resolve_palette(v, low_s, valid_s))
        pal_t = torch.tensor(pal, dtype=torch.float32, device=device)
        pal_lab = srgb_to_oklab(pal_t)
    N = len(pal) if pal else 0

    T = None
    if pal is not None:
        T = D.make_threshold(method, h, w, device, bayer_size=int(v["bayer_size"]))

    outline = v["outline"]
    oc = None
    if outline == "colour":
        oc = hex_to_rgb(v["outline_color"]) or (0.0, 0.0, 0.0)
        oc_t = torch.tensor(oc, dtype=torch.float32, device=device).view(1, 3, 1, 1)
    cleanup = int(v["cleanup"])

    out_img = torch.empty(B, Hout, Wout, 4 if (use_alpha and rgba) else 3)
    out_low = torch.empty(B, h, w, 3)
    if use_alpha:               # filled in rgba mode too, so Join Image with Alpha works
        out_alpha = torch.empty(B, Hout, Wout)
    else:
        out_alpha = torch.zeros(1, Hout, Wout).expand(B, Hout, Wout)
    n_max = max(1, min(MAX_CHUNK, int(PASS_BUDGET // max(1, h * w * S * S))))

    for i in range(0, B, n_max):
        x = to_chw(image[i:i + n_max]).to(device)
        low, fine, avg, opq, fvalid = prepare(x, i)
        del x
        n = low.shape[0]

        if pal is None:
            rgb = low
        else:
            if mode == "dominant" and fine is not None:
                idx = dominant_indices(fine, avg, S, h, w, pal_lab, match, N, fvalid)
            else:
                if match == "tone":
                    rgb = D.dither_tonal(luma_cf(low), pal_t, method, T, strength)
                else:
                    rgb = D.dither_palette(low, pal_t, pal_lab, method, T, strength)
                idx = nearest_palette_idx(rgb.permute(0, 2, 3, 1), pal_lab)
            if cleanup > 0:
                idx = cleanup_indices(idx, N, cleanup, opq)
            rgb = pal_t[idx].permute(0, 3, 1, 2)

        if outline != "none":
            mk = outline_mask(rgb, float(v["outline_threshold"]), opq)
            if oc is not None:
                orgb = oc_t
            else:
                dark = rgb * 0.5
                if pal is not None:
                    orgb = pal_t[nearest_palette_idx(dark.permute(0, 2, 3, 1), pal_lab)]
                    orgb = orgb.permute(0, 3, 1, 2)
                else:
                    orgb = dark
            rgb = torch.where(mk, orgb, rgb)

        rgb = rgb.clamp(0.0, 1.0)
        if opq is not None:
            rgb = rgb * opq                                   # transparent = black
        out_low[i:i + n] = to_bhwc(rgb)
        out_img[i:i + n, :, :, :3] = to_bhwc(nearest_up(rgb, Hout, Wout, cy, cx))
        if opq is not None:
            up_o = nearest_up(opq, Hout, Wout, cy, cx)[:, 0].cpu()
            if rgba:
                out_img[i:i + n, :, :, 3] = up_o
            out_alpha[i:i + n] = 1.0 - up_o

    shown = list(pal) if pal else []
    if oc is not None and oc not in shown:
        shown.append(oc)
    return {"image": out_img, "lowres": out_low, "alpha": out_alpha,
            "palette": palette_to_string(shown) if shown else ""}
