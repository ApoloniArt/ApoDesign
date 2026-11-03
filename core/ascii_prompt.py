"""Style-prompt parser for the ApoDesign Ascii node. Pure Python.

Runs the shared parser (palettes, colours, contrast, dither method ...) and
adds the ASCII-specific words: braille, shape, blocks, quadrants, edges,
columns, bold, terminal / print looks.
"""
import re

from .palettes import hex_to_rgb, luma
from .prompt import parse_style_prompt


def parse_ascii_prompt(text):
    """Return (overrides, notes) for the Ascii node."""
    out, _ = parse_style_prompt(text)
    if not text or not text.strip():
        return out, []

    # The shared parser knows Bitmap-only ideas; translate or drop them.
    if out.get("method") == "threshold":
        out["method"] = "none"
    if out.get("method") in ("halftone_dots", "halftone_lines"):
        del out["method"]
    out.pop("pixel_size", None)
    if "target_width" in out:
        out["columns"] = out.pop("target_width")

    t = text.lower().replace("&", " and ")
    t = re.sub(r"[_\-]+", " ", t)
    t = re.sub(r"[^a-z0-9#,.\s]", " ", t)
    t = re.sub(r"\s+", " ", t)

    # ---- size ----------------------------------------------------------------
    m = re.search(r"\b(\d{2,4})\s*(?:columns|cols|chars|characters|letters|cells)\b", t)
    if m:
        out["columns"] = int(m.group(1))

    # ---- how characters are chosen -------------------------------------------
    quad = re.search(r"\bquadrants?\b|\bmosaic\b|\bteletext\b", t)
    if re.search(r"\bbraille\b", t):
        out["glyph_match"] = "braille"
    elif quad:
        out["glyph_match"] = "shape"
        out["charset"] = "quadrants"
    elif re.search(r"\bshape\b|\bstructure\b|\bstructural\b", t):
        out["glyph_match"] = "shape"

    if not quad:
        if re.search(r"\bblocks?\b|\bblock art\b", t):
            out["charset"] = "blocks"
        elif re.search(r"\bbinary\b|\bones and zeros\b|\b0 and 1\b", t):
            out["charset"] = "binary"
        elif re.search(r"\bmatrix\b|\bletters\b|\balphabet\b", t):
            out["charset"] = "letters"
        elif re.search(r"\bdense\b|\bmany characters\b|\bfull ramp\b|\bdetailed\b", t):
            out["charset"] = "standard"
        elif re.search(r"\bsimple\b|\bminimal\b|\bfew characters\b", t):
            out["charset"] = "simple"
        elif re.search(r"\bclassic\b", t):
            out["charset"] = "classic"

    if re.search(r"\bedges?\b|\boutlines?\b|\bline work\b|\bline art\b", t):
        out["edge_strength"] = 0.5
        out.setdefault("glyph_match", "ramp")

    # ---- look ---------------------------------------------------------------
    if re.search(r"\bbold\b", t):
        out["font_bold"] = True
    if re.search(r"\bpixel font\b|\bbitmap font\b|\bretro font\b|\bcrisp glyphs?\b", t):
        out["glyph_style"] = "crisp"
    if re.search(r"\bdark on light\b|\bblack on white\b|\bink on paper\b|\bprinted?\b", t):
        out["polarity"] = "dark_on_light"
    elif re.search(r"\bwhite on black\b|\blight on dark\b|\bterminal\b|\bhacker\b|\bcrt\b", t):
        out["polarity"] = "light_on_dark"
    if re.search(r"\bmatrix\b", t) and "palette_preset" not in out \
            and "custom_palette" not in out:
        out["palette_preset"] = "green_phosphor"

    # "X on Y" read as ink on paper: the darker colour is the ink
    if out.get("palette_preset") == "ink_paper" and "polarity" not in out:
        ink, paper = hex_to_rgb(out.get("ink_color")), hex_to_rgb(out.get("paper_color"))
        if ink and paper:
            out["polarity"] = "dark_on_light" if luma(ink) < luma(paper) else "light_on_dark"

    # plain "colour ascii"
    if re.search(r"\bcolou?r(?:ed|ful)?\b", t) and "color_mode" not in out \
            and "palette_preset" not in out and "custom_palette" not in out:
        out["color_mode"] = "channels"
        out["color_mix"] = 1.0
        out["mix_mode"] = "global"

    notes = ["%s=%s" % (k, v) for k, v in out.items()]
    return out, notes
