"""Widget specs for the ApoDesign Bitmap node. Pure Python (no torch), so the
node, the style-prompt parser and the tests all read the same definitions."""
from .modes import MIX_MODES
from .palettes import PRESETS
from .params import Spec

METHODS = ["bayer", "blue_noise", "floyd_steinberg", "atkinson", "sierra",
           "sierra_lite", "stucki", "jarvis", "burkes", "halftone_dots",
           "halftone_lines", "threshold"]

SPECS = [
    Spec("style_prompt", "string", "", multiline=True, promptable=False,
         tip="Optional plain-English style, e.g. 'gameboy palette, atkinson "
             "dither, 96 wide, high contrast'. Sets the widgets below."),
    Spec("prompt_priority", "combo", "prompt", choices=["prompt", "widgets"],
         promptable=False,
         tip="prompt: the style prompt overrides the widgets. widgets: the "
             "prompt only fills widgets you left at their defaults."),
    Spec("method", "combo", "bayer", choices=METHODS,
         tip="bayer / blue_noise / halftone_* / threshold are ordered and "
             "perfectly steady across video frames. The error-diffusion "
             "methods (floyd_steinberg ... burkes) look organic but shimmer "
             "slightly between frames."),
    Spec("bayer_size", "combo", "8", choices=["2", "4", "8", "16"],
         tip="Matrix size for the bayer method. 2 and 4 are coarse and "
             "crunchy, 8 and 16 are smooth."),
    Spec("pixel_size", "int", 3, 1, 128,
         tip="Size of each chunky pixel, in source pixels."),
    Spec("target_width", "int", 0, 0, 4096,
         tip="Alternative to pixel_size: the number of pixels across the "
             "image (0 = off). Allows non-integer scaling, e.g. 256 across "
             "a 1920 image."),
    Spec("output_scale", "int", 1, 1, 8,
         tip="Extra whole-number enlargement of the final image, always "
             "crisp nearest-neighbour."),
    Spec("palette_preset", "combo", "ink_paper",
         choices=["ink_paper", "adaptive_kmeans"] + list(PRESETS),
         tip="ink_paper uses the two colours below. adaptive_kmeans builds "
             "a palette from your image (shared by every frame of a batch). "
             "The rest are classic palettes."),
    Spec("ink_color", "string", "#000000",
         tip="Dark colour (hex) for palette_preset = ink_paper."),
    Spec("paper_color", "string", "#ffffff",
         tip="Light colour (hex) for palette_preset = ink_paper. Swap ink "
             "and paper for a negative look."),
    Spec("custom_palette", "string", "",
         tip="Your own palette as hex codes, e.g. #0f380f,#306230,#8bac0f. "
             "Overrides the preset when it holds 2 or more colours."),
    Spec("palette_size", "int", 4, 2, 32,
         tip="Number of colours for palette_preset = adaptive_kmeans."),
    Spec("color_mode", "combo", "tonal", choices=["tonal", "palette", "channels"],
         tip="tonal: brightness is dithered through the palette (classic "
             "1-bit / duotone look). palette: colours are matched to the "
             "palette, keeping the picture's hues. channels: red, green and "
             "blue are dithered separately (true colour dither)."),
    Spec("color_levels", "int", 2, 2, 16,
         tip="Levels per channel when color_mode = channels (2 = 8 colours)."),
    Spec("color_mix", "float", 1.0, 0.0, 1.0,
         tip="How much of the colour layer (palette / channels) is mixed "
             "over the tonal layer. 0 = pure tonal. Ignored in tonal mode."),
    Spec("mix_mode", "combo", "global", choices=MIX_MODES,
         tip="Where colour shows when color_mix is below 1: highlights, "
             "shadows, saturated areas, edges_mono (mono line work over "
             "colour), edges_colour, centre, or a MASK you connect."),
    Spec("dither_strength", "float", 1.0, 0.0, 2.0,
         tip="Strength of the dither pattern. 0 = plain posterize. For "
             "error diffusion it scales how much error is passed on."),
    Spec("halftone_cell", "int", 6, 2, 64,
         tip="Dot or line spacing for halftone methods, measured in grid "
             "pixels (use pixel_size 1 for smooth dots)."),
    Spec("halftone_angle", "float", 45.0, 0.0, 90.0, step=1.0,
         tip="Screen angle for halftone methods."),
    Spec("brightness", "float", 0.0, -1.0, 1.0, tip="Brightness before dithering."),
    Spec("contrast", "float", 1.0, 0.0, 4.0, tip="Contrast before dithering."),
    Spec("gamma", "float", 1.0, 0.1, 4.0,
         tip="Midtone curve. Above 1 brightens the midtones."),
    Spec("sharpen", "float", 0.0, 0.0, 4.0,
         tip="Sharpen before dithering, so fine detail survives."),
    Spec("local_contrast", "float", 0.0, 0.0, 2.0,
         tip="Local contrast boost (CLAHE-style) so shadows and highlights "
             "keep their structure."),
    Spec("invert", "bool", False, tip="Invert the picture before dithering."),
    Spec("ink_mask_output", "bool", False, promptable=False,
         tip="Off: the ink_mask output is plain black and uses no memory. "
             "On: it holds the ink coverage (white where there is ink). "
             "Leave off unless you connect ink_mask; it saves about a "
             "third of the node's memory on long videos."),
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
]
SPEC_BY_NAME = {s.name: s for s in SPECS}
