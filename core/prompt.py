"""Keyword style-prompt parser for ApoDesign. Pure Python, no LLM, no network.

parse_style_prompt("gameboy palette, atkinson dither, 96 wide, high contrast")
-> ({"palette_preset": "gameboy", "method": "atkinson", "target_width": 96,
     "contrast": 1.4}, ["palette_preset=gameboy", ...])

The result is a dict of widget-name -> value overrides. Nothing is applied
here; core.params.apply_overrides() validates and merges it.
"""
import json
import re

from .palettes import PRESETS, PRESET_ALIASES, hex_to_rgb, rgb_to_hex, mix_rgb

COLOR_WORDS = {
    "black": "#000000", "white": "#ffffff", "red": "#e03030",
    "orange": "#ff8c1a", "yellow": "#ffe14d", "green": "#2fbf4f",
    "teal": "#1fa6a0", "cyan": "#2fd8e8", "blue": "#2f5fe0",
    "navy": "#16205c", "purple": "#7b3fb5", "violet": "#8a5be0",
    "magenta": "#e02fb0", "pink": "#ff8fc4", "brown": "#7a4a26",
    "tan": "#d2b48c", "beige": "#e8dcc0", "cream": "#f6efd8",
    "gold": "#e6b422", "amber": "#ffb000", "grey": "#808080",
    "gray": "#808080", "silver": "#c0c0c0", "mint": "#b8f2d0",
    "lime": "#a6e22e", "olive": "#6b6b2a", "maroon": "#701c2c",
    "plum": "#4a1d3d", "lavender": "#c9b6f0", "peach": "#ffcba4",
    "sky": "#7ec8f5", "indigo": "#3b2f9a", "crimson": "#c4163a",
    "coral": "#ff7f6e", "turquoise": "#30d5c8", "ivory": "#fffff0",
}
_MODS = {"dark": ("#000000", 0.45), "deep": ("#000000", 0.28),
         "light": ("#ffffff", 0.45), "pale": ("#ffffff", 0.62)}
_NEUTRALS = {"black", "white", "grey", "gray", "silver"}

_COLOR_ALT = "|".join(sorted(COLOR_WORDS, key=len, reverse=True))
_COLOR_RE = r"\b(?:(dark|deep|light|pale)\s+)?(%s)\b" % _COLOR_ALT
_ON_RE = re.compile(_COLOR_RE + r"\s+on\s+" + _COLOR_RE)
_COLOR_FIND = re.compile(_COLOR_RE)

_METHODS = [
    ("blue_noise", r"\bblue ?noise\b"),
    ("floyd_steinberg", r"\bfloyd\b|\bsteinberg\b"),
    ("atkinson", r"\batkinson\b"),
    ("sierra_lite", r"\bsierra lite\b|\blite sierra\b"),
    ("sierra", r"\bsierra\b"),
    ("stucki", r"\bstucki\b"),
    ("jarvis", r"\bjarvis\b"),
    ("burkes", r"\bburkes\b"),
    ("halftone_lines", r"\bline screen\b|\bhalftone lines\b|\bengraving\b"),
    ("halftone_dots", r"\bhalftone\b|\bcomic dots\b"),
    ("bayer", r"\bbayer\b|\bordered\b"),
    ("threshold", r"\bthreshold\b|\bposteri[sz]e\b"),
]


def _color(mod, word):
    base = hex_to_rgb(COLOR_WORDS[word])
    if mod:
        target, amt = _MODS[mod]
        base = mix_rgb(base, hex_to_rgb(target), amt)
    return base


