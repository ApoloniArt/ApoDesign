"""Colour maths and small image filters for ApoDesign (torch only).

Conventions
  * colour-last tensors  (..., 3)       -> srgb_to_oklab, oklab_to_srgb, nearest_palette_idx
  * colour-first images  (B, C, H, W)   -> luma_cf, gaussian_blur, sobel_mag
  * sRGB values are gamma-encoded 0..1 everywhere unless a name says "linear".
"""
import math

import torch
import torch.nn.functional as F

_M1 = [[0.4122214708, 0.5363325363, 0.0514459929],
       [0.2119034982, 0.6806995451, 0.1073969566],
       [0.0883024619, 0.2817188376, 0.6299787005]]
_M2 = [[0.2104542553, 0.7936177850, -0.0040720468],
       [1.9779984951, -2.4285922050, 0.4505937099],
       [0.0259040371, 0.7827717662, -0.8086757660]]
_M1_INV = torch.linalg.inv(torch.tensor(_M1, dtype=torch.float64)).tolist()
_M2_INV = torch.linalg.inv(torch.tensor(_M2, dtype=torch.float64)).tolist()
_LUMA = (0.2126, 0.7152, 0.0722)


def _mat(m, ref):
    return torch.tensor(m, dtype=ref.dtype, device=ref.device)


def srgb_to_linear(c):
    c = c.clamp(0.0, 1.0)
    return torch.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = c.clamp(0.0, 1.0)
    return torch.where(c <= 0.0031308, c * 12.92, 1.055 * c.pow(1.0 / 2.4) - 0.055)


def srgb_to_oklab(c):
    """(..., 3) sRGB -> (..., 3) OKLab (L, a, b). Input is clamped to 0..1."""
    lin = srgb_to_linear(c)
    lms = lin @ _mat(_M1, lin).T
    lms = torch.sign(lms) * lms.abs().pow(1.0 / 3.0)
    return lms @ _mat(_M2, lin).T


def oklab_to_srgb(lab):
    lms = lab @ _mat(_M2_INV, lab).T
    lms = lms * lms * lms
    lin = lms @ _mat(_M1_INV, lab).T
    return linear_to_srgb(lin)


def luma_cf(x):
    """(B, 3, H, W) -> (B, 1, H, W) Rec.709 luma on gamma-encoded values."""
    w = torch.tensor(_LUMA, dtype=x.dtype, device=x.device).view(1, 3, 1, 1)
    return (x * w).sum(dim=1, keepdim=True)


def gaussian_blur(x, sigma):
    """Separable gaussian blur of a (B, C, H, W) tensor, reflect-padded."""
    if sigma <= 0:
        return x
    h, w = x.shape[-2:]
    radius = max(1, min(int(math.ceil(3.0 * sigma)), min(h, w) - 1))
    ax = torch.arange(-radius, radius + 1, dtype=x.dtype, device=x.device)
    k = torch.exp(-(ax ** 2) / (2.0 * sigma * sigma))
    k = k / k.sum()
    c = x.shape[1]
    kh = k.view(1, 1, 1, -1).expand(c, 1, 1, -1)
    kv = k.view(1, 1, -1, 1).expand(c, 1, -1, 1)
    x = F.pad(x, (radius, radius, 0, 0), mode="reflect")
    x = F.conv2d(x, kh, groups=c)
    x = F.pad(x, (0, 0, radius, radius), mode="reflect")
    return F.conv2d(x, kv, groups=c)


def sobel_mag(lum):
    """(B, 1, H, W) -> gradient magnitude, same shape."""
    kx = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]],
                      dtype=lum.dtype, device=lum.device).view(1, 1, 3, 3)
    ky = kx.transpose(2, 3)
    p = F.pad(lum, (1, 1, 1, 1), mode="replicate")
    gx = F.conv2d(p, kx)
    gy = F.conv2d(p, ky)
    return torch.sqrt(gx * gx + gy * gy)


def nearest_palette_idx(x, pal_lab, chunk=1 << 20):
    """Index of the nearest palette colour (OKLab distance) for sRGB (..., 3)."""
    shape = x.shape[:-1]
    lab = srgb_to_oklab(x).reshape(-1, 3)
    out = torch.empty(lab.shape[0], dtype=torch.long, device=x.device)
    for i in range(0, lab.shape[0], chunk):
        d = torch.cdist(lab[i:i + chunk], pal_lab,
                        compute_mode="donot_use_mm_for_euclid_dist")
        out[i:i + chunk] = d.argmin(dim=1)
    return out.reshape(shape)


def kmeans_oklab(lab, k, iters=12, seed=0):
    """Deterministic k-means++ / Lloyd in OKLab. lab: (N, 3). Returns (k, 3)."""
    n = lab.shape[0]
    k = max(1, min(int(k), n))
    g = torch.Generator().manual_seed(int(seed))
    first = int(torch.randint(0, n, (1,), generator=g).item())
    cent = [lab[first]]
    d2 = ((lab - cent[0]) ** 2).sum(dim=1)
    for _ in range(1, k):
        total = float(d2.sum().item())
        if total < 1e-12:
            probs = torch.ones(n)
        else:
            probs = (d2 / total).cpu().clamp_min(0)
        idx = int(torch.multinomial(probs, 1, generator=g).item())
        cent.append(lab[idx])
        d2 = torch.minimum(d2, ((lab - lab[idx]) ** 2).sum(dim=1))
    cents = torch.stack(cent)
    for _ in range(iters):
        a = torch.cdist(lab, cents).argmin(dim=1)
        sums = torch.zeros_like(cents).index_add_(0, a, lab)
        cnt = torch.bincount(a, minlength=cents.shape[0]).to(lab.dtype).unsqueeze(1)
        cents = torch.where(cnt > 0, sums / cnt.clamp_min(1.0), cents)
    return cents
