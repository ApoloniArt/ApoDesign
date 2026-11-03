"""Widget specs for the ApoDesign Pixel Art node. Pure Python."""
from .palettes import PRESETS
from .params import Spec

PIXEL_METHODS = ["none", "bayer", "blue_noise", "floyd_steinberg", "atkinson",
                 "sierra", "sierra_lite", "stucki", "jarvis", "burkes"]

SPECS = [
    Spec("style_prompt", "string", "", multiline=True, promptable=False,
         tip="Optional plain-English style, e.g. '24 colours, outline, 160 "
             "wide, painterly'. Sets the widgets below."),
    Spec("prompt_priority", "combo", "prompt", choices=["prompt", "widgets"],
         promptable=False,
         tip="prompt: the style prompt overrides the widgets. widgets: the "
             "prompt only fills widgets you left at their defaults."),
    Spec("pixel_size", "int", 4, 1, 128,
         tip="Size of each chunky pixel, in source pixels."),
    Spec("target_width", "int", 0, 0, 4096,
         tip="Alternative to pixel_size: the number of pixels across the "
             "image (0 = off). Allows non-integer scaling, e.g. 160 across "
             "a 1920 image."),
    Spec("output_scale", "int", 1, 1, 8,
         tip="Extra whole-number enlargement of the final image, always "
             "crisp nearest-neighbour."),
    Spec("pixel_mode", "combo", "dominant", choices=["dominant", "average", "nearest"],
         tip="How each pixel gets its colour. dominant: the most common "
             "palette colour in the block, which keeps edges crisp like "
             "hand-made pixel art. average: the block's mean colour (softer, "
             "can be muddy). nearest: one sample from the block's centre."),
    Spec("simplify", "float", 0.0, 0.0, 1.0,
         tip="Painterly flattening before pixelating (Kuwahara filter): "
             "noise and texture melt into clean colour regions while edges "
             "stay sharp. 0 = off."),
    Spec("palette_preset", "combo", "adaptive_kmeans",
         choices=["adaptive_kmeans", "none"] + list(PRESETS),
         tip="adaptive_kmeans builds a palette from your image (shared by "
             "every frame of a video). none keeps the full colours. The rest "
             "are classic palettes."),
    Spec("palette_size", "int", 16, 2, 64,
         tip="Number of colours for palette_preset = adaptive_kmeans."),
    Spec("custom_palette", "string", "",
         tip="Your own palette as hex codes, e.g. #0f380f,#306230,#8bac0f. "
             "Overrides the preset when it holds 2 or more colours."),
    Spec("match", "combo", "colour", choices=["colour", "tone"],
         tip="How pixels are matched to the palette. colour: nearest colour "
             "(use for full-colour palettes). tone: by brightness only (use "
             "for Game Boy, phosphor, sepia and other one-hue palettes)."),
    Spec("method", "combo", "none", choices=PIXEL_METHODS,
         tip="Dithering when snapping to the palette (pixel_mode average or "
             "nearest). none is clean. bayer / blue_noise are steady on "
             "video; error diffusion shimmers slightly between frames."),
    Spec("bayer_size", "combo", "4", choices=["2", "4", "8", "16"],
         tip="Matrix size for the bayer method."),
    Spec("dither_strength", "float", 1.0, 0.0, 2.0,
         tip="Strength of the dithering. 0 = plain nearest palette colour."),
    Spec("cleanup", "int", 1, 0, 3,
         tip="Removes stray pixels that do not belong: 1 = isolated single "
             "pixels, 2 and 3 = progressively more. Gives the clean "
             "hand-placed look. Turn it off when using dithering."),
    Spec("outline", "combo", "none", choices=["none", "dark", "colour"],
         tip="Draws a one-pixel line along edges, on the darker side. dark: "
             "a darker shade of the pixel's own colour (selective outline). "
             "colour: the outline_color below."),
    Spec("outline_color", "string", "#000000",
         tip="Outline colour (hex) for outline = colour."),
    Spec("outline_threshold", "float", 0.12, 0.01, 0.6,
         tip="How big a brightness step must be to get an outline. Lower = "
             "more lines."),
    Spec("saturation", "float", 1.0, 0.0, 3.0,
         tip="Colour intensity before palette matching. Above 1 gives punchy "
             "pixel-art colours."),
    Spec("brightness", "float", 0.0, -1.0, 1.0, tip="Brightness before matching."),
    Spec("contrast", "float", 1.0, 0.0, 4.0, tip="Contrast before matching."),
    Spec("gamma", "float", 1.0, 0.1, 4.0,
         tip="Midtone curve. Above 1 brightens the midtones."),
    Spec("sharpen", "float", 0.0, 0.0, 4.0,
         tip="Sharpen before matching, so fine detail survives."),
    Spec("local_contrast", "float", 0.0, 0.0, 2.0,
         tip="Local contrast boost so shadows and highlights keep structure."),
    Spec("invert", "bool", False, tip="Invert the picture before matching."),
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