def parse_style_prompt(text):
    """Return (overrides, notes). Unknown words are ignored."""
    out = {}
    if not text or not text.strip():
        return out, []

    raw = text.lower()
    hexes = re.findall(r"#[0-9a-f]{6}\b|#[0-9a-f]{3}\b", raw)
    t = raw.replace("&", " and ")
    t = re.sub(r"[_\-]+", " ", t)
    t = re.sub(r"[^a-z0-9#,.\s]", " ", t)
    t = re.sub(r"\s+", " ", t)

    # ---- dither / screen method -------------------------------------------
    for key, pat in _METHODS:
        if re.search(pat, t):
            out["method"] = key
            break
    m = re.search(r"\bbayer\s*(2|4|8|16)\b", t) or \
        re.search(r"\b(2|4|8|16)\s*x\s*\1\b", t)
    if m:
        out["bayer_size"] = m.group(1)
        out.setdefault("method", "bayer")

    # ---- sizes -------------------------------------------------------------
    m = re.search(r"\b(\d{2,4})\s*(?:px |pixels |cells |columns )?wide\b", t)
    if m:
        out["target_width"] = int(m.group(1))
        t = t.replace(m.group(0), " ")
    m = re.search(r"\bpixel size (\d{1,3})\b", t) or \
        re.search(r"\b(\d{1,3})\s*(?:px|pixel|pixels)\b", t)
    if m:
        out["pixel_size"] = int(m.group(1))
    elif re.search(r"\bchunky\b|\bcoarse\b", t):
        out["pixel_size"] = 6
    elif re.search(r"\bfine detail\b|\bdetailed\b", t):
        out["pixel_size"] = 2

    # ---- bit depth ----------------------------------------------------------
    bits = re.search(r"\b([12]) ?bit\b", t)
    if bits:
        out["color_mode"] = "tonal"
        out["palette_preset"] = "black_white" if bits.group(1) == "1" else "grey_4"

    # ---- palette: explicit hex, preset names, then colour words -------------
    chosen_palette = False
    if len(hexes) >= 2:
        out["custom_palette"] = ",".join(hexes)
        chosen_palette = True
    if not chosen_palette:
        for phrase in sorted(PRESET_ALIASES, key=len, reverse=True):
            if re.search(r"\b%s\b" % re.escape(phrase), t):
                out["palette_preset"] = PRESET_ALIASES[phrase]
                chosen_palette = True
                break
    if not chosen_palette:
        for name in PRESETS:
            if re.search(r"\b%s\b" % re.escape(name.replace("_", " ")), t):
                out["palette_preset"] = name
                chosen_palette = True
                break
    if not chosen_palette and not bits:
        on = _ON_RE.search(t)
        if on:
            ink = _color(on.group(1), on.group(2))
            paper = _color(on.group(3), on.group(4))
            out["palette_preset"] = "ink_paper"
            out["ink_color"] = rgb_to_hex(ink)
            out["paper_color"] = rgb_to_hex(paper)
            chosen_palette = True
        else:
            found, seen = [], set()
            for cm in _COLOR_FIND.finditer(t):
                key = (cm.group(1), cm.group(2))
                if key not in seen:
                    seen.add(key)
                    found.append(key)
            if len(found) >= 2:
                out["custom_palette"] = ",".join(
                    rgb_to_hex(_color(mod, w)) for mod, w in found)
                chosen_palette = True
            elif len(found) == 1 and found[0][1] not in _NEUTRALS:
                base = _color(*found[0])
                out["custom_palette"] = ",".join(rgb_to_hex(c) for c in (
                    mix_rgb(base, (0, 0, 0), 0.65), base,
                    mix_rgb(base, (1, 1, 1), 0.7)))
                chosen_palette = True

    # ---- colour behaviour ----------------------------------------------------
    where = None
    if re.search(r"\bcolou?r (?:in|on) (?:the )?highlights\b", t):
        where = "highlights"
    elif re.search(r"\bcolou?r (?:in|on) (?:the )?shadows\b", t):
        where = "shadows"
    elif re.search(r"\bsaturated\b|\bselective colou?r\b", t):
        where = "saturation"
    if where:
        out["color_mode"] = "channels"
        out["mix_mode"] = where
        out["color_mix"] = 0.5
    elif re.search(r"\bfull colou?r\b|\btrue colou?r\b|\brgb\b", t):
        out["color_mode"] = "channels"
        out["color_mix"] = 1.0
        out["mix_mode"] = "global"
    elif re.search(r"\bpalette colou?rs?\b|\blimited colou?rs?\b", t):
        out["color_mode"] = "palette"
        out["color_mix"] = 1.0
        out["mix_mode"] = "global"
    elif re.search(r"\bmonochrome\b|\bmono\b|\bgre[yz]scale\b|\bgrayscale\b|"
                   r"\bb and w\b|\bblack and white\b", t):
        out.setdefault("color_mode", "tonal")
        if not chosen_palette:
            out["palette_preset"] = "black_white"

    # ---- tone adjustments -----------------------------------------------------
    if re.search(r"\bvery high contrast\b", t):
        out["contrast"] = 1.8
    elif re.search(r"\bhigh contrast\b", t):
        out["contrast"] = 1.4
    elif re.search(r"\blow contrast\b", t):
        out["contrast"] = 0.75
    if re.search(r"\bsharp\b|\bcrisp\b", t):
        out["sharpen"] = 1.0
    if re.search(r"\binvert(?:ed)?\b|\bnegative\b", t):
        out["invert"] = True

    notes = ["%s=%s" % (k, v) for k, v in out.items()]
    return out, notes


def parse_style_json(text):
    """Parse the style_json input. Returns (overrides_dict, error_or_None)."""
    if not text or not str(text).strip():
        return {}, None
    s = str(text).strip()
    # LLMs love wrapping JSON in code fences or chatter; grab the outer {...}.
    a, b = s.find("{"), s.rfind("}")
    if a == -1 or b <= a:
        return {}, "style_json: no JSON object found"
    try:
        data = json.loads(s[a:b + 1])
    except ValueError as e:
        return {}, "style_json: %s" % e
    if not isinstance(data, dict):
        return {}, "style_json: top level must be an object"
    return data, None
