"""ApoDesign Ascii - image -> ASCII / block / braille text art, as an image."""
import json

from ..core.ascii_prompt import parse_ascii_prompt
from ..core.ascii_specs import SPEC_BY_NAME, SPECS
from ..core.params import apply_overrides, defaults, input_entry
from ..core.prompt import parse_style_json


class ApoDesignAscii:
    CATEGORY = "ApoDesign"
    FUNCTION = "run"
    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING", "STRING", "MASK")
    RETURN_NAMES = ("image", "glyph_mask", "text", "palette", "settings", "alpha")
    DESCRIPTION = ("Converts images to text art: brightness ramps, shape-matched "
                   "characters, block mosaics and braille, in black & white, "
                   "palettes, or full colour. Also returns the art as plain "
                   "text. Batch and video safe.")

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
        from ..core import ascii_engine, common  # torch loads only when needed

        values = {s.name: kw.get(s.name, s.default) for s in SPECS}
        notes = []

        over, _ = parse_ascii_prompt(values["style_prompt"])
        always = values["prompt_priority"] == "prompt"
        values, applied = apply_overrides(values, over, SPEC_BY_NAME, always)
        notes += ["prompt: " + a for a in applied]

        jover, jerr = parse_style_json(style_json)
        if jerr:
            notes.append(jerr)
        values, applied = apply_overrides(values, jover, SPEC_BY_NAME, True)
        notes += ["json: " + a for a in applied]

        device = common.pick_device()
        colour_mask = mask if values["mix_mode"] == "mask" else None
        alpha, rgba = common.pick_alpha(mask, values["transparency"], values["mix_mode"],
                                       values["invert_mask"])
        try:
            try:
                out = ascii_engine.render(image, colour_mask, values, device, alpha, rgba)
            except RuntimeError as e:  # most likely out of VRAM: retry on the CPU
                if str(device) == "cpu":
                    raise
                print("[ApoDesign] %s failed on %s (%s); retrying on CPU"
                      % (self.__class__.__name__, device, str(e).splitlines()[0]))
                import torch
                out = ascii_engine.render(image, colour_mask, values, torch.device("cpu"),
                                          alpha, rgba)
        finally:
            if image.shape[0] > 1:
                common.release_gpu(device)

        settings = {k: values[k] for k in defaults(SPECS)
                    if k not in ("style_prompt", "prompt_priority")}
        settings["palette"] = out["palette"]
        settings["transparency_applied"] = alpha is not None
        notes += out["notes"]
        for n in out["notes"]:
            print("[ApoDesign] Ascii: " + n)
        if notes:
            settings["applied_overrides"] = notes
        return (out["image"], out["mask"], out["text"], out["palette"],
                json.dumps(settings, indent=2, ensure_ascii=False), out["alpha"])


NODE_CLASS_MAPPINGS = {"ApoDesign_Ascii": ApoDesignAscii}
NODE_DISPLAY_NAME_MAPPINGS = {"ApoDesign_Ascii": "ApoDesign Ascii"}
