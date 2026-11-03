"""Dithering engines for ApoDesign (torch only).

Everything is deterministic and anchored to the pixel grid (not the picture
content), so ordered methods are rock-steady across the frames of a video.

Threshold maps (T) follow one convention: a pixel turns "brighter" when
its value is greater than T. Ordered dither, halftone and blue noise are all
the same operation with a different T.

Error diffusion is sequential by nature. Here it runs as a parallel
wavefront: pixels on the line  x + k*y = t  never feed each other, so a whole
diagonal is processed in one vectorised step, for the whole batch at once.
"""
import math

import torch

from .colorspace import nearest_palette_idx, srgb_to_oklab

ORDERED = ("bayer", "blue_noise", "halftone_dots", "halftone_lines", "threshold")

# name -> list of (dx, dy, weight); weights are normalised below.
_RAW_KERNELS = {
    "floyd_steinberg": ([(1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)], 16),
    "atkinson": ([(1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)], 8),
    "sierra": ([(1, 0, 5), (2, 0, 3), (-2, 1, 2), (-1, 1, 4), (0, 1, 5), (1, 1, 4),
                (2, 1, 2), (-1, 2, 2), (0, 2, 3), (1, 2, 2)], 32),
    "sierra_lite": ([(1, 0, 2), (-1, 1, 1), (0, 1, 1)], 4),
    "stucki": ([(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4),
                (2, 1, 2), (-2, 2, 1), (-1, 2, 2), (0, 2, 4), (1, 2, 2), (2, 2, 1)], 42),
    "jarvis": ([(1, 0, 7), (2, 0, 5), (-2, 1, 3), (-1, 1, 5), (0, 1, 7), (1, 1, 5),
                (2, 1, 3), (-2, 2, 1), (-1, 2, 3), (0, 2, 5), (1, 2, 3), (2, 2, 1)], 48),
    "burkes": ([(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4),
                (2, 1, 2)], 32),
}
KERNELS = {name: [(dx, dy, w / div) for dx, dy, w in taps]
           for name, (taps, div) in _RAW_KERNELS.items()}
DIFFUSION = tuple(KERNELS)

_cache = {}


# --------------------------------------------------------------------------
# threshold maps
# --------------------------------------------------------------------------
def bayer_matrix(n):
    """n x n Bayer matrix (n a power of two), values in (0, 1)."""
    key = ("bayer", n)
    if key not in _cache:
        m = torch.zeros(1, 1)
        size = 1
        while size < n:
            m = torch.cat([torch.cat([4 * m, 4 * m + 2], dim=1),
                           torch.cat([4 * m + 3, 4 * m + 1], dim=1)], dim=0)
            size *= 2
        _cache[key] = (m + 0.5) / float(n * n)
    return _cache[key]


def _vc_add(E, G, y, x, s):
    E.add_(torch.roll(G, (y, x), (0, 1)), alpha=s)


def blue_noise_tile(n=64, sigma=1.5, seed=7):
    """Blue-noise threshold tile via Ulichney's void-and-cluster. Seeded, so
    every machine generates the identical tile. Built once, then cached."""
    key = ("blue", n, sigma, seed)
    if key in _cache:
        return _cache[key]
    N = n * n
    g = torch.Generator().manual_seed(seed)
    ax = torch.arange(n, dtype=torch.float64)
    d = torch.minimum(ax, n - ax)
    G = torch.exp(-(d[:, None] ** 2 + d[None, :] ** 2) / (2.0 * sigma * sigma))

    pattern = torch.zeros(n, n, dtype=torch.bool)
    ones = max(2, int(N * 0.1))
    pattern.view(-1)[torch.randperm(N, generator=g)[:ones]] = True
    E = torch.zeros(n, n, dtype=torch.float64)
    for p in torch.nonzero(pattern):
        _vc_add(E, G, int(p[0]), int(p[1]), 1.0)

    ninf, pinf = float("-inf"), float("inf")
    # Phase 0: relax the initial pattern until the tightest cluster and the
    # largest void coincide.
    for _ in range(4 * ones):
        c = int(E.masked_fill(~pattern, ninf).argmax())
        cy, cx = divmod(c, n)
        pattern[cy, cx] = False
        _vc_add(E, G, cy, cx, -1.0)
        v = int(E.masked_fill(pattern, pinf).argmin())
        if v == c:
            pattern[cy, cx] = True
            _vc_add(E, G, cy, cx, 1.0)
            break
        vy, vx = divmod(v, n)
        pattern[vy, vx] = True
        _vc_add(E, G, vy, vx, 1.0)

    ones = int(pattern.sum())
    rank = torch.zeros(N, dtype=torch.float64)
    # Phase 1: peel clusters off the initial pattern -> ranks ones-1 .. 0
    P, E1 = pattern.clone(), E.clone()
    for r in range(ones - 1, -1, -1):
        c = int(E1.masked_fill(~P, ninf).argmax())
        y, x = divmod(c, n)
        rank[c] = r
        P[y, x] = False
        _vc_add(E1, G, y, x, -1.0)
    # Phases 2+3: fill the largest voids -> ranks ones .. N-1
    P, E2 = pattern.clone(), E.clone()
    for r in range(ones, N):
        c = int(E2.masked_fill(P, pinf).argmin())
        y, x = divmod(c, n)
        rank[c] = r
        P[y, x] = True
        _vc_add(E2, G, y, x, 1.0)

    tile = ((rank + 0.5) / N).reshape(n, n).float()
    _cache[key] = tile
    return tile


