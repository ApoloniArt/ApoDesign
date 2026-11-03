"""Palette building for the ApoDesign Palette node. Pure Python (no torch).
Colours are (r, g, b) floats 0..1, like everywhere else in ApoDesign."""
import colorsys

from .palettes import (PRESETS, hex_to_rgb, luma, mix_rgb, palette_to_string,
                       parse_palette, preset_palette, rgb_to_hex)

MODES = ["preset", "hex_list", "from_image", "gradient", "harmony"]
HARMONIES = ["monochrome", "analogous", "complementary", "split_complementary",
             "triadic", "tetradic"]
SORTS = ["dark_to_light", "light_to_dark", "none"]

# hue offsets in turns (1.0 = full circle)
_HUES = {
    "monochrome": [0.0],
    "analogous": [-1 / 12, 0.0, 1 / 12],
    "complementary": [0.0, 0.5],
    "split_complementary": [0.0, 5 / 12, 7 / 12],
    "triadic": [0.0, 1 / 3, 2 / 3],
    "tetradic": [0.0, 0.25, 0.5, 0.75],
}


def gradient(a, b, n, mid=None):
    """n colours from a to b (through mid when given), mixed in gamma space."""
    n = max(2, int(n))
    stops = [a, mid, b] if mid is not None else [a, b]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        out.append(mix_rgb(stops[k], stops[k + 1], t - k))
    return out


def harmony(base, scheme, n):
    """n colours around the base colour's hue: a dark-to-light ramp whose hue
    steps through the chosen colour scheme."""
    n = max(2, int(n))
    h, l, s = colorsys.rgb_to_hls(*base)
    hues = _HUES.get(scheme, [0.0])
    s = max(s, 0.25) if scheme != "monochrome" else s
    out = []
    for i in range(n):
        light = 0.12 + 0.8 * i / (n - 1)
        hue = (h + hues[i % len(hues)]) % 1.0
        sat = s * (0.55 + 0.45 * (1.0 - abs(2.0 * light - 1.0)))   # calmer at the extremes
        out.append(colorsys.hls_to_rgb(hue, light, min(1.0, sat)))
    return out


def finish(colours, sort="dark_to_light", reverse=False):
    """Deduplicate (by hex), sort, and return (list of rgb, hex string)."""
    seen, out = set(), []
    for c in colours:
        hx = rgb_to_hex(c)
        if hx not in seen:
            seen.add(hx)
            out.append(hex_to_rgb(hx))
    if sort == "dark_to_light":
        out.sort(key=luma)
    elif sort == "light_to_dark":
        out.sort(key=luma, reverse=True)
    if reverse:
        out.reverse()
    return out, palette_to_string(out)


def is_tonal(colours):
    """True when the palette is one hue from dark to light (match by brightness)."""
    if len(colours) < 2:
        return True
    hs = []
    for c in colours:
        h, l, s = colorsys.rgb_to_hls(*c)
        if s > 0.15 and 0.1 < l < 0.9:
            hs.append(h)
    if len(hs) < 2:
        return True
    ref = hs[0]
    return all(min(abs(h - ref), 1 - abs(h - ref)) < 0.15 for h in hs)


def from_text(text):
    return parse_palette(text)


def preset(name):
    return preset_palette(name) if name in PRESETS else []
