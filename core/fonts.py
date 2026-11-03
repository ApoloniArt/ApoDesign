"""Glyph atlases for ApoDesign Ascii. Needs only numpy and Pillow, both of
which ship with ComfyUI. No torch in here, so it is easy to test on its own.

An atlas is a float32 array (G, cell_h, cell_w) of glyph coverage, 0 = paper,
1 = full ink. Everything is rendered at 4x and averaged down, so glyphs are
properly anti-aliased at any cell size. Block and quadrant characters and the
256 braille patterns are drawn procedurally, so they are always exact and
never depend on which font is installed.
"""
import os

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.normpath(os.path.join(_HERE, "..", "fonts"))
BUILTIN_FILES = {False: "DejaVuSansMono.ttf", True: "DejaVuSansMono-Bold.ttf"}

# widget value -> (regular files, bold files) looked up in the system fonts
SYSTEM_FONTS = {
    "consolas": (["consola.ttf", "Consolas.ttf"], ["consolab.ttf", "Consolas Bold.ttf"]),
    "courier_new": (["cour.ttf", "Courier New.ttf", "CourierNew.ttf"],
                    ["courbd.ttf", "Courier New Bold.ttf"]),
    "lucida_console": (["lucon.ttf"], ["lucon.ttf"]),
}


def _system_dirs():
    dirs = []
    win = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if win:
        dirs.append(os.path.join(win, "Fonts"))
    dirs += ["C:\\Windows\\Fonts", "/Library/Fonts", "/System/Library/Fonts",
             "/System/Library/Fonts/Supplemental", "/usr/share/fonts/truetype",
             "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation"]
    return dirs


def resolve_font(font, bold=False, font_file=""):
    """-> (path or None, note or None). Never raises: falls back to the
    bundled DejaVu Sans Mono, and then to Pillow's own default font."""
    note = None
    if font == "custom_file":
        p = (font_file or "").strip().strip('"').strip("'")
        if p and os.path.isfile(p):
            return p, None
        note = "font_file not found (%r); using the built-in font" % p
    elif font in SYSTEM_FONTS:
        names = SYSTEM_FONTS[font][1 if bold else 0]
        for d in _system_dirs():
            for n in names:
                p = os.path.join(d, n)
                if os.path.isfile(p):
                    return p, None
        note = "font %s not installed; using the built-in font" % font
    p = os.path.join(FONT_DIR, BUILTIN_FILES[bool(bold)])
    if os.path.isfile(p):
        return p, note
    return None, (note or "bundled font missing; using Pillow's default font")


# --------------------------------------------------------------------------
# procedural glyphs
# --------------------------------------------------------------------------
# (upper-left, upper-right, lower-left, lower-right)
QUADRANTS = {
    "\u2598": (1, 0, 0, 0), "\u259d": (0, 1, 0, 0), "\u2596": (0, 0, 1, 0),
    "\u2597": (0, 0, 0, 1), "\u2580": (1, 1, 0, 0), "\u2584": (0, 0, 1, 1),
    "\u258c": (1, 0, 1, 0), "\u2590": (0, 1, 0, 1), "\u259e": (0, 1, 1, 0),
    "\u259a": (1, 0, 0, 1), "\u259b": (1, 1, 1, 0), "\u259c": (1, 1, 0, 1),
    "\u2599": (1, 0, 1, 1), "\u259f": (0, 1, 1, 1), "\u2588": (1, 1, 1, 1),
}
SHADES = {"\u2591": 0.25, "\u2592": 0.5, "\u2593": 0.75}


def procedural_glyph(ch, cw, chh):
    """Coverage (chh, cw) for block / shade / quadrant characters, else None."""
    if ch in SHADES:
        return np.full((chh, cw), SHADES[ch], dtype=np.float32)
    if ch in QUADRANTS:
        ul, ur, ll, lr = QUADRANTS[ch]
        left = ((np.arange(cw) + 0.5) / cw) < 0.5
        top = ((np.arange(chh) + 0.5) / chh) < 0.5
        out = np.zeros((chh, cw), dtype=np.float32)
        out[np.ix_(top, left)] = ul
        out[np.ix_(top, ~left)] = ur
        out[np.ix_(~top, left)] = ll
        out[np.ix_(~top, ~left)] = lr
        return out
    return None