def _tile(m, h, w, device):
    m = m.to(device)
    n_y, n_x = m.shape
    ys = torch.arange(h, device=device) % n_y
    xs = torch.arange(w, device=device) % n_x
    return m[ys][:, xs]


def _halftone_T(h, w, cell, angle_deg, shape, device):
    """Brightness-threshold map for a rotated halftone screen.

    The spot function is rank-equalised, so a flat grey of value v covers
    exactly (1 - v) of each cell with ink. Dots grow as the picture darkens."""
    cell = max(1.5, float(cell))
    y = (torch.arange(h, device=device, dtype=torch.float32) + 0.5)[:, None]
    x = (torch.arange(w, device=device, dtype=torch.float32) + 0.5)[None, :]
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)
    u = (x * c + y * s) / cell
    v = (-x * s + y * c) / cell
    fx = u - u.floor() - 0.5
    fy = v - v.floor() - 0.5
    if shape == "dot":
        spot = torch.sqrt(fx * fx + fy * fy)
        g = (torch.arange(64, device=device, dtype=torch.float32) + 0.5) / 64.0 - 0.5
        ref = torch.sqrt(g[:, None] ** 2 + g[None, :] ** 2).reshape(-1).sort().values
        pos = torch.searchsorted(ref, spot.contiguous())
        t_spot = (pos.float() + 0.5) / (ref.numel() + 1.0)
    else:  # line screen
        t_spot = (fy.abs() * 2.0).clamp(0.0, 1.0)
    return 1.0 - t_spot


def make_threshold(method, h, w, device, bayer_size=8, cell=6.0, angle=45.0,
                   per_channel=False):
    """Return threshold maps shaped (Cb, h, w); Cb is 1, or 3 for per-channel
    halftone screens (RGB channels get classic offset screen angles)."""
    if method == "bayer":
        return _tile(bayer_matrix(int(bayer_size)), h, w, device)[None]
    if method == "blue_noise":
        return _tile(blue_noise_tile(), h, w, device)[None]
    if method in ("halftone_dots", "halftone_lines"):
        shape = "dot" if method == "halftone_dots" else "line"
        if per_channel:
            angles = [angle - 45.0 + a for a in (15.0, 75.0, 0.0)]
        else:
            angles = [angle]
        return torch.stack([_halftone_T(h, w, cell, a, shape, device) for a in angles])
    # "threshold" (and anything unknown): plain rounding, no dither.
    return torch.full((1, h, w), 0.5, device=device)


# --------------------------------------------------------------------------
# quantisers (used by error diffusion)
# --------------------------------------------------------------------------
def level_quantizer(L):
    """Round each channel to one of L evenly spaced levels."""
    def q(old):
        idx = (old.clamp(0.0, 1.0) * (L - 1)).round()
        return idx / (L - 1), idx.long()
    return q


def palette_quantizer(pal_srgb, pal_lab):
    """Nearest palette colour. old: (B, 3, n) -> (B, 3, n) colours, (B, 1, n) idx."""
    def q(old):
        lab = srgb_to_oklab(old.transpose(1, 2))                      # (B, n, 3)
        d = ((lab[:, :, None, :] - pal_lab[None, None, :, :]) ** 2).sum(-1)
        idx = d.argmin(dim=-1)                                        # (B, n)
        return pal_srgb[idx].transpose(1, 2), idx.unsqueeze(1)
    return q


