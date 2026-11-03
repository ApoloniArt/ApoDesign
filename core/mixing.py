"""Mono <-> colour mixing shared by every ApoDesign node (torch only).

Each node renders two layers:  a "mono" layer (the tonal / palette look)
and a "colour" layer (the colour-preserving look). `mix_weight` decides, per
pixel, how much of the colour layer shows through, so you can have
B&W shadows with colour highlights, colour only where the source is saturated,
B&W line work over colour fills, a MASK-painted region, and so on.
"""
import torch

from .colorspace import luma_cf, sobel_mag, srgb_to_oklab
from .modes import MIX_MODES  # noqa: F401  (re-exported)


def _feature(mode, src, mask):
    """Per-pixel 0..1 'colour-ness' feature for a mix mode. src: (B,3,h,w)."""
    lum = luma_cf(src)
    if mode == "highlights":
        return lum
    if mode == "shadows":
        return 1.0 - lum
    if mode == "saturation":
        lab = srgb_to_oklab(src.permute(0, 2, 3, 1))
        chroma = torch.sqrt(lab[..., 1] ** 2 + lab[..., 2] ** 2).unsqueeze(1)
        return (chroma / 0.25).clamp(0.0, 1.0)
    if mode in ("edges_mono", "edges_colour"):
        e = sobel_mag(lum)
        peak = e.flatten(1).amax(dim=1).view(-1, 1, 1, 1).clamp_min(1e-6)
        e = (e / peak).sqrt()
        return 1.0 - e if mode == "edges_mono" else e
    if mode == "centre":
        B, _, h, w = src.shape
        ys = torch.linspace(-1.0, 1.0, h, device=src.device).view(1, 1, h, 1)
        xs = torch.linspace(-1.0, 1.0, w, device=src.device).view(1, 1, 1, w)
        r = torch.sqrt(ys * ys + xs * xs) / 1.4142
        return (1.0 - r).expand(B, 1, h, w)
    return torch.ones_like(lum)


def mix_weight(mode, amount, src, mask=None, soft=0.25):
    """Weight (B,1,h,w) of the colour layer. amount 0 -> none, 1 -> everywhere."""
    amount = float(max(0.0, min(1.0, amount)))
    B, _, h, w = src.shape
    if mode == "global" or (mode == "mask" and mask is None):
        return torch.full((B, 1, h, w), amount, device=src.device, dtype=src.dtype)
    if mode == "mask":
        return mask.clamp(0.0, 1.0) * amount
    f = _feature(mode, src, mask)
    lo = (1.0 - amount) * (1.0 + soft) - soft
    return ((f - lo) / soft).clamp(0.0, 1.0)


def blend(mono, colour, weight):
    return mono * (1.0 - weight) + colour * weight
