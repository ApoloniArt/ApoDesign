"""Palette helpers for ApoDesign. Pure Python, no dependencies.

Colours are (r, g, b) tuples of floats in 0..1 (sRGB, gamma-encoded).
Palettes travel as plain hex strings ("#0f380f,#306230,...") so they are easy
to copy, paste and share.
"""
import re

# Order here is the order shown in the dropdown.
PRESETS = {
    "black_white": ["#000000", "#ffffff"],
    "grey_4": ["#000000", "#555555", "#aaaaaa", "#ffffff"],
    "gameboy": ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"],
    # Sampled from the user's reference images.
    "mint_plum": ["#281729", "#e1fee0"],
    "ice_blue": ["#252559", "#576d86", "#b4d7e4"],
    "newspaper": ["#1a1a1a", "#f0ead6"],
    "sepia": ["#2b1d0e", "#7a5a34", "#e9d8b0"],
    "amber_crt": ["#000000", "#3a1c00", "#a85b00", "#ffb000"],
    "green_phosphor": ["#000000", "#003b00", "#00a800", "#33ff33"],
    "virtual_boy": ["#000000", "#550000", "#aa0000", "#ff0000"],
    "cga_pal1": ["#000000", "#55ffff", "#ff55ff", "#ffffff"],
    "cga_pal0": ["#000000", "#55ff55", "#ff5555", "#ffff55"],
    "ega": ["#000000", "#0000aa", "#00aa00", "#00aaaa", "#aa0000", "#aa00aa",
            "#aa5500", "#aaaaaa", "#555555", "#5555ff", "#55ff55", "#55ffff",
            "#ff5555", "#ff55ff", "#ffff55", "#ffffff"],
    "c64": ["#000000", "#ffffff", "#68372b", "#70a4b2", "#6f3d86", "#588d43",
            "#352879", "#b8c76f", "#6f4f25", "#433900", "#9a6759", "#444444",
            "#6c6c6c", "#9ad284", "#6c5eb5", "#959595"],
    "pico8": ["#000000", "#1d2b53", "#7e2553", "#008751", "#ab5236", "#5f574f",
              "#c2c3c7", "#fff1e8", "#ff004d", "#ffa300", "#ffec27", "#00e436",
              "#29adff", "#83769c", "#ff77a8", "#ffccaa"],
    "zx_spectrum": ["#000000", "#0000d7", "#d70000", "#d700d7", "#00d700",
                    "#00d7d7", "#d7d700", "#d7d7d7", "#0000ff", "#ff0000",
                    "#ff00ff", "#00ff00", "#00ffff", "#ffff00", "#ffffff"],
    "nes": ["#7c7c7c", "#0000fc", "#0000bc", "#4428bc", "#940084", "#a80020",
            "#a81000", "#881400", "#503000", "#007800", "#006800", "#005800",
            "#004058", "#000000", "#bcbcbc", "#0078f8", "#0058f8", "#6844fc",
            "#d800cc", "#e40058", "#f83800", "#e45c10", "#ac7c00", "#00b800",
            "#00a800", "#00a844", "#008888", "#f8f8f8", "#3cbcfc", "#6888fc",
            "#9878f8", "#f878f8", "#f85898", "#f87858", "#fca044", "#f8b800",
            "#b8f818", "#58d854", "#58f898", "#00e8d8", "#787878", "#fcfcfc",
            "#a4e4fc", "#b8b8f8", "#d8b8f8", "#f8b8f8", "#f8a4c0", "#f0d0b0",
            "#fce0a8", "#f8d878", "#d8f878", "#b8f8b8", "#b8f8d8", "#00fcfc",
            "#f8d8f8"],
    "apple_ii": ["#000000", "#e31e60", "#604ebd", "#ff44fd", "#00a360",
                 "#9c9c9c", "#14cffd", "#d0c3ff", "#607203", "#ff6a3c",
                 "#ffa0d0", "#14f53c", "#d0dd8d", "#72ffd0", "#ffffff"],
    "msx": ["#000000", "#3eb849", "#74d07d", "#5955e0", "#8076f1", "#b95e51",
            "#65dbef", "#db6559", "#ff897d", "#ccc35e", "#ded087", "#3aa241",
            "#b766b5", "#cccccc", "#ffffff"],
    "amstrad_cpc": ["#%02x%02x%02x" % (r, g, b)
                    for r in (0, 128, 255) for g in (0, 128, 255) for b in (0, 128, 255)],
    "teletext": ["#000000", "#ff0000", "#00ff00", "#ffff00", "#0000ff",
                 "#ff00ff", "#00ffff", "#ffffff"],
    "sweetie16": ["#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75",
                  "#a7f070", "#38b764", "#257179", "#29366f", "#3b5dc9",
                  "#41a6f6", "#73eff7", "#f4f4f4", "#94b0c2", "#566c86",
                  "#333c57"],
}

# Words people might type -> preset key (used by the prompt parser).
PRESET_ALIASES = {
    "black and white": "black_white", "black white": "black_white",
    "grey 4": "grey_4", "gray 4": "grey_4", "4 grey": "grey_4",
    "game boy": "gameboy", "gameboy": "gameboy", "dmg": "gameboy",
    "mint plum": "mint_plum", "ice blue": "ice_blue",
    "newspaper": "newspaper", "newsprint": "newspaper",
    "sepia": "sepia", "amber": "amber_crt", "amber crt": "amber_crt",
    "green phosphor": "green_phosphor", "phosphor": "green_phosphor",
    "virtual boy": "virtual_boy",
    "cga": "cga_pal1", "cga pal1": "cga_pal1", "cga pal0": "cga_pal0",
    "ega": "ega", "c64": "c64", "commodore": "c64", "commodore 64": "c64",
    "pico 8": "pico8", "pico8": "pico8",
    "zx spectrum": "zx_spectrum", "spectrum": "zx_spectrum",
    "nes": "nes", "famicom": "nes", "nintendo": "nes",
    "apple ii": "apple_ii", "apple 2": "apple_ii",
    "msx": "msx", "amstrad": "amstrad_cpc", "cpc": "amstrad_cpc",
    "teletext": "teletext", "ceefax": "teletext",
    "sweetie 16": "sweetie16", "sweetie16": "sweetie16",
}


def hex_to_rgb(text):
    """'#rrggbb' / 'rrggbb' / '#rgb' -> (r, g, b) floats, or None if invalid."""
    if not isinstance(text, str):
        return None
    m = re.fullmatch(r"\s*(#[0-9a-fA-F]{3}|#?[0-9a-fA-F]{6})\s*", text)
    if not m:
        return None
    h = m.group(1).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    r, g, b = (max(0, min(255, int(round(c * 255)))) for c in rgb)
    return "#%02x%02x%02x" % (r, g, b)


def parse_palette(text):
    """Split a free-form string into valid colours (invalid tokens are skipped)."""
    out = []
    for tok in re.split(r"[,;\s]+", text or ""):
        if tok:
            c = hex_to_rgb(tok)
            if c is not None:
                out.append(c)
    return out


def luma(rgb):
    """Rec.709 luma on gamma-encoded values (what dithering has always used)."""
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def sort_by_luma(palette):
    return sorted(palette, key=luma)


def palette_to_string(palette):
    return ",".join(rgb_to_hex(c) for c in palette)


def mix_rgb(a, b, t):
    """Linear mix a -> b by t (0..1), in gamma space (fine for UI shading)."""
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(3))


def preset_palette(name):
    return [hex_to_rgb(h) for h in PRESETS[name]]
