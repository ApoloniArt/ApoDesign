"""Tests that need only the Python standard library.  Run:  python tests/test_pure.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.palettes import (PRESETS, PRESET_ALIASES, hex_to_rgb, parse_palette,
                           rgb_to_hex, sort_by_luma)
from core.params import Spec, apply_overrides, coerce
from core.prompt import parse_style_json, parse_style_prompt
from core.ascii_prompt import parse_ascii_prompt
from core.pixel_prompt import parse_pixel_prompt


def test_palettes():
    assert hex_to_rgb("#fff") == (1.0, 1.0, 1.0)
    assert hex_to_rgb("0f380f") is not None
    assert hex_to_rgb("abc") is None            # bare 3-digit is not a colour
    assert rgb_to_hex(hex_to_rgb("#306230")) == "#306230"
    assert len(parse_palette("#000000, #ffffff bad #abc")) == 3
    assert all(hex_to_rgb(h) for p in PRESETS.values() for h in p)
    assert all(v in PRESETS for v in PRESET_ALIASES.values())
    lum = [sum(c) for c in sort_by_luma(parse_palette("#ffffff,#000000,#808080"))]
    assert lum == sorted(lum)


def test_prompt():
    o, _ = parse_style_prompt("gameboy palette, atkinson dither, 96 wide, high contrast")
    assert o == {"method": "atkinson", "target_width": 96,
                 "palette_preset": "gameboy", "contrast": 1.4}
    o, _ = parse_style_prompt("dark purple on mint, bayer 4")
    assert o["palette_preset"] == "ink_paper" and o["bayer_size"] == "4"
    o, _ = parse_style_prompt("teal and orange, floyd steinberg, 3px")
    assert o["method"] == "floyd_steinberg" and o["pixel_size"] == 3
    assert len(o["custom_palette"].split(",")) == 2
    o, _ = parse_style_prompt("colour in the highlights, atkinson")
    assert o["mix_mode"] == "highlights" and o["color_mode"] == "channels"
    assert parse_style_prompt("")[0] == {}
    assert parse_style_prompt("nothing useful here")[0] == {}
    d, err = parse_style_json('```json\n{"method": "stucki"}\n```')
    assert d == {"method": "stucki"} and err is None
    assert parse_style_json("nope")[1] is not None


def test_params():
    specs = {s.name: s for s in [
        Spec("pixel_size", "int", 3, 1, 128),
        Spec("method", "combo", "bayer", choices=["bayer", "blue_noise"]),
        Spec("invert", "bool", False)]}
    assert coerce(specs["pixel_size"], "500") == (True, 128)
    assert coerce(specs["method"], "Blue Noise") == (True, "blue_noise")
    assert coerce(specs["method"], "nope")[0] is False
    assert coerce(specs["invert"], "yes") == (True, True)
    vals = {"pixel_size": 5, "method": "bayer", "invert": False}
    out, _ = apply_overrides(vals, {"pixel_size": 9, "method": "blue_noise"}, specs, False)
    assert out["pixel_size"] == 5 and out["method"] == "blue_noise"   # only defaults fill
    out, _ = apply_overrides(vals, {"pixel_size": 9}, specs, True)
    assert out["pixel_size"] == 9


def _load_package():
    """Import the whole ApoDesign package (no torch needed to import it)."""
    import importlib.util
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if "ApoDesignPkg" in sys.modules:
        return sys.modules["ApoDesignPkg"]
    spec = importlib.util.spec_from_file_location(
        "ApoDesignPkg", os.path.join(root, "__init__.py"),
        submodule_search_locations=[root])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ApoDesignPkg"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_specs_are_valid():
    from core import ascii_specs, bitmap_specs, pixel_specs
    for specs in (bitmap_specs.SPECS, ascii_specs.SPECS, pixel_specs.SPECS):
        names = [s.name for s in specs]
        assert len(names) == len(set(names)), "duplicate widget names"
        for s in specs:
            if s.kind in ("int", "float"):
                assert s.min <= s.default <= s.max, s.name
            if s.kind == "combo":
                assert s.default in s.choices, s.name
            if s.promptable:
                ok, val = coerce(s, s.default)
                assert ok and val == s.default, s.name
    for cs in ascii_specs.CHARSETS.values():
        assert len(cs) >= 2 and len(set(cs)) == len(cs)


def test_text_order_specs():
    from core import ascii_specs
    sp = ascii_specs.SPEC_BY_NAME
    assert sp["text_order"].default == "off"          # off by default: nothing changes
    assert sp["order_text"].default == "LEST WE FORGET"
    assert 0.0 <= sp["order_threshold"].default <= 1.0
    names = [x.name for x in ascii_specs.SPECS]
    # added at the END so workflows saved before 0.7.5 keep their values in place
    assert names[-3:] == ["text_order", "order_text", "order_threshold"]


def test_nodes_register():
    pkg = _load_package()
    assert set(pkg.NODE_CLASS_MAPPINGS) == {"ApoDesign_Bitmap", "ApoDesign_Ascii", "ApoDesign_PixelArt",
                                            "ApoDesign_Style", "ApoDesign_Palette", "ApoDesign_SaveLook"}
    assert set(pkg.NODE_DISPLAY_NAME_MAPPINGS) == set(pkg.NODE_CLASS_MAPPINGS)
    for name, cls in pkg.NODE_CLASS_MAPPINGS.items():
        it = cls.INPUT_TYPES()
        if name in ("ApoDesign_Style", "ApoDesign_Palette", "ApoDesign_SaveLook"):
            assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES) and hasattr(cls, cls.FUNCTION)
            continue
        assert "image" in it["required"] and "style_json" in it["optional"]
        assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES), name
        assert hasattr(cls, cls.FUNCTION)


def test_ascii_prompt():
    o, _ = parse_ascii_prompt("braille, 160 columns, green phosphor")
    assert o["glyph_match"] == "braille" and o["columns"] == 160
    assert o["palette_preset"] == "green_phosphor"
    o, _ = parse_ascii_prompt("quadrant mosaic, 80 wide")
    assert o["glyph_match"] == "shape" and o["charset"] == "quadrants" and o["columns"] == 80
    o, _ = parse_ascii_prompt("dense characters, edges, bold")
    assert o["charset"] == "standard" and o["edge_strength"] == 0.5 and o["font_bold"] is True
    o, _ = parse_ascii_prompt("dark purple on mint")
    assert o["polarity"] == "dark_on_light" and o["palette_preset"] == "ink_paper"
    o, _ = parse_ascii_prompt("white on black, blue noise")
    assert o["polarity"] == "light_on_dark" and o["method"] == "blue_noise"
    o, _ = parse_ascii_prompt("colour ascii")
    assert o["color_mode"] == "channels"
    o, _ = parse_ascii_prompt("halftone, 3px")
    assert "method" not in o and "pixel_size" not in o
    assert parse_ascii_prompt("")[0] == {}


def test_pixel_prompt():
    o, _ = parse_pixel_prompt("24 colours, outline, 160 wide, painterly")
    assert o["palette_size"] == 24 and o["palette_preset"] == "adaptive_kmeans"
    assert o["outline"] == "dark" and o["target_width"] == 160 and o["simplify"] == 0.5
    o, _ = parse_pixel_prompt("gameboy, no dither, clean, average")
    assert o["palette_preset"] == "gameboy" and o["match"] == "tone"
    assert o["method"] == "none" and o["cleanup"] == 2 and o["pixel_mode"] == "average"
    o, _ = parse_pixel_prompt("halftone, vibrant")
    assert "method" not in o and o["saturation"] == 1.3
    assert parse_pixel_prompt("")[0] == {}


def test_style_looks_are_valid():
    """Every recipe of every look uses real, settable widgets with valid values."""
    from core import styles
    from core.params import coerce
    assert len(styles.LOOKS) >= 40 and len(set(styles.LOOK_NAMES)) == len(styles.LOOKS)
    for lk in styles.LOOKS:
        assert lk["desc"], lk["name"]
        for node in styles.NODES:
            assert lk[node], (lk["name"], node)
            for k, v in lk[node].items():
                spec = styles.SPEC_MAPS[node].get(k)
                assert spec is not None and spec.promptable, (lk["name"], node, k)
                ok, val = coerce(spec, v)
                assert ok, (lk["name"], node, k, v)
                if spec.kind in ("int", "float"):
                    assert float(val) == float(v), (lk["name"], node, k, v, "out of range")
                if spec.kind == "combo":
                    assert val == str(v), (lk["name"], node, k, v)


def test_style_build_scale_and_tweaks():
    import json
    from core import styles
    out, info = styles.build("Game Boy (green)")
    px, bmp, asc_ = (json.loads(out[n]) for n in ("pixel_art", "bitmap", "ascii"))
    assert px["target_width"] == 160 and px["palette_preset"] == "gameboy" and px["match"] == "tone"
    assert bmp["target_width"] == 160 and asc_["palette_preset"] == "gameboy"
    assert "brightness" not in px and "output_scale" not in px     # your own tone widgets stay
    out2, info2 = styles.build("Game Boy (green)", 2.0, {"palette_size": 8, "nonsense": 1})
    assert json.loads(out2["pixel_art"])["target_width"] == 80
    assert json.loads(out2["ascii"])["columns"] == 50
    assert json.loads(out2["pixel_art"])["palette_size"] == 8
    assert "ignored" in info2 and "nonsense" in info2
    out3, _ = styles.build("Newspaper halftone", 2.0)
    assert json.loads(out3["bitmap"])["halftone_cell"] == 12
    assert styles.build("no such look")[0]["bitmap"] == "{}"


def test_style_node_runs_without_torch():
    import json
    pkg = _load_package()
    cls = pkg.NODE_CLASS_MAPPINGS["ApoDesign_Style"]
    b, a, p, info = cls().run(cls.INPUT_TYPES()["required"]["look"][0][3], 1.0, '{"outline": "dark"}')
    assert json.loads(p)["outline"] == "dark" and "outline" not in json.loads(b) and info


def test_palette_tools():
    from core import palette_tools as T
    from core.palettes import hex_to_rgb, luma
    g = T.gradient((0, 0, 0), (1, 1, 1), 5)
    assert len(g) == 5 and g[0] == (0, 0, 0) and g[-1] == (1, 1, 1)
    g3 = T.gradient((0, 0, 0), (1, 1, 1), 5, (1, 0, 0))
    assert g3[2] == (1, 0, 0)
    for scheme in T.HARMONIES:
        cols, text = T.finish(T.harmony(hex_to_rgb("#3a7bd5"), scheme, 7))
        assert 3 <= len(cols) <= 7 and all(hex_to_rgb(h) for h in text.split(","))
        assert [luma(c) for c in cols] == sorted(luma(c) for c in cols)
    mono, _ = T.finish(T.harmony(hex_to_rgb("#3a7bd5"), "monochrome", 6))
    assert T.is_tonal(mono) and not T.is_tonal(T.preset("pico8"))
    assert T.is_tonal(T.preset("gameboy")) and T.is_tonal(T.preset("sepia"))
    _, txt = T.finish([(1, 0, 0), (1, 0, 0), (0, 0, 1)], "light_to_dark")
    assert txt.count(",") == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)


def _tmp_looks():
    import tempfile
    return tempfile.mkdtemp(prefix="apolooks_")


def test_user_looks_read_and_validate():
    import json
    from core import styles, userlooks
    d = _tmp_looks()
    open(os.path.join(d, "a.json"), "w").write(json.dumps({
        "name": "Mine", "extends": "Game Boy (green)", "all": {"palette_preset": "pico8"},
        "pixel_art": {"target_width": 77, "nonsense": 1, "outline": "bad"}}))
    open(os.path.join(d, "b.json"), "w").write("not json at all")
    open(os.path.join(d, "_skip.json"), "w").write(json.dumps({"name": "Skipped"}))
    looks, problems = userlooks.scan(styles.LOOK_BY_NAME, [d])
    assert [l["name"] for l in looks] == [userlooks.PREFIX + "Mine"]
    lk = looks[0]
    assert lk["pixel_art"]["target_width"] == 77 and lk["pixel_art"]["palette_preset"] == "pico8"
    assert lk["bitmap"]["palette_preset"] == "pico8" and lk["ascii"]["columns"] == 100   # inherited
    assert "nonsense" not in lk["pixel_art"] and "outline" not in lk["pixel_art"]
    assert any("nonsense" in p for p in problems) and any("b.json" in p for p in problems)


def test_user_looks_in_style_build():
    import json
    from core import styles, userlooks
    d = _tmp_looks()
    os.environ["APODESIGN_LOOKS"] = d
    try:
        open(os.path.join(d, "x.json"), "w").write(json.dumps(
            {"name": "Zed", "pixel_art": {"palette_size": 5, "palette_preset": "adaptive_kmeans"}}))
        zed = userlooks.PREFIX + os.path.basename(d) + "/Zed"     # a listed folder is a menu
        assert zed in styles.look_names(), styles.look_names()[-3:]
        out, info = styles.build(zed, 1.0, {})
        assert json.loads(out["pixel_art"])["palette_size"] == 5 and "Zed" in info
        # a look with a baseline: widgets the look does not set return to defaults
        assert json.loads(out["pixel_art"])["outline"] == "none"
        out, info = styles.build("nope")
        assert "Unknown look" in info
    finally:
        del os.environ["APODESIGN_LOOKS"]


def test_save_look_node_and_overwrite():
    import json
    from core import styles, userlooks
    pkg = _load_package()
    d = _tmp_looks()
    cls = pkg.NODE_CLASS_MAPPINGS["ApoDesign_SaveLook"]
    node = cls()
    settings = json.dumps({"palette_preset": "gameboy", "target_width": 120, "outline": "none",
                           "transparency": "separate", "palette": "#000000", "applied_overrides": ["x"]})
    info, = node.run("Saved one", "desc", False, pixel_art_settings=settings, save_folder=d)
    path = os.path.join(d, "Saved one.json")
    data = json.load(open(path))
    assert data["name"] == "Saved one" and data["pixel_art"] == {"palette_preset": "gameboy", "target_width": 120}, data
    info, = node.run("Saved one", "desc", False, pixel_art_settings=settings, save_folder=d)
    assert "already exists" in info
    info, = node.run("Saved one", "desc", True, pixel_art_settings=settings, save_folder=d)
    assert info.startswith("Saved")
    info, = node.run("", "", False, look_json=json.dumps({"name": "From LLM", "all": {"palette_preset": "pico8"}}), save_folder=d)
    assert os.path.exists(os.path.join(d, "From LLM.json"))
    info, = node.run("Flat", "", False, look_json='```json\n{"palette_preset": "nes", "bogus": 3}\n```', save_folder=d)
    assert "bogus" in info and os.path.exists(os.path.join(d, "Flat.json"))
    info, = node.run("Empty", "", False, save_folder=d)
    assert "Nothing to save" in info
    # tidy: the node remembers a new folder in looks_folder.txt - undo that for the test
    try:
        lines = open(userlooks.CONFIG_FILE, encoding="utf-8").read().splitlines()
        open(userlooks.CONFIG_FILE, "w", encoding="utf-8").write(
            "\n".join(l for l in lines if os.path.normcase(l.strip()) != os.path.normcase(d)) + "\n")
    except OSError:
        pass


def test_save_look_with_all_default_settings():
    import json, shutil
    from core import bitmap_specs, userlooks
    from core.params import defaults
    pkg = _load_package()
    d = _tmp_looks()
    node = pkg.NODE_CLASS_MAPPINGS["ApoDesign_SaveLook"]()
    info, = node.run("Plain", "", False, bitmap_settings=json.dumps(defaults(bitmap_specs.SPECS)), save_folder=d)
    assert info.startswith("Saved") and "default" in info, info
    assert json.load(open(os.path.join(d, "Plain.json")))["bitmap"]
    try:
        lines = open(userlooks.CONFIG_FILE, encoding="utf-8").read().splitlines()
        open(userlooks.CONFIG_FILE, "w", encoding="utf-8").write(
            "\n".join(l for l in lines if os.path.normcase(l.strip()) != os.path.normcase(d)) + "\n")
    except OSError:
        pass


def test_folder_reached_twice_is_read_once():
    import json, shutil
    from core import userlooks
    sub = os.path.join(userlooks.DEFAULT_DIR, "_dup_test_folder")
    sub = os.path.join(userlooks.DEFAULT_DIR, "dup_test_folder")
    os.makedirs(sub, exist_ok=True)
    try:
        json.dump({"name": "Dup", "bitmap": {"method": "bayer"}}, open(os.path.join(sub, "dup.json"), "w"))
        files = userlooks._files([sub, userlooks.DEFAULT_DIR])
        assert sum(f.endswith("dup.json") for f in files) == 1, files
    finally:
        shutil.rmtree(sub, ignore_errors=True)


def test_subfolders_become_menu_groups():
    import json, shutil, tempfile
    from core import userlooks
    root = tempfile.mkdtemp(prefix="apogroups_")
    try:
        os.makedirs(os.path.join(root, "Arcade", "Deep"))
        for rel, nm in (("Top.json", "Top"), ("Arcade/A1.json", "A1"), ("Arcade/Deep/D1.json", "D1")):
            json.dump({"name": nm, "bitmap": {"method": "bayer"}}, open(os.path.join(root, rel), "w"))
        looks, problems = userlooks.scan({}, [root])
        names = sorted(l["name"] for l in looks)
        assert names == [userlooks.PREFIX + "Arcade/A1", userlooks.PREFIX + "Arcade/Deep/D1", userlooks.PREFIX + "Top"], names
        assert userlooks.display_name(os.path.join(root, "Arcade", "A1.json"), "A1", [root]) == userlooks.PREFIX + "Arcade/A1"
        # a configured folder that also lies inside the built-in looks folder keeps its group
        inner = os.path.join(userlooks.DEFAULT_DIR, "grp_test_folder")
        os.makedirs(inner, exist_ok=True)
        json.dump({"name": "G", "bitmap": {"method": "bayer"}}, open(os.path.join(inner, "g.json"), "w"))
        try:
            looks, _ = userlooks.scan({}, [inner, userlooks.DEFAULT_DIR])
            g = [l["name"] for l in looks if l["name"].endswith("G")]
            assert g == [userlooks.PREFIX + "grp_test_folder/G"], g
        finally:
            shutil.rmtree(inner, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_listed_folder_is_a_menu():
    import json, shutil, tempfile
    from core import userlooks
    root = os.path.join(tempfile.mkdtemp(prefix="apotop_"), "MyTop")
    os.makedirs(os.path.join(root, "Sub"))
    old = os.environ.get("APODESIGN_LOOKS")
    try:
        for rel, nm in (("Top.json", "Top"), ("Sub/S1.json", "S1")):
            json.dump({"name": nm, "bitmap": {"method": "bayer"}}, open(os.path.join(root, rel), "w"))
        os.environ["APODESIGN_LOOKS"] = root
        looks, problems = userlooks.scan({})
        names = sorted(l["name"] for l in looks if "MyTop" in l["name"])
        assert names == [userlooks.PREFIX + "MyTop/Sub/S1", userlooks.PREFIX + "MyTop/Top"], names
        assert userlooks.display_name(os.path.join(root, "Top.json"), "Top") == userlooks.PREFIX + "MyTop/Top"
    finally:
        if old is None:
            os.environ.pop("APODESIGN_LOOKS", None)
        else:
            os.environ["APODESIGN_LOOKS"] = old
        shutil.rmtree(os.path.dirname(root), ignore_errors=True)


def test_banner_files_are_in_place():
    pkg = _load_package()
    assert pkg.WEB_DIRECTORY == "./web"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "web", "apodesign_banner.js"), encoding="utf-8").read()
    for cls in pkg.NODE_CLASS_MAPPINGS:
        assert cls in js, "banner has no entry for " + cls
    assert "github.com/ApoloniArt" in js and "discord.gg/XDExAUzuZp" in js
    font = open(os.path.join(root, "web", "apodesign_font.js"), encoding="utf-8").read()
    assert "data:font/woff2;base64," in font and len(font) > 5000
    # the font must also be a real file next to the script (the page cannot use embedded
    # fonts under ComfyUI's content security policy) and the script must load it from there
    assert os.path.getsize(os.path.join(root, "web", "fonts", "BitcountInk-500.woff2")) > 5000
    assert "import.meta.url" in js and "fonts/BitcountInk-500.woff2" in js
    # the banner must take part in the saved widget list (never "serialize = false"),
    # otherwise ComfyUI saves by position but restores skipping it and every value shifts
    assert "widget.serialize = true" in js and "widget.serialize = false" not in js
    assert "serializeValue" in js and "widgets_values" in js


def test_builtin_look_names_have_no_slash():
    from core import styles
    assert not [n for n in styles.LOOK_NAMES if "/" in n]


def test_relative_folder_goes_inside_looks_folder():
    from core import userlooks
    r = userlooks.resolve_dir("test1")
    assert r == os.path.normpath(os.path.join(userlooks.DEFAULT_DIR, "test1")), r
    assert userlooks.resolve_dir('  "D:\\My Looks"  ') == "D:\\My Looks"
    assert userlooks.resolve_dir("") == ""


def test_example_looks_and_llm_prompt_are_valid():
    from core import looks_help, styles, userlooks
    ex = os.path.join(userlooks.DEFAULT_DIR, "_examples")
    looks, problems = userlooks.scan(styles.LOOK_BY_NAME, [ex])
    assert len(looks) == 4 and not problems, problems
    p = looks_help.llm_prompt()
    assert "[bitmap]" in p and "[pixel_art]" in p and "palette_preset" in p and "Game Boy (green)" in p
    on_disk = open(os.path.join(userlooks.DEFAULT_DIR, "_LLM_system_prompt.txt"), encoding="utf-8").read()
    assert on_disk == p, "looks/_LLM_system_prompt.txt is out of date: run  python core/looks_help.py > looks/_LLM_system_prompt.txt"
