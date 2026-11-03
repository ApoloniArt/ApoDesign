"""ApoDesign Style - pick a named look, get ready-made settings for the
Bitmap, Ascii and Pixel Art nodes. No torch needed."""
from ..core import styles
from ..core.prompt import parse_style_json


class ApoDesignStyle:
    CATEGORY = "ApoDesign"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("bitmap", "ascii", "pixel_art", "info")
    DESCRIPTION = ("Pick a classic look (Game Boy, NES, C64, newspaper "
                   "halftone, Matrix code ...) and connect the matching "
                   "output to the style_json input of the Bitmap, Ascii or "
                   "Pixel Art node. Every look has a recipe for all three "
                   "nodes, so the same choice gives a matching result "
                   "whichever you use.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "look": (styles.look_names(), {"default": styles.LOOK_NAMES[0],
                         "tooltip": "The look to apply. The info output says "
                                    "what it does. Your own looks (from the "
                                    "looks folder) are marked with a star and "
                                    "listed last. Press R in ComfyUI to "
                                    "refresh the list after adding a file."}),
                "scale": ("FLOAT", {"default": 1.0, "min": 0.25, "max": 4.0,
                          "step": 0.05, "tooltip":
                          "Chunkier above 1 (bigger pixels, fewer characters, "
                          "larger halftone dots), finer below 1."}),
            },
            "optional": {
                "tweaks": ("STRING", {"default": "", "multiline": True,
                           "tooltip": "Optional changes on top of the look, as "
                                      "JSON, e.g. {\"palette_size\": 8, "
                                      "\"outline\": \"dark\"}. Use the widget "
                                      "names of the node. Names a node does "
                                      "not have are skipped for that node."}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, look=None, scale=1.0, tweaks=""):
        from ..core import userlooks     # re-run when a look file is edited
        return userlooks.signature_hash()

    def run(self, look, scale=1.0, tweaks=""):
        over, err = parse_style_json(tweaks)
        out, info = styles.build(look, scale, over)
        if err:
            info += "\ntweaks: " + err
        return (out["bitmap"], out["ascii"], out["pixel_art"], info)


NODE_CLASS_MAPPINGS = {"ApoDesign_Style": ApoDesignStyle}
NODE_DISPLAY_NAME_MAPPINGS = {"ApoDesign_Style": "ApoDesign Style"}
