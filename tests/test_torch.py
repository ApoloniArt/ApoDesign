"""Tests for the torch engine. Needs torch only (no ComfyUI).

Run with any Python that has torch, for example ComfyUI's embedded Python:
    python_embeded\\python.exe ApoDesign\\tests\\test_torch.py
"""
import os
import sys

import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import ascii_specs
from core import palettes as P
from core.common import pick_alpha
from core import dither as D
from core.ascii_engine import cell_geometry
from core.ascii_engine import render as ascii_render
from core.bitmap_engine import render
from core import pixel_specs
from core.pixel_engine import render as pixel_render, kuwahara, cleanup_indices
from core.bitmap_specs import SPECS
from core.params import defaults
from core.palettes import PRESETS


def _values(**over):
    v = defaults(SPECS)      # the exact defaults the node ships with
    v.update(over)
    return v


def _sequential(x, kernel, L, strength):
    B, C, h, w = x.shape
    buf = x.clone().double()
    out = torch.zeros_like(buf)
    for y in range(h):
        for xx in range(w):
            old = buf[:, :, y, xx].clone()
            new = (old.clamp(0, 1) * (L - 1)).round() / (L - 1)
            out[:, :, y, xx] = new
            err = old - new
            for dx, dy, wt in kernel:
                X, Y = xx + dx, y + dy
                if 0 <= X < w and 0 <= Y < h:
                    buf[:, :, Y, X] += err * wt * strength
    return out


