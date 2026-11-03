"""The ApoDesign Bitmap renderer (torch only).

Pipeline (all per frame, batch-vectorised, chunked to bound memory):
  downsample to the pixel grid -> tone adjustments -> palette ->
  mono layer (+ colour layer, mixed by region) -> crisp nearest upscale.
Output is deterministic for ordered methods, so video stays steady.
"""
import torch

from . import dither as D
from .colorspace import (gaussian_blur, kmeans_oklab, luma_cf, oklab_to_srgb,
                         srgb_to_oklab)
from .common import (downsample, fill_transparent, grid_size, mask_to_grid_chunk,
                     nearest_up, opacity_chunk, to_bhwc, to_chw, weighted_pool)
from .mixing import blend, mix_weight
from .palettes import (PRESETS, hex_to_rgb, palette_to_string, parse_palette,
                       preset_palette, sort_by_luma)

CHUNK = 8  # frames per pass


def preprocess(x, v):
    """Tone shaping on the low-res grid, so the dither sees what you tuned."""
    if v["invert"]:
        x = 1.0 - x
    if v["local_contrast"] > 0:
        sigma = max(2.0, min(x.shape[-2:]) / 12.0)
        x = x + v["local_contrast"] * (x - gaussian_blur(x, sigma))
    if v["sharpen"] > 0:
        x = x + v["sharpen"] * (x - gaussian_blur(x, 1.0))
    x = (x - 0.5) * v["contrast"] + 0.5 + v["brightness"]
    x = x.clamp(0.0, 1.0)
    if abs(v["gamma"] - 1.0) > 1e-6:
        x = x.pow(1.0 / v["gamma"])
    return x


def adaptive_palette(low, k, max_samples=20000, valid=None):
    """k-means palette in OKLab over the WHOLE batch, so every frame of a
    video shares one palette. valid (B,1,h,w): only these pixels count
    (transparent ones are left out)."""
    px = low.permute(0, 2, 3, 1).reshape(-1, 3)
    if valid is not None:
        keep = valid.reshape(-1) > 0.5
        if bool(keep.any()):
            px = px[keep]
    if px.shape[0] > max_samples:
        sel = torch.linspace(0, px.shape[0] - 1, max_samples, device=px.device).long()
        px = px[sel]
    cents = kmeans_oklab(srgb_to_oklab(px), k)
    rgb = oklab_to_srgb(cents).clamp(0.0, 1.0).cpu().tolist()
    return [tuple(c) for c in rgb]


def resolve_palette(v, low, valid=None):
    """-> (palette as list of rgb tuples, dark->light for tonal use)."""
    custom = parse_palette(v["custom_palette"])
    if len(custom) >= 2:
        return sort_by_luma(custom)
    preset = v["palette_preset"]
    if preset == "ink_paper":
        ink = hex_to_rgb(v["ink_color"]) or (0.0, 0.0, 0.0)
        paper = hex_to_rgb(v["paper_color"]) or (1.0, 1.0, 1.0)
        return [ink, paper]          # order kept: a light ink gives a negative look
    if preset == "adaptive_kmeans":
        return sort_by_luma(adaptive_palette(low, v["palette_size"], valid=valid))
    if preset in PRESETS:
        return sort_by_luma(preset_palette(preset))
    return sort_by_luma(preset_palette("black_white"))


