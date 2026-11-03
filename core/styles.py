"""Named looks for the ApoDesign Style node. Pure Python (no torch).

Every look holds one recipe per render node (Bitmap, Ascii, Pixel Art). A
recipe is a dict of widget names and values, exactly what the style_json
input of that node understands. The Style node adds a baseline of defaults
under the recipe (so the look is the same whatever the node's widgets say)
and hands each recipe out on its own output.
"""
import json

from . import ascii_specs, bitmap_specs, pixel_specs, userlooks
from .params import coerce, defaults

NODES = ("bitmap", "ascii", "pixel_art")
SPEC_MAPS = {
    "bitmap": {s.name: s for s in bitmap_specs.SPECS},
    "ascii": {s.name: s for s in ascii_specs.SPECS},
    "pixel_art": {s.name: s for s in pixel_specs.SPECS},
}
ALL_SPECS = {"bitmap": bitmap_specs.SPECS, "ascii": ascii_specs.SPECS,
             "pixel_art": pixel_specs.SPECS}

# Widgets the baseline leaves alone, so your own tone tweaks, output size and
# font choice survive a change of look (a look can still set them itself).
KEEP = {"output_scale", "brightness", "contrast", "gamma", "sharpen",
        "local_contrast", "invert", "saturation", "font", "font_file"}

# One-hue, dark-to-light palettes: matched by brightness.
TONAL = {"black_white", "grey_4", "gameboy", "mint_plum", "ice_blue",
         "newspaper", "sepia", "amber_crt", "green_phosphor", "virtual_boy"}


# --------------------------------------------------------------------------
# recipe builders
# --------------------------------------------------------------------------
def bm(preset, width=0, method="bayer", **kw):
    d = {"palette_preset": preset, "method": method,
         "color_mode": "tonal" if preset in TONAL or preset == "ink_paper" else "palette"}
    if width:
        d["target_width"] = width
    if method == "bayer":
        d["bayer_size"] = "4"
    d.update(kw)
    return d


def asc(preset, columns=120, **kw):
    d = {"palette_preset": preset, "columns": columns, "glyph_match": "ramp",
         "charset": "standard", "polarity": "light_on_dark",
         "color_mode": "tonal" if preset in TONAL or preset == "ink_paper" else "palette"}
    d.update(kw)
    return d


def px(preset, width, **kw):
    d = {"palette_preset": preset, "target_width": width, "pixel_mode": "dominant",
         "match": "tone" if preset in TONAL else "colour", "cleanup": 1,
         "simplify": 0.3}
    d.update(kw)
    return d


def custom(colours):
    return {"custom_palette": ",".join(colours)}


LOOKS = []


def look(name, desc, bitmap, ascii_, pixel):
    LOOKS.append({"name": name, "desc": desc, "bitmap": bitmap, "ascii": ascii_,
                  "pixel_art": pixel})


# --------------------------------------------------------------------------
# consoles and home computers
# --------------------------------------------------------------------------
look("Game Boy (green)", "The original Game Boy: four greens, 160 pixels across.",
     bm("gameboy", 160, contrast=1.2), asc("gameboy", 100), px("gameboy", 160))
look("Game Boy Camera", "Grainy 128-pixel photos, ordered dither, four greens.",
     bm("gameboy", 128, contrast=1.35, gamma=1.1),
     asc("gameboy", 80, method="bayer", bayer_size="4", contrast=1.3),
     px("gameboy", 128, pixel_mode="average", method="bayer", bayer_size="4",
        cleanup=0, simplify=0.0, contrast=1.3))
look("Game Boy Pocket (grey)", "Four greys, 160 pixels across.",
     bm("grey_4", 160, contrast=1.15), asc("grey_4", 100), px("grey_4", 160))
look("NES 8-bit", "The 8-bit Nintendo palette at 256 pixels across: clean flat colour.",
     bm("nes", 256, bayer_size="2", dither_strength=0.6),
     asc("nes", 110, charset="blocks"),
     px("nes", 256, simplify=0.4, saturation=1.2, cleanup=1))
look("16-bit console (SNES style)", "32 adaptive colours, 256 across, gentle outlines.",
     bm("adaptive_kmeans", 256, palette_size=16, bayer_size="4", dither_strength=0.7),
     asc("adaptive_kmeans", 110, palette_size=16, color_mode="channels", color_levels=4),
     px("adaptive_kmeans", 256, palette_size=32, simplify=0.35, saturation=1.15,
        outline="dark", outline_threshold=0.16))
