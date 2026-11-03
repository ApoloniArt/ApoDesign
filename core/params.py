"""Declarative widget specs shared by every ApoDesign node. Pure Python.

One Spec list drives three things at once, so they can never drift apart:
the ComfyUI widgets, the defaults, and validation of values that arrive from
the style prompt or the style_json input.
"""
from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass
class Spec:
    name: str
    kind: str                      # "int" | "float" | "bool" | "combo" | "string"
    default: Any
    min: Any = None
    max: Any = None
    step: Any = None
    choices: Optional[Sequence[str]] = None
    tip: str = ""
    multiline: bool = False
    promptable: bool = True        # may the prompt / JSON set this?


def input_entry(s):
    """Spec -> ComfyUI INPUT_TYPES entry."""
    tip = {"tooltip": s.tip} if s.tip else {}
    if s.kind == "int":
        return ("INT", {"default": s.default, "min": s.min, "max": s.max,
                        "step": s.step or 1, **tip})
    if s.kind == "float":
        return ("FLOAT", {"default": s.default, "min": s.min, "max": s.max,
                          "step": s.step or 0.01, **tip})
    if s.kind == "bool":
        return ("BOOLEAN", {"default": s.default, **tip})
    if s.kind == "combo":
        return (list(s.choices), {"default": s.default, **tip})
    return ("STRING", {"default": s.default, "multiline": s.multiline, **tip})


def coerce(s, value):
    """Validate/convert `value` for spec `s`. Returns (ok, value)."""
    try:
        if s.kind == "int":
            v = int(round(float(value)))
            return True, max(s.min, min(s.max, v))
        if s.kind == "float":
            v = float(value)
            return True, max(s.min, min(s.max, v))
        if s.kind == "bool":
            if isinstance(value, bool):
                return True, value
            if isinstance(value, (int, float)):
                return True, bool(value)
            t = str(value).strip().lower()
            if t in ("true", "yes", "on", "1"):
                return True, True
            if t in ("false", "no", "off", "0"):
                return True, False
            return False, None
        if s.kind == "combo":
            t = str(value).strip().lower().replace(" ", "_").replace("-", "_")
            for c in s.choices:
                if c.lower() == t:
                    return True, c
            return False, None
        return True, str(value)
    except (TypeError, ValueError, OverflowError):
        return False, None


def defaults(specs):
    return {s.name: s.default for s in specs}


def apply_overrides(values, overrides, spec_by_name, always):
    """Merge `overrides` into a copy of `values`.

    always=True  -> overrides win over whatever the widgets say.
    always=False -> an override only fills a widget still at its default.
    Returns (new_values, applied) where applied is a list of "name=value".
    """
    out = dict(values)
    applied = []
    for key, raw in overrides.items():
        spec = spec_by_name.get(key)
        if spec is None or not spec.promptable:
            continue
        ok, val = coerce(spec, raw)
        if not ok:
            continue
        if always or out.get(key) == spec.default:
            out[key] = val
            applied.append("%s=%s" % (key, val))
    return out, applied