# --------------------------------------------------------------------------
# error diffusion (parallel wavefront)
# --------------------------------------------------------------------------
def wavefront_k(kernel):
    """Smallest k such that every error tap lands on a later wavefront."""
    k = 1
    for dx, dy, _ in kernel:
        if dy > 0:
            k = max(k, -(-(1 - dx) // dy))
    return k


def error_diffusion(x, quant, kernel_name, strength=1.0):
    """x: (B, C, h, w). quant(old (B,C,n)) -> (new (B,C,n), idx (B,Ci,n)).
    Returns (values (B,C,h,w), idx (B,Ci,h,w))."""
    B, C, h, w = x.shape
    dev = x.device
    ker = KERNELS[kernel_name]
    k = wavefront_k(ker)
    PAD = 2
    Wp = w + 2 * PAD
    buf = torch.zeros(B, C, h + 2, Wp, device=dev, dtype=x.dtype)
    buf[:, :, :h, PAD:PAD + w] = x
    flat = buf.view(B, C, -1)

    _, probe = quant(x[:, :, :1, :1].reshape(B, C, 1))
    out_val = torch.zeros(B, C, h, w, device=dev, dtype=x.dtype)
    out_idx = torch.zeros(B, probe.shape[1], h, w, device=dev, dtype=torch.long)

    rows = torch.arange(h, device=dev)
    taps = [(dy * Wp + dx, wt * strength) for dx, dy, wt in ker]
    for t in range((w - 1) + k * (h - 1) + 1):
        y0 = max(0, -(-(t - (w - 1)) // k))
        y1 = min(h - 1, t // k)
        if y1 < y0:
            continue
        ys = rows[y0:y1 + 1]
        xs = t - k * ys
        pos = ys * Wp + xs + PAD
        old = flat[:, :, pos]
        new, idx = quant(old)
        out_val[:, :, ys, xs] = new
        out_idx[:, :, ys, xs] = idx
        err = old - new
        for off, wt in taps:
            flat.index_add_(2, pos + off, err * wt)
    return out_val, out_idx


# --------------------------------------------------------------------------
# ordered quantisation
# --------------------------------------------------------------------------
def _soften(T, strength):
    return 0.5 + (T - 0.5) * strength


def ordered_levels(x, L, T, strength=1.0):
    """x (B,C,h,w) in 0..1 -> level index (B,C,h,w), using threshold map T."""
    Tt = _soften(T, strength)[None]
    s = x.clamp(0.0, 1.0) * (L - 1)
    fl = s.floor()
    idx = fl + ((s - fl) > Tt).to(s.dtype)
    return idx.clamp(0, L - 1).long()


def ordered_palette(x, pal_srgb, pal_lab, T, strength=1.0):
    """Offset each pixel by the threshold, then snap to the nearest palette
    colour in OKLab. Returns palette index (B, h, w)."""
    P = pal_srgb.shape[0]
    spread = 1.0 / max(1.0, P ** (1.0 / 3.0))
    off = (0.5 - _soften(T[:1], strength))[None] * spread        # (1,1,h,w)
    xo = (x + off).permute(0, 2, 3, 1)                            # (B,h,w,3)
    return nearest_palette_idx(xo, pal_lab)


# --------------------------------------------------------------------------
# the three public layers
# --------------------------------------------------------------------------
def dither_tonal(lum, tone_pal, method, T, strength=1.0):
    """lum (B,1,h,w) -> RGB (B,3,h,w) using the tone palette (N,3), dark->light."""
    N = tone_pal.shape[0]
    if method in DIFFUSION:
        _, idx = error_diffusion(lum, level_quantizer(N), method, strength)
    else:
        idx = ordered_levels(lum, N, T[:1], strength)
    return tone_pal[idx[:, 0]].permute(0, 3, 1, 2)


def dither_channels(x, L, method, T, strength=1.0):
    """x (B,3,h,w) -> RGB where each channel has L levels (classic colour dither)."""
    if method in DIFFUSION:
        val, _ = error_diffusion(x, level_quantizer(L), method, strength)
        return val
    return ordered_levels(x, L, T, strength).to(x.dtype) / (L - 1)


def dither_palette(x, pal_srgb, pal_lab, method, T, strength=1.0):
    """x (B,3,h,w) -> RGB snapped to the palette, colour-preserving."""
    if method in DIFFUSION:
        val, _ = error_diffusion(x, palette_quantizer(pal_srgb, pal_lab), method, strength)
        return val
    idx = ordered_palette(x, pal_srgb, pal_lab, T, strength)
    return pal_srgb[idx].permute(0, 3, 1, 2)