look("Commodore 64", "The C64's 16 colours, 160 across (multicolour mode).",
     bm("c64", 160, bayer_size="4"), asc("c64", 100),
     px("c64", 160, simplify=0.35))
look("ZX Spectrum", "15 bright colours, 256 across, crunchy ordered dither.",
     bm("zx_spectrum", 256, bayer_size="4"), asc("zx_spectrum", 110),
     px("zx_spectrum", 256, simplify=0.3, saturation=1.1))
look("Apple II", "The Apple II's lo-res colours at 140 across.",
     bm("apple_ii", 140, bayer_size="4"), asc("apple_ii", 90),
     px("apple_ii", 140, simplify=0.35))
look("MSX", "The MSX 15-colour palette at 256 across.",
     bm("msx", 256, bayer_size="4"), asc("msx", 110), px("msx", 256))
look("Amstrad CPC", "Bold 27-colour CPC palette at 160 across.",
     bm("amstrad_cpc", 160, bayer_size="4"), asc("amstrad_cpc", 100),
     px("amstrad_cpc", 160, saturation=1.1))
look("CGA (cyan, magenta)", "The famous four-colour CGA palette, 320 across, ordered dither.",
     bm("cga_pal1", 320, bayer_size="4"), asc("cga_pal1", 110),
     px("cga_pal1", 320, pixel_mode="average", method="bayer", bayer_size="4",
        cleanup=0, simplify=0.0))
look("CGA (red, green, yellow)", "The other CGA palette: black, green, red, yellow.",
     bm("cga_pal0", 320, bayer_size="4"), asc("cga_pal0", 110),
     px("cga_pal0", 320, pixel_mode="average", method="bayer", bayer_size="4",
        cleanup=0, simplify=0.0))
look("EGA 16 colour", "The 16 EGA colours at 320 across.",
     bm("ega", 320, bayer_size="4"), asc("ega", 110),
     px("ega", 320, simplify=0.3))
look("PICO-8 fantasy console", "The PICO-8 16-colour palette at 128 across.",
     bm("pico8", 128, bayer_size="4"), asc("pico8", 90),
     px("pico8", 128, simplify=0.4, cleanup=1))
look("Sweetie 16 (indie pixel art)", "A popular modern 16-colour pixel-art palette.",
     bm("sweetie16", 192, bayer_size="4"), asc("sweetie16", 100),
     px("sweetie16", 192, simplify=0.4, outline="dark"))
look("Teletext blocks", "Chunky 8-colour mosaic blocks, like 80s TV text pages.",
     bm("teletext", 80, "bayer", dither_strength=0.0, color_mode="palette"),
     asc("teletext", 60, glyph_match="shape", charset="quadrants"),
     px("teletext", 80, simplify=0.2))
look("Virtual Boy (red)", "Red-on-black four-level image, 192 pixels across.",
     bm("virtual_boy", 192, bayer_size="2"), asc("virtual_boy", 100),
     px("virtual_boy", 192))
look("Amber CRT monitor", "Amber monochrome monitor look with a fine ordered dither.",
     bm("amber_crt", 320, bayer_size="4", contrast=1.15),
     asc("amber_crt", 120), px("amber_crt", 240, simplify=0.2))
look("Green phosphor CRT", "Old green-screen terminal monitor look.",
     bm("green_phosphor", 320, bayer_size="4", contrast=1.15),
     asc("green_phosphor", 120), px("green_phosphor", 240, simplify=0.2))

# --------------------------------------------------------------------------
# modern pixel art
# --------------------------------------------------------------------------
look("Modern pixel art (clean)", "24 colours, painterly flattening, selective outline.",
     bm("adaptive_kmeans", 0, "bayer", palette_size=8, pixel_size=4, color_mode="palette"),
     asc("adaptive_kmeans", 100, palette_size=16, color_mode="channels", color_levels=4),
     px("adaptive_kmeans", 200, palette_size=24, simplify=0.4, saturation=1.2,
        outline="dark"))
look("Arcade 16-colour", "Punchy 16-colour arcade look with black outlines, 224 across.",
     bm("adaptive_kmeans", 224, palette_size=8, color_mode="palette"),
     asc("adaptive_kmeans", 100, palette_size=16, color_mode="channels", color_levels=3),
     px("adaptive_kmeans", 224, palette_size=16, simplify=0.3, saturation=1.3,
        outline="colour", outline_color="#000000"))
look("Painterly pixel art (detailed)", "48 colours at 320 across: lots of detail, still clearly pixels.",
     bm("adaptive_kmeans", 320, palette_size=16, color_mode="palette", dither_strength=0.5),
     asc("adaptive_kmeans", 140, color_mode="channels", color_levels=6, palette_size=32),
     px("adaptive_kmeans", 320, palette_size=48, simplify=0.7, saturation=1.1))
