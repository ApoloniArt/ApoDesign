"""Tests for the glyph atlas code. Needs numpy and Pillow only (no torch).
Run:  python tests/test_fonts.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import fonts

CW, CH = 8, 16


def _builtin():
    path, note = fonts.resolve_font("builtin", False, "")
    assert path and os.path.isfile(path), "bundled font missing: %s" % note
    return path


def test_font_resolution():
    assert _builtin().endswith("DejaVuSansMono.ttf")
    bold, _ = fonts.resolve_font("builtin", True, "")
    assert bold.endswith("DejaVuSansMono-Bold.ttf")
    path, note = fonts.resolve_font("custom_file", False, "no/such/file.ttf")
    assert path and note and "not found" in note          # falls back, never raises
    path, note = fonts.resolve_font("consolas", False, "")
    assert path                                           # installed, or the fallback


def test_atlas_basics():
    kept, atlas = fonts.get_atlas(" .@#", _builtin(), CW, CH, True)
    assert kept == [" ", ".", "@", "#"] and atlas.shape == (4, CH, CW)
    assert atlas.dtype == np.float32 and 0.0 <= atlas.min() and atlas.max() <= 1.0
    dens = atlas.mean(axis=(1, 2))
    assert dens[0] == 0.0 and dens[1] < dens[2] and dens[1] < dens[3]


def test_missing_glyphs_are_dropped():
    kept, _ = fonts.get_atlas("a\u4e2d\u00e9b", _builtin(), CW, CH, True)
    assert "a" in kept and "b" in kept and "\u00e9" in kept
    assert "\u4e2d" not in kept                           # no CJK in this font


def test_crisp_is_binary():
    _, atlas = fonts.get_atlas("@%&", _builtin(), CW, CH, False)
    assert set(np.unique(atlas)) <= {0.0, 1.0}


def test_block_and_quadrant_glyphs_are_exact():
    kept, atlas = fonts.get_atlas(" \u2588\u2598\u2584\u2592", _builtin(), CW, CH, True)
    full, ul, lower, shade = atlas[1], atlas[2], atlas[3], atlas[4]
    assert (full == 1.0).all()
    assert (ul[:CH // 2, :CW // 2] == 1.0).all() and ul.sum() == (CH // 2) * (CW // 2)
    assert (lower[CH // 2:] == 1.0).all() and lower[:CH // 2].sum() == 0.0
    assert np.allclose(shade, 0.5)


def test_braille_atlas():
    a = fonts.braille_atlas(CW, CH)
    assert a.shape == (256, CH, CW) and a[0].sum() == 0.0
    assert a[0xFF].sum() > a[0x01].sum() > 0.0
    # U+2801 is the top-left dot, U+2880 the bottom-right dot
    assert a[0x01][:CH // 2, :CW // 2].sum() == a[0x01].sum()
    assert a[0x80][CH // 2:, CW // 2:].sum() == a[0x80].sum()
    assert np.allclose(a[0xFF], np.max(a[[1, 2, 4, 8, 16, 32, 64, 128]], axis=0))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