# Unicode braille: bit value of the dot at (row 0..3, column 0..1)
BRAILLE_BIT = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]


def braille_atlas(cw, chh):
    """(256, chh, cw): index i is the glyph chr(0x2800 + i), drawn as round dots."""
    ys = (np.arange(chh, dtype=np.float32) + 0.5)[:, None]
    xs = (np.arange(cw, dtype=np.float32) + 0.5)[None, :]
    radius = 0.4 * min(cw / 2.0, chh / 4.0)
    dots = {}
    for r in range(4):
        for c in range(2):
            cy, cx = (r + 0.5) / 4.0 * chh, (c + 0.5) / 2.0 * cw
            d = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2)
            dots[BRAILLE_BIT[r][c]] = np.clip(radius + 0.5 - d, 0.0, 1.0)
    atlas = np.zeros((256, chh, cw), dtype=np.float32)
    for i in range(256):
        for bit, m in dots.items():
            if i & bit:
                atlas[i] = np.maximum(atlas[i], m)
    return atlas


# --------------------------------------------------------------------------
# font glyphs
# --------------------------------------------------------------------------
SS = 4  # supersampling


class _Renderer:
    """Draws single characters of one font into (chh, cw) coverage arrays."""

    def __init__(self, font_path, cw, chh):
        from PIL import Image, ImageDraw, ImageFont
        self.Image, self.ImageDraw = Image, ImageDraw
        self.cw, self.chh = cw, chh
        self.font = None
        if font_path:
            try:
                ref = ImageFont.truetype(font_path, 100)
                asc, desc = ref.getmetrics()
                size = max(6, int(round(chh * SS * 100.0 / max(1, asc + desc))))
                self.font = ImageFont.truetype(font_path, size)
            except (OSError, ValueError):
                self.font = None
        if self.font is not None:
            self.asc, self.desc = self.font.getmetrics()
            self.adv = max(1, int(round(self.font.getlength("M"))))
            self.canvas = (self.adv, self.asc + self.desc)
        else:                                   # last resort: Pillow's default
            self.font = ImageFont.load_default()
            self.canvas = (cw * SS, chh * SS)
            self.asc = self.desc = None

    def draw(self, ch):
        img = self.Image.new("L", self.canvas, 0)
        d = self.ImageDraw.Draw(img)
        if self.asc is not None:
            d.text((self.canvas[0] / 2.0, self.asc), ch, font=self.font,
                   fill=255, anchor="ms")
        else:
            d.text((0, 0), ch, font=self.font, fill=255)
        return img

    def coverage(self, img):
        img = img.resize((self.cw, self.chh), self.Image.BOX)
        return np.asarray(img, dtype=np.float32) / 255.0


_cache = {}


def get_atlas(chars, font_path, cw, chh, smooth=True):
    """chars: iterable of single characters. Returns (kept_chars, atlas) where
    kept_chars drops characters the font cannot draw and atlas is
    (len(kept), chh, cw) float32 coverage."""
    chars = [c for c in dict.fromkeys(chars) if c and c not in "\r\n\t"]
    key = (tuple(chars), font_path, cw, chh, bool(smooth))
    if key in _cache:
        return _cache[key]

    rend = None
    notdef = None
    kept, rows = [], []
    for ch in chars:
        g = procedural_glyph(ch, cw, chh)
        if g is None and ch == " ":
            g = np.zeros((chh, cw), dtype=np.float32)
        if g is None:
            if rend is None:
                rend = _Renderer(font_path, cw, chh)
                notdef = np.asarray(rend.draw("\uffff"))
            img = rend.draw(ch)
            if ch != " " and np.array_equal(np.asarray(img), notdef):
                continue                        # the font has no such glyph (would draw a box)
            g = rend.coverage(img)
            if not smooth:
                g = (g >= 0.4).astype(np.float32)
        kept.append(ch)
        rows.append(g)
    if not rows:
        kept, rows = [" "], [np.zeros((chh, cw), dtype=np.float32)]
    atlas = np.stack(rows).astype(np.float32)
    if len(_cache) >= 8:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (kept, atlas)
    return kept, atlas