look("Chunky mini sprite", "Tiny 64-pixel sprite, 12 colours, black outline.",
     bm("adaptive_kmeans", 64, palette_size=6, color_mode="palette"),
     asc("adaptive_kmeans", 48, palette_size=8, color_mode="palette", charset="blocks"),
     px("adaptive_kmeans", 64, palette_size=12, simplify=0.5, cleanup=2,
        outline="colour", outline_color="#000000", saturation=1.2))
look("Flat poster colours", "Six flat colours, no texture: screen-print poster.",
     bm("adaptive_kmeans", 0, "bayer", dither_strength=0.0, palette_size=6, pixel_size=2, color_mode="palette"),
     asc("adaptive_kmeans", 100, palette_size=6, color_mode="palette", charset="blocks"),
     px("adaptive_kmeans", 0, palette_size=6, simplify=0.85, cleanup=3,
        pixel_size=2, saturation=1.2))
look("Synthwave neon", "Deep purple to hot pink and cyan, 240 across.",
     bm("ink_paper", 0, "bayer", pixel_size=3, **custom(
         ["#0d0221", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0", "#fdf6ff"]),
        color_mode="palette"),
     asc("ink_paper", 120, **custom(
         ["#0d0221", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0", "#fdf6ff"]),
         color_mode="palette"),
     px("adaptive_kmeans", 240, match="colour", saturation=1.2, **custom(
         ["#0d0221", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0", "#fdf6ff"])))
look("Comic book", "Bold flat colours, black outlines and Ben-Day style dots.",
     bm("ink_paper", 0, "halftone_dots", pixel_size=1, halftone_cell=8,
        halftone_angle=45.0, color_mode="channels", color_levels=2, contrast=1.15),
     asc("adaptive_kmeans", 120, color_mode="channels", color_levels=3,
         edge_strength=0.4),
     px("adaptive_kmeans", 240, palette_size=10, simplify=0.6, saturation=1.4,
        outline="colour", outline_color="#000000", cleanup=2))

# --------------------------------------------------------------------------
# one-bit, print and graphic looks
# --------------------------------------------------------------------------
look("Mac Plus 1-bit (Atkinson)", "Black and white, Atkinson dither, 512 across: the early Mac look.",
     bm("black_white", 512, "atkinson"),
     asc("black_white", 120, polarity="dark_on_light"),
     px("black_white", 320, pixel_mode="average", method="atkinson", cleanup=0,
        simplify=0.0))
look("Floyd-Steinberg 1-bit", "Black and white error diffusion with a soft, organic grain.",
     bm("black_white", 0, "floyd_steinberg", pixel_size=2),
     asc("black_white", 140, method="floyd_steinberg"),
     px("black_white", 320, pixel_mode="average", method="floyd_steinberg", cleanup=0,
        simplify=0.0))
look("Blue-noise 1-bit (heavy)", "High-contrast 1-bit with blue-noise grain, steady on video.",
     bm("black_white", 0, "blue_noise", pixel_size=2, contrast=1.2, local_contrast=0.5),
     asc("black_white", 140, method="blue_noise", contrast=1.2),
     px("black_white", 320, pixel_mode="average", method="blue_noise", cleanup=0,
        simplify=0.0, contrast=1.2))
look("Ordered 1-bit (Bayer 8x8)", "Crosshatch-like ordered dither, perfectly steady on video.",
     bm("black_white", 0, "bayer", pixel_size=2, bayer_size="8"),
     asc("black_white", 140, method="bayer", bayer_size="8"),
     px("black_white", 320, pixel_mode="average", method="bayer", bayer_size="8",
        cleanup=0, simplify=0.0))
look("Newspaper halftone", "Black dots on newsprint, like a printed photo.",
     bm("newspaper", 0, "halftone_dots", pixel_size=1, halftone_cell=6,
        halftone_angle=45.0, contrast=1.15),
     asc("newspaper", 110, polarity="dark_on_light", charset="standard"),
     px("newspaper", 240, pixel_mode="average", method="bayer", bayer_size="4",
        cleanup=0, simplify=0.0))
look("Engraving (line screen)", "Fine parallel lines of ink on cream paper, like a banknote engraving.",
     bm("ink_paper", 0, "halftone_lines", pixel_size=1, halftone_cell=5,
        halftone_angle=30.0, ink_color="#1b1b1b", paper_color="#f2ecd8", contrast=1.2),
     asc("ink_paper", 140, polarity="dark_on_light", ink_color="#1b1b1b",
         paper_color="#f2ecd8", edge_strength=0.7),
     px("sepia", 240, simplify=0.5, outline="dark", cleanup=1))
look("Photocopy", "Harsh black-and-white copy: high contrast, no greys.",
     bm("black_white", 0, "threshold", pixel_size=1, contrast=1.3, local_contrast=1.0),
     asc("black_white", 140, polarity="dark_on_light", charset="simple", contrast=1.4),
     px("black_white", 320, simplify=0.5, cleanup=2, contrast=1.4))
look("Thermal printer receipt", "Receipt-printer dither: dark grey on warm white, 384 across.",
     bm("ink_paper", 384, "floyd_steinberg", ink_color="#2b2b2b", paper_color="#f5f2ea"),
     asc("newspaper", 48, polarity="dark_on_light"),
     px("newspaper", 192, pixel_mode="average", method="floyd_steinberg", cleanup=0,
        simplify=0.0))
look("Risograph duotone", "Two-ink print: ultramarine on cream with grainy shadows.",
     bm("ink_paper", 0, "blue_noise", pixel_size=2, ink_color="#243a8c",
        paper_color="#f7efe0", contrast=1.1),
     asc("ink_paper", 130, polarity="dark_on_light", ink_color="#243a8c",
         paper_color="#f7efe0", method="blue_noise"),
     px("adaptive_kmeans", 240, match="tone", simplify=0.4, cleanup=1,
        palette_size=4, **custom(["#243a8c", "#6d7fcb", "#c8cdea", "#f7efe0"])))
look("Blueprint", "White-blue technical drawing look.",
     bm("ink_paper", 0, "bayer", pixel_size=2, ink_color="#0a2f7a", paper_color="#e6f0ff",
        contrast=1.15),
     asc("ink_paper", 130, ink_color="#0a2f7a", paper_color="#e6f0ff", edge_strength=0.5),
     px("adaptive_kmeans", 240, match="tone", outline="colour", outline_color="#e6f0ff",
        **custom(["#0a2f7a", "#2a5cb8", "#8fb4ee", "#e6f0ff"])))
look("Sepia print", "Warm brown-and-cream old photograph.",
     bm("sepia", 0, "atkinson", pixel_size=2),
     asc("sepia", 130, polarity="dark_on_light"),
     px("sepia", 240, simplify=0.4))

# --------------------------------------------------------------------------
# text looks
# --------------------------------------------------------------------------
look("ASCII classic (white on black)", "The standard ASCII portrait: bright characters on black.",
     bm("black_white", 0, "bayer", pixel_size=2, bayer_size="4"),
     asc("black_white", 120),
     px("black_white", 160, pixel_mode="average", method="bayer", bayer_size="4",
        cleanup=0, simplify=0.0))
look("ASCII print (black on white)", "Dark characters on white paper.",
     bm("black_white", 0, "bayer", pixel_size=2, bayer_size="4"),
     asc("black_white", 120, polarity="dark_on_light"),
     px("black_white", 160, pixel_mode="average", method="bayer", bayer_size="4",
        cleanup=0, simplify=0.0))
look("Matrix code (green letters)", "Green letters and digits on black.",
     bm("green_phosphor", 320, bayer_size="4"),
     asc("green_phosphor", 140, charset="letters", font_bold=True),
     px("green_phosphor", 200))
look("Amber terminal text", "Amber characters on a dark brown-black page.",
     bm("amber_crt", 320, bayer_size="4"),
     asc("amber_crt", 130), px("amber_crt", 200))
look("Braille art", "Tiny braille dots, the finest text detail: 160 characters across.",
     bm("black_white", 0, "blue_noise", pixel_size=2),
     asc("black_white", 160, glyph_match="braille", method="bayer", bayer_size="4"),
     px("black_white", 320, pixel_mode="average", method="blue_noise", cleanup=0,
        simplify=0.0))
look("Block mosaic (quadrants)", "Chunky half and quarter block characters that follow the drawing.",
     bm("black_white", 0, "bayer", pixel_size=4, bayer_size="2"),
     asc("black_white", 100, glyph_match="shape", charset="quadrants"),
     px("black_white", 120, pixel_mode="average", cleanup=0, simplify=0.2, method="bayer",
        bayer_size="2"))
look("Colour ASCII", "Every character takes the picture's own colour.",
     bm("adaptive_kmeans", 0, "bayer", pixel_size=3, palette_size=16, color_mode="palette"),
     asc("ink_paper", 120, color_mode="channels", color_levels=4, color_boost=0.5),
     px("adaptive_kmeans", 200, palette_size=32, simplify=0.3))
look("ASCII line art (edges)", "Outlines drawn with | / - \\ characters over a light ramp.",
     bm("black_white", 0, "threshold", pixel_size=2, local_contrast=1.0, contrast=1.3),
     asc("black_white", 140, polarity="dark_on_light", edge_strength=0.8, charset="simple"),
     px("black_white", 240, outline="colour", outline_color="#000000", simplify=0.6,
        cleanup=2, palette_size=3))
look("Binary (0 and 1)", "Pictures made of zeros and ones in green.",
     bm("green_phosphor", 320, bayer_size="4"),
     asc("green_phosphor", 150, charset="binary"),
     px("green_phosphor", 200))
look("Typewriter", "Dark letters on cream paper, like a typewritten picture.",
     bm("newspaper", 0, "bayer", pixel_size=2, bayer_size="4"),
     asc("newspaper", 100, charset="letters", polarity="dark_on_light", font_bold=True),
     px("newspaper", 200))

LOOK_NAMES = [l["name"] for l in LOOKS]
LOOK_BY_NAME = {l["name"]: l for l in LOOKS}


# --------------------------------------------------------------------------
# building the three JSON outputs
# --------------------------------------------------------------------------
def baseline(node):
    """Default value of every look-defining widget of a node."""
    return {k: v for k, v in defaults(ALL_SPECS[node]).items()
            if SPEC_MAPS[node][k].promptable and k not in KEEP
            and k not in ("text_frame",)}


def apply_scale(node, d, scale):
    """scale > 1 = chunkier (bigger pixels, fewer characters), < 1 = finer."""
    if abs(scale - 1.0) < 1e-6:
        return d
    d = dict(d)
    if node in ("bitmap", "pixel_art"):
        if d.get("target_width", 0):
            d["target_width"] = max(1, round(d["target_width"] / scale))
        else:
            d["pixel_size"] = max(1, round(d.get("pixel_size", 3 if node == "bitmap" else 4) * scale))
        if "halftone_cell" in d:
            d["halftone_cell"] = max(2, round(d["halftone_cell"] * scale))
        elif node == "bitmap" and d.get("method") in ("halftone_dots", "halftone_lines"):
            d["halftone_cell"] = max(2, round(6 * scale))
    else:
        d["columns"] = max(8, round(d.get("columns", 120) / scale))
    return d


def all_looks():
    """-> (built-in looks + your own looks, list of problems found in your files)."""
    user, problems = userlooks.scan_cached(LOOK_BY_NAME)
    return LOOKS + user, problems


def look_names():
    return [l["name"] for l in all_looks()[0]]


def build(look_name, scale=1.0, tweaks=None):
    """-> (dict node -> json string, info text). tweaks: dict applied last to
    every node that has the widget (unknown names are reported, not an error)."""
    looks, file_problems = all_looks()
    lk = next((l for l in looks if l["name"] == look_name), None)
    if lk is None:
        return {n: "{}" for n in NODES}, ("Unknown look: %s\n(If you just added a look file, "
                                          "press R in ComfyUI to refresh the list.)" % look_name)
    tweaks = tweaks or {}
    out, notes = {}, []
    used = set()
    for node in NODES:
        d = baseline(node)
        d.update(lk[node])
        d = apply_scale(node, d, float(scale))
        for k, raw in tweaks.items():
            spec = SPEC_MAPS[node].get(k)
            if spec is None or not spec.promptable:
                continue
            ok, val = coerce(spec, raw)
            if ok:
                d[k] = val
                used.add(k)
        out[node] = json.dumps(d, indent=2, ensure_ascii=False)
    lines = ["Look: " + lk["name"], lk["desc"]]
    if abs(float(scale) - 1.0) > 1e-6:
        lines.append("scale %.2g: %s" % (float(scale), "chunkier" if scale > 1 else "finer"))
    for k in tweaks:
        if k in used:
            lines.append("tweak applied: %s=%s" % (k, tweaks[k]))
        else:
            lines.append("tweak ignored (no such widget, or not settable): %s" % k)
    for pr in lk.get("problems", []):
        lines.append("look file: " + pr)
    other = [p for p in file_problems if p not in lk.get("problems", [])]
    if other:
        lines.append("%d problem(s) in other look files (first: %s)" % (len(other), other[0]))
    lines.append("Connect bitmap -> ApoDesign Bitmap, ascii -> ApoDesign Ascii, "
                 "pixel_art -> ApoDesign Pixel Art (style_json inputs).")
    return out, "\n".join(lines + notes)
