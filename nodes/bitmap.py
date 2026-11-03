"""ApoDesign Bitmap - image -> dithered / halftone retro bitmap art."""
import json

from ..core.bitmap_specs import SPEC_BY_NAME, SPECS
from ..core.params import apply_overrides, defaults, input_entry
from ..core.prompt import parse_style_json, parse_style_prompt


class ApoDesignBitmap:
    CATEGORY = "ApoDesign"
    FUNCTION = "run"
    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK", "STRING", "STRING", "MASK")
    RETURN_NAMES = ("image", "lowres", "ink_mask", "palette", "settings", "alpha")
    DESCRIPTION = ("Converts images to retro bitmap art: ordered, blue-noise "
                   "and error-diffusion dithering plus halftone screens, in "
                   "black & white, palettes, or full colour. Batch and "
                   "video safe.")

    @classmethod
    def INPUT_TYPES(cls):
        required = {"image": ("IMAGE",)}
        for s in SPECS:
            required[s.name] = input_entry(s)
        return {
            "required": required,
            "optional": {
                "mask": ("MASK", {"tooltip": "Transparency mask from Load Image (white = transparent): "
                                  "transparent areas stay transparent in the result. "
                                  "If mix_mode = mask it is instead the colour region "
                                  "(colour appears where the mask is white). "
                                  "See the transparency widget."}),
                "style_json": ("STRING", {"forceInput": True, "tooltip":
                               "Optional JSON of widget names and values, "
                               "e.g. from an LLM node. Always wins over "
                               "the widgets and the style prompt."}),
            },
        }

    def run(self, image, mask=None, style_json=None, **kw):
        from ..core import bitmap_engine, common  # torch loads only when needed

        values = {s.name: kw.get(s.name, s.default) for s in SPECS}
        notes = []

        over, _ = parse_style_prompt(values["style_prompt"])
        always = values["prompt_priority"] == "prompt"
        values, applied = apply_overrides(values, over, SPEC_BY_NAME, always)
        notes += ["prompt: " + a for a in applied]

        jover, jerr = parse_style_json(style_json)
        if jerr:
            notes.append(jerr)
        values, applied = apply_overrides(values, jover, SPEC_BY_NAME, True)
        notes += ["json: " + a for a in applied]

        device = common.pick_device()
        want_mask = bool(values["ink_mask_output"])
        colour_mask = mask if values["mix_mode"] == "mask" else None
        alpha, rgba = common.pick_alpha(mask, values["transparency"], values["mix_mode"],
                                       values["invert_mask"])
        try:
            try:
                out = bitmap_engine.render(image, colour_mask, values, device, want_mask,
                                           alpha, rgba)
            except RuntimeError as e:  # most likely out of VRAM: retry on the CPU
                if str(device) == "cpu":
                    raise
                print("[ApoDesign] %s failed on %s (%s); retrying on CPU"
                      % (self.__class__.__name__, device, str(e).splitlines()[0]))
                import torch
                out = bitmap_engine.render(image, colour_mask, values,
                                           torch.device("cpu"), want_mask, alpha, rgba)
        finally:
            if image.shape[0] > 1:
                common.release_gpu(device)

        settings = {k: values[k] for k in defaults(SPECS)
                    if k not in ("style_prompt", "prompt_priority")}
        settings["palette"] = out["palette"]
        settings["transparency_applied"] = alpha is not None
        if notes:
            settings["applied_overrides"] = notes
        return (out["image"], out["lowres"], out["mask"], out["palette"],
                json.dumps(settings, indent=2), out["alpha"])


NODE_CLASS_MAPPINGS = {"ApoDesign_Bitmap": ApoDesignBitmap}
NODE_DISPLAY_NAME_MAPPINGS = {"ApoDesign_Bitmap": "ApoDesign Bitmap"}
