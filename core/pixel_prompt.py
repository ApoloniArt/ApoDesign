"""Style-prompt parser for the ApoDesign Pixel Art node. Pure Python.

Runs the shared parser (palettes, size, contrast, dither method ...) and adds
pixel-art words: N colours, outline, clean, painterly, dominant / average."""
import re

from .prompt import parse_style_prompt

_TONE_PRESETS = {"black_white", "grey_4", "gameboy", "mint_plum", "ice_blue",
                 "newspaper", "sepia", "amber_crt", "green_phosphor", "virtual_boy"}


def parse_pixel_prompt(text):
    """Return (overrides, notes) for the Pixel Art node."""
    out, _ = parse_style_prompt(text)
    if not text or not text.strip():
        return out, []
    if out.get("method") in ("threshold", "halftone_dots", "halftone_lines"):
        del out["method"]

    t = text.lower().replace("&", " and ")
    t = re.sub(r"[_\-]+", " ", t)
    t = re.sub(r"[^a-z0-9#,.\s]", " ", t)
    t = re.sub(r"\s+", " ", t)

    m = re.search(r"\b(\d{1,2})\s*colou?rs?\b", t)
    if m:
        out["palette_size"] = int(m.group(1))
        if "palette_preset" not in out and "custom_palette" not in out:
            out["palette_preset"] = "adaptive_kmeans"
    if re.search(r"\bno dither(?:ing)?\b", t):
        out["method"] = "none"
    if re.search(r"\boutline[ds]?\b", t):
        out["outline"] = "dark"
    if re.search(r"\bclean(?:ed|up)?\b", t):
        out["cleanup"] = 2
    if re.search(r"\bpainterly\b|\bsmooth(?:ed)?\b|\bsimplif(?:y|ied)\b|\bflat\b", t):
        out["simplify"] = 0.5
    if re.search(r"\bdominant\b", t):
        out["pixel_mode"] = "dominant"
    elif re.search(r"\baverage\b|\bsoft pixels\b", t):
        out["pixel_mode"] = "average"
    elif re.search(r"\bnearest\b", t):
        out["pixel_mode"] = "nearest"
    if re.search(r"\bvibrant\b|\bpunchy\b|\bvivid\b", t):
        out["saturation"] = 1.3
    if out.get("palette_preset") in _TONE_PRESETS:
        out["match"] = "tone"
    if "custom_palette" in out and re.search(r"\bgreyscale\b|\bgrayscale\b|\bmono\b", t):
        out["match"] = "tone"

    notes = ["%s=%s" % (k, v) for k, v in out.items()]
    return out, notes
