"""Widget specs for the ApoDesign Ascii node. Pure Python (no torch, no
Pillow), so the node, the style-prompt parser and the tests share them."""
from .modes import MIX_MODES
from .palettes import PRESETS
from .params import Spec

# Characters per preset. Order does not matter: the engine measures how much
# ink each glyph really has in the chosen font and sorts them by that.
CHARSETS = {
    "classic": " .:-=+*#%@",
    "standard": " .'`^\",:;Il!i><~+_-?][}{1)(|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "simple": " .oO@",
    "blocks": " ░▒▓█",
    "quadrants": " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█",
    "binary": " 01",
    "letters": " .,:;il1tfLCG08@",
}
CHARSET_NAMES = list(CHARSETS) + ["custom"]
EDGE_CHARS = "|/-\\"          # vertical, rising, horizontal, falling

FONT_CHOICES = ["builtin", "consolas", "courier_new", "lucida_console", "custom_file"]
ASCII_METHODS = ["none", "bayer", "blue_noise", "floyd_steinberg", "atkinson",
                 "sierra", "sierra_lite", "stucki", "jarvis", "burkes"]

SPECS = [
    Spec("style_prompt", "string", "", multiline=True, promptable=False,
         tip="Optional plain-English style, e.g. 'braille, 160 columns, "
             "green phosphor' or 'dense characters, edges, colour'. Sets "
             "the widgets below."),
    Spec("prompt_priority", "combo", "prompt", choices=["prompt", "widgets"],
         promptable=False,
         tip="prompt: the style prompt overrides the widgets. widgets: the "
             "prompt only fills widgets you left at their defaults."),
    Spec("glyph_match", "combo", "ramp", choices=["ramp", "shape", "braille"],
         tip="ramp: brightness picks the character, like classic ASCII art. "
             "shape: each cell gets the character whose SHAPE best matches "
             "the picture there, so edges follow the drawing (try it with "
             "the standard or quadrants charset). braille: 2x4 dots per "
             "cell, the finest detail."),
    Spec("charset", "combo", "standard", choices=CHARSET_NAMES,
         tip="Which characters may be used (ramp and shape modes). standard "
             "is the 70-character ramp; blocks and quadrants give a chunky "
             "mosaic look; custom uses custom_charset."),
    Spec("custom_charset", "string", "",
         tip="Your own characters for charset = custom, e.g. ' .oO0@'. "
             "Include a space for the darkest cells."),
    Spec("columns", "int", 120, 8, 1000,
         tip="Number of characters across. More = finer detail."),
    Spec("cell_aspect", "float", 2.0, 1.0, 3.0, step=0.05,
         tip="Height of a character cell divided by its width. 2.0 suits "
             "most monospace fonts."),
    Spec("output_scale", "int", 1, 1, 4,
         tip="Whole-number enlargement of the final image. Characters are "
             "drawn fresh at the larger size, so they stay sharp."),
    Spec("font", "combo", "builtin", choices=FONT_CHOICES,
         tip="builtin is DejaVu Sans Mono, bundled with ApoDesign. The others "
             "are used if installed on this computer, otherwise builtin is "
             "used. custom_file uses font_file."),
    Spec("font_file", "string", "",
         tip="Full path to a .ttf / .otf monospace font, for font = custom_file."),
    Spec("font_bold", "bool", False, tip="Use the bold weight of the font."),
    Spec("glyph_style", "combo", "smooth", choices=["smooth", "crisp"],
         tip="smooth: anti-aliased characters. crisp: hard-edged, "
             "bitmap-font look."),
    Spec("method", "combo", "none", choices=ASCII_METHODS,
         tip="Dithering of the character choice (and of colours). none is "
             "clean classic ASCII. bayer / blue_noise are steady on video; "
             "the error-diffusion methods look organic but shimmer slightly "
             "between frames."),
    Spec("bayer_size", "combo", "8", choices=["2", "4", "8", "16"],
         tip="Matrix size for the bayer method."),
    Spec("dither_strength", "float", 1.0, 0.0, 2.0,
         tip="Strength of the dithering. 0 = plain nearest character."),
    Spec("edge_strength", "float", 0.0, 0.0, 1.0,
         tip="Ramp mode only: draw | / - \\ along strong edges, so outlines "
             "read as line work. 0 = off."),
    Spec("polarity", "combo", "light_on_dark",
         choices=["light_on_dark", "dark_on_light"],
         tip="light_on_dark: bright characters on a dark page (terminal "
             "look), bright picture areas get dense characters. "
             "dark_on_light: ink on paper, dark areas get dense characters."),
    Spec("palette_preset", "combo", "ink_paper",
         choices=["ink_paper", "adaptive_kmeans"] + list(PRESETS),
         tip="Colours of the page and characters. The darkest palette colour "
             "and the lightest one become page and ink (see polarity). "
             "adaptive_kmeans builds a palette from your image."),
    Spec("ink_color", "string", "#000000",
         tip="One of the two colours for palette_preset = ink_paper."),
    Spec("paper_color", "string", "#ffffff",
         tip="The other colour for ink_paper. polarity decides which one is "
             "the page and which one the characters."),
    Spec("custom_palette", "string", "",
         tip="Your own palette as hex codes, e.g. #0f380f,#306230,#8bac0f. "
             "Overrides the preset when it holds 2 or more colours."),
    Spec("palette_size", "int", 4, 2, 32,
         tip="Number of colours for palette_preset = adaptive_kmeans."),
    Spec("color_mode", "combo", "tonal", choices=["tonal", "palette", "channels"],
         tip="tonal: one ink colour on one page colour. palette: every "
             "character takes the nearest palette colour to the picture. "
             "channels: every character takes the picture's own colour "
             "(quantised to color_levels per channel)."),
    Spec("color_levels", "int", 4, 2, 16,
         tip="Levels per channel when color_mode = channels. 2 = 8 colours, "
             "4 = 64, 16 = 4096."),
    Spec("color_mix", "float", 1.0, 0.0, 1.0,
         tip="How much colour is mixed over the plain ink colour. 0 = none."),
    Spec("mix_mode", "combo", "global", choices=MIX_MODES,
         tip="Where colour shows when color_mix is below 1: highlights, "
             "shadows, saturated areas, edges_mono, edges_colour, centre, or "
             "a MASK you connect."),
    Spec("color_boost", "float", 0.5, 0.0, 1.0,
         tip="channels mode on a dark page: brightens each character's "
             "colour to full vividness, because the character's density "
             "already carries the brightness. 0 = true colour."),
    Spec("background", "combo", "paper", choices=["paper", "tint"],
         tip="paper: plain page colour behind every character. tint: the "
             "page takes a faint shade of the cell's colour."),
    Spec("bg_tint", "float", 0.2, 0.0, 1.0,
         tip="How strongly the page takes the cell colour when background = tint."),
    Spec("brightness", "float", 0.0, -1.0, 1.0, tip="Brightness before conversion."),
    Spec("contrast", "float", 1.0, 0.0, 4.0, tip="Contrast before conversion."),
    Spec("gamma", "float", 1.0, 0.1, 4.0,
         tip="Midtone curve. Above 1 brightens the midtones."),
    Spec("sharpen", "float", 0.0, 0.0, 4.0,
         tip="Sharpen before conversion, so fine detail survives."),
    Spec("local_contrast", "float", 0.0, 0.0, 2.0,
         tip="Local contrast boost so shadows and highlights keep structure."),
    Spec("invert", "bool", False, tip="Invert the picture before conversion."),
    Spec("text_frame", "int", 0, -1, 100000, promptable=False,
         tip="Which frame to put in the text output (0 = first). -1 = every "
             "frame, separated by a line containing only a form feed."),
    Spec("glyph_mask_output", "bool", False, promptable=False,
         tip="Off: the glyph_mask output is plain black and uses no memory. "
             "On: it holds the characters' coverage (white where there is "
             "ink). Leave off unless you connect glyph_mask."),
    Spec("transparency", "combo", "rgba", choices=["rgba", "separate", "off"], promptable=False,
         tip="What to do when the connected mask makes parts of the picture "
             "transparent (white = transparent, as core Load Image outputs it). "
             "rgba: the image output carries its own alpha channel, so Preview "
             "and Save Image show / write real transparency - do NOT add Join "
             "Image with Alpha. separate: the image stays plain RGB "
             "(transparent areas black) and the alpha output holds the "
             "transparency, for Join Image with Alpha or video. off: ignore "
             "the mask. An all-opaque mask is ignored automatically."),
    Spec("invert_mask", "bool", False, promptable=False,
         tip="Turn on if the transparency comes out the wrong way round "
             "(the subject vanishes and the background stays). Some loaders "
             "output white = opaque instead of white = transparent."),
    Spec("text_order", "combo", "off", choices=["off", "in_order", "in_order_per_row"],
         tip="off: the usual tone-based choice of characters. in_order: the "
             "inked cells are filled with order_text, one letter after "
             "another in reading order, so the words can be read (e.g. LEST "
             "WE FORGET). in_order_per_row: every row starts the text again. "
             "Ramp and shape modes only; edge_strength is ignored."),
    Spec("order_text", "string", "LEST WE FORGET", promptable=False,
         tip="The text used by text_order. It repeats, with a space between "
             "repeats. Spaces in it leave small gaps between the words."),
    Spec("order_threshold", "float", 0.15, 0.0, 1.0, step=0.01, promptable=False,
         tip="text_order only: how dark a cell may be and still get a letter. "
             "Higher = fewer letters (only the brighter parts of the picture); "
             "0 = a letter in every cell. Raise brightness or gamma instead "
             "if too much of the picture stays empty."),
]
SPEC_BY_NAME = {s.name: s for s in SPECS}