def test_bayer():
    m = (D.bayer_matrix(4) * 16 - 0.5).round().long().tolist()
    assert m == [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def test_blue_noise():
    t = D.blue_noise_tile()
    assert t.shape == (64, 64)
    ranks = (t.flatten() * 4096 - 0.5).round().long().sort().values
    assert torch.equal(ranks, torch.arange(4096))
    assert abs(float((t < 0.3).float().mean()) - 0.3) < 0.01


def test_wavefront_matches_sequential():
    torch.manual_seed(0)
    for name, ker in D.KERNELS.items():
        x = torch.rand(2, 3, 11, 17)
        for L, s in ((2, 1.0), (4, 0.7)):
            got, _ = D.error_diffusion(x, D.level_quantizer(L), name, s)
            ref = _sequential(x, ker, L, s)
            assert torch.allclose(got.double(), ref, atol=1e-5), (name, L, s)


def test_halftone_coverage():
    for method in ("halftone_dots", "halftone_lines"):
        T = D.make_threshold(method, 128, 128, torch.device("cpu"), cell=8.0, angle=30.0)
        grey = torch.full((1, 1, 128, 128), 0.7)
        bright = D.ordered_levels(grey, 2, T[:1]).float().mean().item()
        assert abs(bright - 0.7) < 0.03, (method, bright)


def test_render_all_methods_and_modes():
    torch.manual_seed(1)
    img = torch.rand(3, 61, 83, 3)
    for method in ("bayer", "blue_noise", "halftone_dots", "halftone_lines",
                   "threshold", "floyd_steinberg", "atkinson", "stucki"):
        for mode in ("tonal", "palette", "channels"):
            v = _values(method=method, color_mode=mode, pixel_size=4,
                        palette_preset="gameboy", halftone_cell=4)
            out = render(img, None, v, torch.device("cpu"))
            assert out["image"].shape == (3, 61, 83, 3), (method, mode)
            assert out["lowres"].shape == (3, 16, 21, 3)
            assert out["mask"].shape == (3, 61, 83)
            assert 0.0 <= float(out["image"].min()) and float(out["image"].max()) <= 1.0


def test_tonal_uses_only_palette_colours():
    img = torch.rand(1, 40, 40, 3)
    v = _values(method="bayer", palette_preset="gameboy", pixel_size=2)
    out = render(img, None, v, torch.device("cpu"))
    got = {tuple(int(round(c * 255)) for c in px) for px in out["image"].reshape(-1, 3).tolist()}
    want = {tuple(int(round(c * 255)) for c in __import__("core.palettes", fromlist=["x"]).hex_to_rgb(h))
            for h in PRESETS["gameboy"]}
    assert got <= want, got - want


def test_ordered_is_batch_and_video_stable():
    torch.manual_seed(2)
    frame = torch.rand(1, 50, 50, 3)
    batch = frame.repeat(4, 1, 1, 1)
    for method in ("bayer", "blue_noise", "halftone_dots"):
        v = _values(method=method, pixel_size=3)
        a = render(batch, None, v, torch.device("cpu"))["image"]
        b = render(frame, None, v, torch.device("cpu"))["image"]
        assert all(torch.equal(a[i], b[0]) for i in range(4)), method


def test_target_width_non_integer_scale():
    img = torch.rand(1, 100, 150, 3)
    v = _values(target_width=40, method="bayer")
    out = render(img, None, v, torch.device("cpu"))
    assert out["lowres"].shape == (1, 27, 40, 3)         # round(40 * 100/150)
    assert out["image"].shape == (1, 100, 150, 3)


def test_mix_modes_and_mask():
    img = torch.rand(2, 48, 48, 3)
    mask = torch.zeros(2, 48, 48)
    mask[:, :, 24:] = 1.0
    for mode in ("global", "highlights", "shadows", "saturation", "edges_mono",
                 "edges_colour", "centre", "mask"):
        v = _values(color_mode="channels", color_mix=0.5, mix_mode=mode, pixel_size=2)
        out = render(img, mask, v, torch.device("cpu"))
        assert out["image"].shape == (2, 48, 48, 3), mode
    # mask mode: left half (mask 0) must be pure mono (R == G == B)
    v = _values(color_mode="channels", color_mix=1.0, mix_mode="mask", pixel_size=2)
    im = render(img, mask, v, torch.device("cpu"))["image"]
    left = im[:, :, :20]
    assert torch.allclose(left[..., 0], left[..., 1]) and torch.allclose(left[..., 1], left[..., 2])


def test_adaptive_palette_is_shared_across_batch():
    img = torch.rand(4, 32, 32, 3)
    v = _values(palette_preset="adaptive_kmeans", palette_size=5, color_mode="palette")
    out = render(img, None, v, torch.device("cpu"))
    assert len(out["palette"].split(",")) == 5


def test_bitmap_chunks_mask_and_memory_options():
    """10 frames crosses the 8-frame chunk boundary. A single mask must apply
    to every frame, and turning the ink mask off must not change the picture."""
    torch.manual_seed(3)
    cpu = torch.device("cpu")
    img = torch.rand(10, 40, 56, 3)
    mask = torch.zeros(1, 40, 56)
    mask[:, :, 28:] = 1.0
    v = _values(method="bayer", color_mode="channels", color_mix=1.0,
                mix_mode="mask", pixel_size=2)
    full = render(img, mask, v, cpu)
    for k in (0, 7, 8, 9):                       # frames either side of the chunk edge
        one = render(img[k:k + 1], mask, v, cpu)["image"]
        assert torch.equal(full["image"][k], one[0]), k
    lean = render(img, mask, v, cpu, want_mask=False)
    assert torch.equal(lean["image"], full["image"])
    assert lean["mask"].shape == full["mask"].shape == (10, 40, 56)
    assert float(lean["mask"].abs().max()) == 0.0 and float(full["mask"].max()) > 0.0


# --------------------------------------------------------------------------
# Ascii
# --------------------------------------------------------------------------
def _avalues(**over):
    v = defaults(ascii_specs.SPECS)
    v.update(over)
    return v


CPU = torch.device("cpu")


def test_ascii_all_modes():
    torch.manual_seed(4)
    img = torch.rand(2, 61, 83, 3)
    for match, charset in (("ramp", "standard"), ("ramp", "blocks"), ("shape", "standard"),
                           ("shape", "quadrants"), ("braille", "standard")):
        for method in ("none", "bayer", "blue_noise", "floyd_steinberg"):
            for mode in ("tonal", "palette", "channels"):
                for scale in (1, 2):
                    v = _avalues(glyph_match=match, charset=charset, method=method,
                                 color_mode=mode, columns=20, output_scale=scale,
                                 palette_preset="gameboy", edge_strength=0.5)
                    out = ascii_render(img, None, v, CPU)
                    tag = (match, charset, method, mode, scale)
                    assert out["image"].shape == (2, 61 * scale, 83 * scale, 3), tag
                    assert out["mask"].shape == (2, 61 * scale, 83 * scale), tag
                    assert 0.0 <= float(out["image"].min()) and float(out["image"].max()) <= 1.0, tag
                    cw0, ch0, c_, r_ = cell_geometry(61, 83, 20, 2.0)
                    assert len(out["text"].split("\n")) == r_, tag
    v = _avalues(columns=20, glyph_match="shape", background="tint", color_mode="channels",
                 mix_mode="highlights", color_mix=0.5, glyph_style="crisp", font_bold=True)
    assert ascii_render(img, torch.rand(2, 61, 83), v, CPU)["image"].shape == (2, 61, 83, 3)


def test_ascii_text_order():
    """text_order fills the inked cells with the text, in reading order."""
    phrase = "LEST WE FORGET"
    bright = torch.ones(1, 80, 160, 3)
    for charset in ("standard", "letters", "classic"):
        for match in ("ramp", "shape"):
            v = _avalues(columns=40, charset=charset, glyph_match=match,
                         text_order="in_order", order_text=phrase)
            out = ascii_render(bright, None, v, CPU)
            lines = out["text"].split("\n")
            flow = " ".join(ln for ln in lines)
            letters = [c for c in flow if c != " "]
            want = list(phrase.replace(" ", "")) * (len(letters) // 12 + 1)
            assert letters == want[:len(letters)], (charset, match)
            assert lines[0].startswith("LEST WE FORGET LEST"), (charset, match, lines[0])
    v = _avalues(columns=40, text_order="in_order_per_row", order_text=phrase)
    lines = ascii_render(bright, None, v, CPU)["text"].split("\n")
    assert all(ln.startswith("LEST WE FORGET LEST") for ln in lines)
    # a black picture inks nothing, so no letters at all
    v = _avalues(columns=40, text_order="in_order", order_text=phrase)
    assert ascii_render(torch.zeros(1, 80, 160, 3), None, v, CPU)["text"].strip() == ""
    # a transparent cell never uses up a letter
    al = torch.zeros(1, 80, 160)
    al[:, :, :80] = 1.0
    v = _avalues(columns=40, text_order="in_order_per_row", order_text=phrase)
    lines = ascii_render(bright, None, v, CPU, alpha=al)["text"].split("\n")
    assert all(ln.strip() == "" or ln.lstrip().startswith("LEST") for ln in lines)
    assert any(ln.startswith(" " * 20 + "LEST") for ln in lines)
    # empty text and braille are ignored, never an error
    for over in ({"order_text": "  "}, {"glyph_match": "braille"}):
        v = _avalues(columns=20, text_order="in_order", **over)
        out = ascii_render(bright, None, v, CPU)
        assert out["image"].shape == (1, 80, 160, 3) and out["notes"]
    # default off: the same picture as before the option existed
    v0 = _avalues(columns=40)
    assert v0["text_order"] == "off"


def test_ascii_reproduces_the_picture():
    """A left-to-right gradient must come out brighter on the right, for both
    polarities, and inverted when asked to invert."""
    g = torch.linspace(0, 1, 192).view(1, 1, 192, 1).expand(1, 64, 192, 3).contiguous()
    for pol in ("light_on_dark", "dark_on_light"):
        for charset in ("classic", "standard", "blocks"):
            v = _avalues(columns=48, charset=charset, polarity=pol)
            im = ascii_render(g, None, v, CPU)["image"]
            assert float(im[:, :, :48].mean()) < float(im[:, :, 144:].mean()), (pol, charset)
            v["invert"] = True
            im = ascii_render(g, None, v, CPU)["image"]
            assert float(im[:, :, :48].mean()) > float(im[:, :, 144:].mean()), (pol, charset)


def test_ascii_shape_mode_reproduces_quadrants_exactly():
    """Cells drawn as quadrant patterns must come back pixel-for-pixel when
    shape matching is allowed to use the quadrant characters."""
    torch.manual_seed(5)
    rows, cols = 4, 10
    bits = torch.randint(0, 2, (rows, cols, 4))
    img = torch.zeros(1, rows * 16, cols * 8, 3)
    for r in range(rows):
        for c in range(cols):
            for q, (dy, dx) in enumerate([(0, 0), (0, 4), (8, 0), (8, 4)]):
                if bits[r, c, q]:
                    img[0, r * 16 + dy:r * 16 + dy + 8, c * 8 + dx:c * 8 + dx + 4, :] = 1.0
    v = _avalues(glyph_match="shape", charset="quadrants", columns=cols, cell_aspect=2.0)
    out = ascii_render(img, None, v, CPU)
    assert torch.allclose(out["image"], img, atol=1e-4)


def test_ascii_braille_dots_match_the_picture():
    torch.manual_seed(6)
    rows, cols = 4, 10
    dots = torch.randint(0, 2, (rows * 4, cols * 2))              # one value per dot
    img = dots.float().repeat_interleave(4, 0).repeat_interleave(4, 1)
    img = img.unsqueeze(0).unsqueeze(-1).expand(1, rows * 16, cols * 8, 3).contiguous()
    v = _avalues(glyph_match="braille", columns=cols, cell_aspect=2.0)
    out = ascii_render(img, None, v, CPU)
    weights = [[1, 8], [2, 16], [4, 32], [64, 128]]
    want = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            code = sum(weights[y][x] for y in range(4) for x in range(2)
                       if dots[r * 4 + y, c * 2 + x])
            line += chr(0x2800 + code)
        want.append(line)
    assert out["text"].split("\n") == want


def test_ascii_ordered_is_batch_and_video_stable():
    torch.manual_seed(7)
    frame = torch.rand(1, 50, 70, 3)
    batch = frame.repeat(10, 1, 1, 1)                             # crosses the chunk edge
    for match, method in (("ramp", "bayer"), ("ramp", "blue_noise"), ("braille", "bayer"),
                          ("shape", "none")):
        v = _avalues(glyph_match=match, method=method, columns=24, color_mode="palette",
                     palette_preset="pico8")
        a = ascii_render(batch, None, v, CPU)["image"]
        b = ascii_render(frame, None, v, CPU)["image"]
        same = sum(float((a[i] == b[0]).float().mean()) for i in range(10)) / 10.0
        assert same > 0.995, (match, method, same)


def test_ascii_text_output():
    img = torch.rand(3, 40, 60, 3)
    v = _avalues(columns=15, text_frame=1)
    one = ascii_render(img, None, v, CPU)["text"]
    v["text_frame"] = -1
    every = ascii_render(img, None, v, CPU)["text"]
    assert every.split("\n\f\n")[1] == one and len(every.split("\n\f\n")) == 3
    v["text_frame"] = 99                                          # past the end: last frame
    assert ascii_render(img, None, v, CPU)["text"] == every.split("\n\f\n")[2]


def test_ascii_edges_follow_outlines():
    img = torch.zeros(1, 64, 192, 3)
    img[:, :, 96:] = 1.0                                          # a vertical edge
    v = _avalues(columns=48, charset="simple")
    assert "|" not in ascii_render(img, None, v, CPU)["text"]
    v["edge_strength"] = 1.0
    assert "|" in ascii_render(img, None, v, CPU)["text"]
    img = torch.zeros(1, 192, 64, 3)
    img[:, 96:] = 1.0                                             # a horizontal edge
    v = _avalues(columns=16, charset="simple")
    assert "-" not in ascii_render(img, None, v, CPU)["text"]
    v["edge_strength"] = 1.0
    assert "-" in ascii_render(img, None, v, CPU)["text"]


def test_ascii_glyph_mask_option():
    img = torch.rand(2, 48, 64, 3)
    v = _avalues(columns=16)
    off = ascii_render(img, None, v, CPU)
    assert off["mask"].shape == (2, 48, 64) and float(off["mask"].abs().max()) == 0.0
    v["glyph_mask_output"] = True
    on = ascii_render(img, None, v, CPU)
    assert float(on["mask"].max()) > 0.0 and torch.equal(on["image"], off["image"])


def test_ascii_colour_modes_use_expected_colours():
    torch.manual_seed(8)
    img = torch.rand(1, 48, 64, 3)
    v = _avalues(columns=16, glyph_match="shape", charset="quadrants",
                 palette_preset="gameboy", color_mode="tonal")
    px = ascii_render(img, None, v, CPU)["image"].reshape(-1, 3).tolist()
    got = {tuple(int(round(c * 255)) for c in p) for p in px}
    assert got == {(0x0f, 0x38, 0x0f), (0x9b, 0xbc, 0x0f)}        # darkest page, lightest ink
    v["polarity"] = "dark_on_light"
    px = ascii_render(img, None, v, CPU)["image"].reshape(-1, 3).tolist()
    assert {tuple(int(round(c * 255)) for c in p) for p in px} == got


# --------------------------------------------------------------------------
# Pixel Art
# --------------------------------------------------------------------------
def _pvalues(**over):
    v = defaults(pixel_specs.SPECS)
    v.update(over)
    return v


def _hexset(img):
    return {tuple(int(round(c * 255)) for c in p) for p in img.reshape(-1, 3).tolist()}


def test_pixel_all_modes():
    torch.manual_seed(9)
    img = torch.rand(2, 61, 83, 3)
    for mode in ("dominant", "average", "nearest"):
        for preset in ("adaptive_kmeans", "none", "gameboy", "pico8"):
            for outline in ("none", "dark", "colour"):
                for simplify in (0.0, 0.7):
                    v = _pvalues(pixel_mode=mode, palette_preset=preset, outline=outline,
                                 simplify=simplify, pixel_size=4, cleanup=2,
                                 match="tone" if preset == "gameboy" else "colour")
                    out = pixel_render(img, v, CPU)
                    tag = (mode, preset, outline, simplify)
                    assert out["image"].shape == (2, 61, 83, 3), tag
                    assert out["lowres"].shape == (2, 16, 21, 3), tag
                    assert 0.0 <= float(out["image"].min()) and float(out["image"].max()) <= 1.0, tag
    for method in ("bayer", "blue_noise", "floyd_steinberg"):
        v = _pvalues(pixel_mode="average", method=method, palette_preset="c64", cleanup=0)
        assert pixel_render(img, v, CPU)["image"].shape == (2, 61, 83, 3)
    v = _pvalues(target_width=30, output_scale=2)
    out = pixel_render(img, v, CPU)
    assert out["lowres"].shape == (2, 22, 30, 3) and out["image"].shape == (2, 122, 166, 3)


def test_pixel_output_uses_only_palette_colours():
    torch.manual_seed(10)
    img = torch.rand(1, 48, 48, 3)
    v = _pvalues(palette_preset="gameboy", match="tone", pixel_size=3)
    assert _hexset(pixel_render(img, v, CPU)["image"]) <= {(0x0f, 0x38, 0x0f), (0x30, 0x62, 0x30),
                                                          (0x8b, 0xac, 0x0f), (0x9b, 0xbc, 0x0f)}
    v = _pvalues(palette_preset="adaptive_kmeans", palette_size=5, pixel_size=3)
    out = pixel_render(img, v, CPU)
    assert len(out["palette"].split(",")) == 5 and len(_hexset(out["image"])) <= 5
    v = _pvalues(palette_preset="none", custom_palette="#ff0000,#0000ff", pixel_size=3)
    assert _hexset(pixel_render(img, v, CPU)["image"]) <= {(255, 0, 0), (0, 0, 255)}


def test_pixel_dominant_beats_average():
    """3 of the 4 samples in a block are red: dominant must say red."""
    img = torch.zeros(1, 4, 4, 3)
    img[..., 0] = 1.0                                   # all red
    img[:, 1::2, 1::2] = torch.tensor([0.0, 0.0, 1.0])  # one blue sample per 2x2 block
    v = _pvalues(pixel_size=2, palette_preset="none", custom_palette="#ff0000,#0000ff",
                 pixel_mode="dominant", cleanup=0)
    out = pixel_render(img, v, CPU)["lowres"]
    assert _hexset(out) == {(255, 0, 0)}


def test_pixel_cleanup_removes_stray_pixels():
    img = torch.zeros(1, 9, 9, 3)
    img[:, 4, 4] = 1.0                                  # a lone white pixel on black
    base = dict(pixel_size=1, palette_preset="none", custom_palette="#000000,#ffffff",
                pixel_mode="average", match="tone")
    kept = pixel_render(img, _pvalues(cleanup=0, **base), CPU)["lowres"]
    gone = pixel_render(img, _pvalues(cleanup=1, **base), CPU)["lowres"]
    assert float(kept.max()) == 1.0 and float(gone.max()) == 0.0
    idx = torch.zeros(1, 7, 7, dtype=torch.long)
    idx[0, 3, 3] = 1
    assert int(cleanup_indices(idx, 2, 1).sum()) == 0
    idx[0, 3, 2:5] = 1                                  # a 3-pixel line is not stray
    assert int(cleanup_indices(idx, 2, 1).sum()) == 3


def test_pixel_outline_is_on_the_dark_side_of_edges():
    img = torch.zeros(1, 8, 16, 3)
    img[:, :, 8:] = 1.0                                 # dark left, light right
    v = _pvalues(pixel_size=1, palette_preset="none", custom_palette="#000000,#ffffff",
                 pixel_mode="average", match="tone", cleanup=0, outline="colour",
                 outline_color="#ff0000")
    low = pixel_render(img, v, CPU)["lowres"]
    assert torch.allclose(low[0, :, 7], torch.tensor([1.0, 0.0, 0.0]))      # dark side of the edge
    assert torch.allclose(low[0, :, 8], torch.ones(3))                       # light side untouched
    assert torch.allclose(low[0, :, 3], torch.zeros(3))                      # flat areas untouched


def test_pixel_simplify_flattens_noise_but_keeps_edges():
    torch.manual_seed(11)
    img = torch.full((1, 64, 64, 3), 0.25)
    img[:, :, 32:] = 0.75
    noisy = (img + 0.08 * torch.randn_like(img)).clamp(0, 1)
    base = dict(pixel_size=2, palette_preset="none", pixel_mode="average", cleanup=0)
    rough = pixel_render(noisy, _pvalues(simplify=0.0, **base), CPU)["lowres"]
    flat = pixel_render(noisy, _pvalues(simplify=1.0, **base), CPU)["lowres"]
    assert float(flat[:, :, :12].std()) < float(rough[:, :, :12].std())
    assert float(flat[:, :, 20:].mean()) - float(flat[:, :, :12].mean()) > 0.35   # edge survives
    k = kuwahara(noisy.permute(0, 3, 1, 2), 2)
    assert k.shape == (1, 3, 64, 64)


def test_pixel_video_is_steady_and_chunk_safe():
    torch.manual_seed(12)
    frame = torch.rand(1, 40, 56, 3)
    batch = frame.repeat(10, 1, 1, 1)
    for mode in ("dominant", "average", "nearest"):
        v = _pvalues(pixel_mode=mode, palette_preset="none", custom_palette="#102040,#a0c0e0,#ffe0a0",
                     method="bayer" if mode != "dominant" else "none", cleanup=0)
        a = pixel_render(batch, v, CPU)["image"]
        b = pixel_render(frame, v, CPU)["image"]
        assert all(torch.equal(a[i], b[0]) for i in range(10)), mode
    v = _pvalues(palette_preset="adaptive_kmeans", palette_size=6)       # palette shared by all frames
    out = pixel_render(torch.rand(20, 32, 32, 3), v, CPU)
    assert len(out["palette"].split(",")) == 6 and len(_hexset(out["image"])) <= 6


# --------------------------------------------------------------------------
# Transparency
# --------------------------------------------------------------------------
MAGENTA = (1.0, 0.0, 1.0)


def _alpha_case(B=2):
    """Random picture whose right half is transparent, with junk magenta hidden
    under it. Cell edges (4 px wide, 8 px tall) line up with the split."""
    torch.manual_seed(13)
    img = torch.rand(B, 48, 64, 3)
    mask = torch.zeros(B, 48, 64)
    mask[:, :, 32:] = 1.0                                  # white = transparent
    img[:, :, 32:] = torch.tensor(MAGENTA)
    return img, mask


def _no_magenta(palette_string, tol=0.2):
    for hx in palette_string.split(","):
        c = P.hex_to_rgb(hx)
        assert sum((a - b) ** 2 for a, b in zip(c, MAGENTA)) ** 0.5 > tol, palette_string


def test_pick_alpha():
    m = torch.zeros(1, 8, 8)
    assert pick_alpha(m, "rgba") == (None, False)                 # fully opaque mask: ignored
    m[0, 0, 0] = 1.0
    assert pick_alpha(m, "rgba") == (m, True)
    assert pick_alpha(m, "separate") == (m, False)
    assert pick_alpha(m, "off") == (None, False)
    assert pick_alpha(m, "rgba", "mask") == (None, False)         # mix_mode = mask: colour region
    assert pick_alpha(None, "rgba") == (None, False)


def test_pick_alpha_invert():
    # a loader that outputs white = OPAQUE: invert turns it into white = transparent
    m = torch.ones(1, 8, 8)
    m[0, :, 4:] = 0.0
    a, rgba = pick_alpha(m, "rgba", None, True)
    assert rgba and float(a[0, :, :4].max()) == 0.0 and float(a[0, :, 4:].min()) == 1.0
    assert pick_alpha(torch.ones(1, 8, 8), "rgba", None, True) == (None, False)   # all opaque after flip
    assert pick_alpha(m, "rgba", "mask", True) == (None, False)                  # colour-region mode


def test_invert_mask_fixes_a_flipped_loader():
    img, mask = _alpha_case()
    flipped = 1.0 - mask
    v = _values(pixel_size=4, palette_preset="adaptive_kmeans", palette_size=3, method="bayer")
    a, rgba = pick_alpha(flipped, "rgba", None, True)
    out = render(img, None, v, CPU, True, a, rgba)
    _check_alpha_outputs(out, 2, 48, 64, True)



def _check_alpha_outputs(out, B, H, W, rgba):
    img, al = out["image"], out["alpha"]
    if rgba:
        assert img.shape == (B, H, W, 4)
        assert float(img[:, :, :32, 3].min()) == 1.0 and float(img[:, :, 32:, 3].max()) == 0.0
    else:
        assert img.shape == (B, H, W, 3)
    # the alpha output is filled in both modes, so Join Image with Alpha works
    assert al.shape == (B, H, W)
    assert float(al[:, :, :32].max()) == 0.0 and float(al[:, :, 32:].min()) == 1.0
    assert float(img[:, :, 32:, :3].abs().max()) == 0.0               # transparent = black, no magenta


def test_bitmap_transparency():
    img, mask = _alpha_case()
    for rgba in (True, False):
        for mode in ("tonal", "palette", "channels"):
            v = _values(pixel_size=4, palette_preset="adaptive_kmeans", palette_size=3,
                        color_mode=mode, method="bayer")
            out = render(img, None, v, CPU, True, mask, rgba)
            _check_alpha_outputs(out, 2, 48, 64, rgba)
            assert float(out["mask"][:, :, 32:].max()) == 0.0         # no ink where transparent
            _no_magenta(out["palette"])
    plain = render(img, None, _values(pixel_size=4), CPU)
    assert plain["image"].shape == (2, 48, 64, 3) and float(plain["alpha"].abs().max()) == 0.0


def test_ascii_transparency():
    img, mask = _alpha_case()
    for match in ("ramp", "shape", "braille"):
        for rgba in (True, False):
            v = _avalues(glyph_match=match, columns=16, palette_preset="adaptive_kmeans",
                         palette_size=3, color_mode="channels", glyph_mask_output=True)
            out = ascii_render(img, None, v, CPU, mask, rgba)
            _check_alpha_outputs(out, 2, 48, 64, rgba)
            assert float(out["mask"][:, :, 32:].max()) == 0.0
            _no_magenta(out["palette"])
            lines = out["text"].split("\n")
            if match == "braille":
                assert all(ln[8:] == "\u2800" * 8 for ln in lines)
            else:
                assert all(len(ln) <= 8 for ln in lines)               # right half is blank


def test_pixel_transparency():
    img, mask = _alpha_case()
    for mode in ("dominant", "average", "nearest"):
        for rgba in (True, False):
            v = _pvalues(pixel_mode=mode, pixel_size=4, palette_preset="adaptive_kmeans",
                         palette_size=3, simplify=0.5 if rgba else 0.0)
            out = pixel_render(img, v, CPU, mask, rgba)
            _check_alpha_outputs(out, 2, 48, 64, rgba)
            _no_magenta(out["palette"])


def test_pixel_transparency_only_opaque_samples_vote():
    """A block with 3 opaque red samples and 1 transparent (junk magenta)
    comes out red and opaque; a block with 1 opaque sample out of 4 is transparent."""
    img = torch.zeros(1, 4, 4, 3)
    img[:] = torch.tensor(MAGENTA)
    mask = torch.ones(1, 4, 4)
    for y, x in ((0, 0), (0, 1), (1, 0), (0, 2)):
        img[0, y, x] = torch.tensor([1.0, 0.0, 0.0])
        mask[0, y, x] = 0.0
    for mode in ("dominant", "average"):
        v = _pvalues(pixel_size=2, palette_preset="none", custom_palette="#ff0000,#0000ff",
                     pixel_mode=mode, cleanup=0)
        out = pixel_render(img, v, CPU, mask, True)["image"]            # (1,4,4,4)
        assert torch.allclose(out[0, :2, :2, 0], torch.ones(2, 2)) and float(out[0, :2, :2, 1:3].abs().max()) == 0.0
        assert float(out[0, :2, :2, 3].min()) == 1.0                    # opaque red block
        assert float(out[0, :2, 2:, 3].max()) == 0.0                    # 1 of 4 opaque: transparent
        assert float(out[0, 2:, :, 3].max()) == 0.0


def test_pixel_outline_traces_the_silhouette():
    img = torch.full((1, 32, 64, 3), 0.5)
    mask = torch.zeros(1, 32, 64)
    mask[:, :, 32:] = 1.0
    v = _pvalues(pixel_size=4, palette_preset="none", pixel_mode="average", cleanup=0,
                 outline="colour", outline_color="#ff0000")
    low = pixel_render(img, v, CPU, mask, True)["lowres"]               # (1,8,16,3)
    assert torch.allclose(low[0, :, 7], torch.tensor([1.0, 0.0, 0.0]))    # last opaque column
    assert torch.allclose(low[0, :, 3], torch.full((8, 3), 0.5))          # inside: untouched
    assert float(low[0, :, 8:].abs().max()) == 0.0                        # transparent: black


def test_transparency_is_chunk_safe():
    img, mask = _alpha_case(B=1)
    batch, bmask = img.repeat(10, 1, 1, 1), mask.repeat(10, 1, 1)
    v = _values(pixel_size=4, method="bayer", palette_preset="pico8")
    a = render(batch, None, v, CPU, True, bmask, True)["image"]
    b = render(img, None, v, CPU, True, mask, True)["image"]
    assert all(torch.equal(a[i], b[0]) for i in range(10))
    one = mask[:1]                                                      # a single mask for the whole batch
    c = ascii_render(batch, None, _avalues(columns=16), CPU, one, True)["image"]
    d = ascii_render(img, None, _avalues(columns=16), CPU, one, True)["image"]
    assert all(torch.equal(c[i], d[0]) for i in range(10))
    e = pixel_render(batch, _pvalues(palette_preset="gameboy", match="tone"), CPU, one, True)["image"]
    f = pixel_render(img, _pvalues(palette_preset="gameboy", match="tone"), CPU, one, True)["image"]
    assert all(torch.equal(e[i], f[0]) for i in range(10))


def test_palette_node():
    import json
    from test_pure import _load_package
    node = _load_package().NODE_CLASS_MAPPINGS["ApoDesign_Palette"]()
    base = dict(mode="preset", preset="gameboy", hex_list="", colours=6, colour_a="#3a7bd5",
                colour_b="#f7efe0", colour_mid="", scheme="analogous", sort="dark_to_light",
                set_colour_modes=True, swatch_height=16)
    text, sw, js = node.run(**base)
    assert text == "#0f380f,#306230,#8bac0f,#9bbc0f" and sw.shape == (1, 16, 64, 3)
    assert json.loads(js) == {"custom_palette": text, "color_mode": "tonal", "match": "tone"}
    _, sw, js = node.run(**{**base, "preset": "pico8"})
    assert json.loads(js)["match"] == "colour" and sw.shape == (1, 16, 256, 3)
    t, sw, _ = node.run(**{**base, "mode": "gradient", "colours": 5})
    assert len(t.split(",")) == 5 and sw.shape[2] == 80
    t, _, _ = node.run(**{**base, "mode": "harmony", "scheme": "triadic"})
    assert 3 <= len(t.split(",")) <= 6
    t, _, _ = node.run(**{**base, "mode": "hex_list", "hex_list": "#000000, #ff0000, bad"})
    assert t == "#000000,#ff0000"
    img = torch.zeros(2, 32, 32, 3)
    img[:, :, 16:] = torch.tensor([1.0, 0.0, 0.0])
    t, _, _ = node.run(**{**base, "mode": "from_image", "colours": 2}, image=img)
    assert len(t.split(",")) == 2
    t, _, _ = node.run(**{**base, "mode": "from_image"})          # no image: safe fallback
    assert t == "#000000,#ffffff"


def test_style_output_drives_a_node():
    """A Style look fed through the real override path changes the right widgets."""
    import json
    from core import styles
    from core.params import apply_overrides
    from core import pixel_specs as PS
    out, _ = styles.build("Game Boy (green)")
    vals = defaults(PS.SPECS)
    vals, applied = apply_overrides(vals, json.loads(out["pixel_art"]), {s.name: s for s in PS.SPECS}, True)
    assert vals["palette_preset"] == "gameboy" and vals["target_width"] == 160 and applied
    img = torch.rand(1, 240, 320, 3)
    res = pixel_render(img, vals, CPU)
    assert res["lowres"].shape[2] == 160 and res["image"].shape[-1] == 3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