def render(image, mask, v, device, want_mask=True, alpha=None, rgba=False):
    """image: ComfyUI IMAGE (B,H,W,C). Returns a dict of CPU tensors/strings.

    mask   colour-region MASK (used by mix_mode = mask), or None.
    alpha  transparency MASK (1 = transparent), or None. Transparent areas
           stay transparent: they are left out of palettes, never bleed into
           neighbouring pixels, and come out black. The transparency follows
           the pixel grid, so it is as chunky as the pixels.
    rgba   True: "image" gets a 4th (alpha) channel. False: "image" is RGB
           and "alpha" holds the transparency (1 = transparent).

    Memory: the input is converted one chunk at a time (never as a whole
    copy), the outputs are written straight into pre-allocated tensors (no
    list-then-cat doubling), and the full-size ink mask is only built when
    want_mask is True. The picture itself is computed exactly as before."""
    B, H, W = image.shape[0], image.shape[1], image.shape[2]
    sc = int(v["output_scale"])
    h, w, integer = grid_size(H, W, v["pixel_size"], v["target_width"])
    Hout, Wout = H * sc, W * sc
    if integer:
        cy = cx = float(int(v["pixel_size"]) * sc)
    else:
        cy, cx = Hout / h, Wout / w

    def to_grid(t):
        return downsample(t, h, w, v["pixel_size"], integer)

    def stage_a(i):
        """tone-adjusted low-res grid (and its opacity) for one chunk"""
        x = to_chw(image[i:i + CHUNK]).to(device)
        if alpha is None:
            return preprocess(to_grid(x), v), None
        a = opacity_chunk(alpha, i, x.shape[0], H, W, device)
        colour, cover = weighted_pool(to_grid, x, a)
        opq = (cover >= 0.5).float()
        return preprocess(fill_transparent(colour, opq), v), opq

    # Stage A: low-res grid for the whole batch, tone-adjusted. It is small
    # unless pixel_size is 1, in which case it stays on the CPU.
    low_dev = device if B * 3 * h * w * 4 <= (256 << 20) else torch.device("cpu")
    parts = [stage_a(i) for i in range(0, B, CHUNK)]
    low = torch.cat([p[0].to(low_dev) for p in parts])
    opq_all = torch.cat([p[1].to(low_dev) for p in parts]) if alpha is not None else None
    del parts

    pal = resolve_palette(v, low, opq_all)
    pal_t = torch.tensor(pal, dtype=torch.float32, device=device)       # (N,3)
    pal_lab = srgb_to_oklab(pal_t)

    method = v["method"]
    mode = v["color_mode"]
    T = D.make_threshold(method, h, w, device,
                         bayer_size=int(v["bayer_size"]),
                         cell=float(v["halftone_cell"]),
                         angle=float(v["halftone_angle"]),
                         per_channel=(mode == "channels"))
    strength = float(v["dither_strength"])
    amount = float(v["color_mix"])
    want_colour = mode != "tonal" and amount > 0.0
    colour_only = want_colour and amount >= 1.0 and v["mix_mode"] == "global"

    out_img = torch.empty(B, Hout, Wout, 4 if (alpha is not None and rgba) else 3)
    out_low = torch.empty(B, h, w, 3)
    if want_mask:
        out_mask = torch.empty(B, Hout, Wout)
    else:   # all-black mask that costs no memory (one row, repeated)
        out_mask = torch.zeros(1, Hout, Wout).expand(B, Hout, Wout)
    if alpha is not None:       # filled in rgba mode too, so Join Image with Alpha works
        out_alpha = torch.empty(B, Hout, Wout)
    else:
        out_alpha = torch.zeros(1, Hout, Wout).expand(B, Hout, Wout)

    for i in range(0, B, CHUNK):
        lb = low[i:i + CHUNK].to(device)
        n = lb.shape[0]
        ob = opq_all[i:i + n].to(device) if opq_all is not None else None
        mb = None
        if mask is not None:
            mb = mask_to_grid_chunk(mask, i, n, h, w, device)

        rgb = None
        if not colour_only:
            rgb = D.dither_tonal(luma_cf(lb), pal_t, method, T, strength)
        if want_colour:
            if mode == "channels":
                col = D.dither_channels(lb, int(v["color_levels"]), method, T, strength)
            else:
                col = D.dither_palette(lb, pal_t, pal_lab, method, T, strength)
            if rgb is None:
                rgb = col
            else:
                rgb = blend(rgb, col, mix_weight(v["mix_mode"], amount, lb, mb))

        rgb = rgb.clamp(0.0, 1.0)
        if ob is not None:
            rgb = rgb * ob                                   # transparent = black
        out_low[i:i + n] = to_bhwc(rgb)
        out_img[i:i + n, :, :, :3] = to_bhwc(nearest_up(rgb, Hout, Wout, cy, cx))
        up_o = nearest_up(ob, Hout, Wout, cy, cx)[:, 0].cpu() if ob is not None else None
        if up_o is not None:
            if rgba:
                out_img[i:i + n, :, :, 3] = up_o
            out_alpha[i:i + n] = 1.0 - up_o
        if want_mask:
            ink = 1.0 - luma_cf(rgb)
            if ob is not None:
                ink = ink * ob
            out_mask[i:i + n] = nearest_up(ink, Hout, Wout, cy, cx)[:, 0].clamp(0.0, 1.0).cpu()

    return {
        "image": out_img,
        "lowres": out_low,
        "mask": out_mask,
        "alpha": out_alpha,
        "palette": palette_to_string(pal),
    }
