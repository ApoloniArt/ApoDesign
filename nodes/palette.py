"""ApoDesign Palette - build, extract or generate a colour palette and feed
it to the Bitmap, Ascii and Pixel Art nodes."""
import json

from ..core import palette_tools as T
from ..core.palettes import PRESETS, hex_to_rgb, parse_palette


class ApoDesignPalette:
    CATEGORY = "ApoDesign"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("palette", "swatch", "style_json")
    DESCRIPTION = ("Makes a palette: from a classic preset, your own hex "
                   "codes, the colours of a picture, a gradient between two "
                   "colours, or a colour scheme built around one colour. "
                   "Connect style_json to the style_json input of the "
                   "Bitmap, Ascii or Pixel Art node.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (T.MODES, {"default": "preset", "tooltip":
                         "preset: a classic palette. hex_list: your own "
                         "colours. from_image: the main colours of the "
                         "connected image. gradient: colour_a to colour_b. "
                         "harmony: a colour scheme built on colour_a."}),
                "preset": (list(PRESETS), {"default": "gameboy",
                           "tooltip": "Palette for mode = preset."}),
                "hex_list": ("STRING", {"default": "", "tooltip":
                             "Colours for mode = hex_list, e.g. "
                             "#0f380f,#306230,#8bac0f"}),
                "colours": ("INT", {"default": 8, "min": 2, "max": 64,
                            "tooltip": "How many colours (from_image, "
                                       "gradient, harmony)."}),
                "colour_a": ("STRING", {"default": "#1b1b3a", "tooltip":
                             "Start colour for gradient, base colour for "
                             "harmony."}),
                "colour_b": ("STRING", {"default": "#f7efe0", "tooltip":
                             "End colour for gradient."}),
                "colour_mid": ("STRING", {"default": "", "tooltip":
                               "Optional middle colour for gradient."}),
                "scheme": (T.HARMONIES, {"default": "analogous", "tooltip":
                           "Colour scheme for mode = harmony."}),
                "sort": (T.SORTS, {"default": "dark_to_light", "tooltip":
                         "Order of the colours in the output."}),
                "set_colour_modes": ("BOOLEAN", {"default": True, "tooltip":
                                     "Also set color_mode (and match, in Pixel "
                                     "Art) in style_json to suit the palette: "
                                     "by brightness for one-hue palettes, by "
                                     "colour for the rest."}),
                "swatch_height": ("INT", {"default": 64, "min": 16, "max": 512,
                                  "tooltip": "Height in pixels of the swatch "
                                             "image (each colour is as wide "
                                             "as it is tall)."}),
            },
            "optional": {
                "image": ("IMAGE", {"tooltip": "Picture for mode = from_image. "
                                    "Up to 16 evenly spaced frames are used."}),
            },
        }

    def run(self, mode, preset, hex_list, colours, colour_a, colour_b, colour_mid,
            scheme, sort, set_colour_modes, swatch_height, image=None):
        notes = []
        a = hex_to_rgb(colour_a) or (0.1, 0.1, 0.2)
        b = hex_to_rgb(colour_b) or (0.97, 0.94, 0.88)
        mid = hex_to_rgb(colour_mid) if colour_mid.strip() else None

        if mode == "preset":
            cols = T.preset(preset)
        elif mode == "hex_list":
            cols = parse_palette(hex_list)
            if len(cols) < 2:
                notes.append("hex_list needs at least 2 valid colours; using black and white")
                cols = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
        elif mode == "from_image":
            if image is None:
                notes.append("from_image needs the image input; using black and white")
                cols = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
            else:
                cols = self._from_image(image, int(colours))
        elif mode == "gradient":
            cols = T.gradient(a, b, colours, mid)
        else:
            cols = T.harmony(a, scheme, colours)

        cols, text = T.finish(cols, sort)
        data = {"custom_palette": text}
        if set_colour_modes:
            tonal = T.is_tonal(cols)
            data["color_mode"] = "tonal" if tonal else "palette"
            data["match"] = "tone" if tonal else "colour"
        for n in notes:
            print("[ApoDesign] Palette: " + n)
        return (text, self._swatch(cols, int(swatch_height)), json.dumps(data, indent=2))

    @staticmethod
    def _from_image(image, k):
        import torch
        import torch.nn.functional as F
        from ..core import bitmap_engine, common
        B = image.shape[0]
        idx = torch.linspace(0, B - 1, min(B, 16)).round().long().unique()
        x = common.to_chw(image[idx])
        x = F.adaptive_avg_pool2d(x, (96, 96)).clamp(0.0, 1.0)
        return bitmap_engine.adaptive_palette(x, k)

    @staticmethod
    def _swatch(cols, h):
        import torch
        strip = torch.tensor(cols, dtype=torch.float32).view(1, 1, len(cols), 3)
        return strip.repeat_interleave(h, 2).repeat(1, h, 1, 1)


NODE_CLASS_MAPPINGS = {"ApoDesign_Palette": ApoDesignPalette}
NODE_DISPLAY_NAME_MAPPINGS = {"ApoDesign_Palette": "ApoDesign Palette"}
