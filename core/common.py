"""Shared image plumbing for ApoDesign nodes (torch only)."""
import torch
import torch.nn.functional as F


def pick_device():
    """ComfyUI's compute device when running inside ComfyUI, else cuda/cpu."""
    try:
        import comfy.model_management as mm
        return mm.get_torch_device()
    except Exception:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def to_chw(img):
    """ComfyUI IMAGE (B, H, W, C) -> float32 (B, 3, H, W). Drops alpha."""
    x = img.float()
    if x.shape[-1] == 1:
        x = x.expand(-1, -1, -1, 3)
    return x[..., :3].permute(0, 3, 1, 2).contiguous()


def to_bhwc(x):
    """(B, 3, H, W) -> ComfyUI IMAGE on the CPU, clamped to 0..1."""
    return x.clamp(0.0, 1.0).permute(0, 2, 3, 1).contiguous().cpu()


def grid_size(H, W, pixel_size, target_width):
    """Size (h, w) of the low-res grid and whether integer blocks are used."""
    if target_width and target_width > 0:
        w = max(1, min(int(target_width), W))
        h = max(1, int(round(w * H / W)))
        return h, w, False
    ps = max(1, int(pixel_size))
    return -(-H // ps), -(-W // ps), True


def downsample(x, h, w, pixel_size, integer_blocks):
    """Block-average (B, C, H, W) down to the (h, w) grid."""
    H, W = x.shape[-2:]
    if integer_blocks:
        ps = max(1, int(pixel_size))
        if ps == 1:
            return x
        ph, pw = h * ps - H, w * ps - W
        if ph or pw:
            x = F.pad(x, (0, pw, 0, ph), mode="replicate")
        return F.avg_pool2d(x, ps)
    return F.adaptive_avg_pool2d(x, (h, w))


def nearest_up(x, Hout, Wout, cell_y, cell_x):
    """Crisp nearest-neighbour upscale where each low-res cell spans
    (cell_y, cell_x) output pixels (floats allowed, e.g. 7.5 for 256 -> 1920)."""
    h, w = x.shape[-2:]
    iy = ((torch.arange(Hout, device=x.device, dtype=torch.float32) + 0.5)
          / cell_y).floor().long().clamp(0, h - 1)
    ix = ((torch.arange(Wout, device=x.device, dtype=torch.float32) + 0.5)
          / cell_x).floor().long().clamp(0, w - 1)
    return x[..., iy, :][..., :, ix]


def mask_to_grid_chunk(mask, start, n, h, w, device):
    """Frames start..start+n-1 of a ComfyUI MASK, pooled to (n, 1, h, w) on
    `device`. A mask with fewer frames than the batch repeats (a single mask
    applies to every frame). Works one chunk at a time, so a long video never
    needs its whole mask grid in memory at once."""
    m = mask.float()
    if m.dim() == 2:
        m = m.unsqueeze(0)
    m = m[torch.arange(start, start + n) % m.shape[0]]
    return F.adaptive_avg_pool2d(m.unsqueeze(1).to(device), (h, w)).clamp(0.0, 1.0)


# --------------------------------------------------------------------------
# transparency
#   ComfyUI MASKs from Load Image are 1 where the picture is TRANSPARENT.
#   Inside ApoDesign "opacity" is the opposite: 1 = opaque.
# --------------------------------------------------------------------------
def has_transparency(mask):
    """True when a MASK actually makes something transparent."""
    return mask is not None and mask.numel() > 0 and float(mask.max()) > 1e-3


def pick_alpha(mask, transparency, mix_mode=None, invert=False):
    """-> (mask to use as transparency or None, output RGBA?).
    A mask that is all zero (fully opaque) is ignored, so ordinary opaque
    pictures and videos keep their plain 3-channel output. invert flips a
    mask that follows the other convention (white = opaque)."""
    if mask is None or transparency == "off" or mix_mode == "mask":
        return None, False
    if invert:
        mask = 1.0 - mask.float().clamp(0.0, 1.0)
    if not has_transparency(mask):
        return None, False
    return mask, transparency == "rgba"


def opacity_chunk(mask, start, n, H, W, device):
    """Frames start..start+n-1 of a MASK as opacity (n,1,H,W), 1 = opaque.
    A mask with fewer frames than the batch repeats; a mask of another size
    is resized."""
    m = mask.float()
    if m.dim() == 2:
        m = m.unsqueeze(0)
    m = m[torch.arange(start, start + n) % m.shape[0]].unsqueeze(1).to(device)
    if m.shape[-2:] != (H, W):
        m = F.interpolate(m, size=(H, W), mode="bilinear", align_corners=False)
    return 1.0 - m.clamp(0.0, 1.0)


def weighted_pool(pool, x, a):
    """Alpha-weighted pooling, so the colour hiding under transparent pixels
    never bleeds into the result. pool: any function that pools (B,C,H,W).
    Returns (colour (B,3,h,w), coverage (B,1,h,w))."""
    cover = pool(a)
    return pool(x * a) / cover.clamp_min(1e-4), cover


def fill_transparent(rgb, opq):
    """Give transparent cells the mean colour of the opaque ones (per frame),
    so they cannot skew tone adjustments, dithering or palettes."""
    m = opq.to(rgb.dtype)
    cnt = m.sum(dim=(2, 3), keepdim=True)
    mean = (rgb * m).sum(dim=(2, 3), keepdim=True) / cnt.clamp_min(1.0)
    mean = torch.where(cnt > 0, mean, torch.full_like(mean, 0.5))
    return rgb * m + mean * (1.0 - m)


def release_gpu(device):
    """After a long batch, hand cached GPU memory back so ComfyUI's models
    can use it. Harmless if anything about this is unavailable."""
    try:
        if str(device).startswith("cuda"):
            try:
                import comfy.model_management as mm
                mm.soft_empty_cache()
            except Exception:
                torch.cuda.empty_cache()
    except Exception:
        pass


def mask_to_grid(mask, B, h, w, device):
    """ComfyUI MASK (B,H,W) or (H,W) -> (B, 1, h, w) on `device`."""
    m = mask.float()
    if m.dim() == 2:
        m = m.unsqueeze(0)
    m = F.adaptive_avg_pool2d(m.unsqueeze(1).to(device), (h, w)).clamp(0.0, 1.0)
    if m.shape[0] != B:
        m = m[torch.arange(B) % m.shape[0]]
    return m
