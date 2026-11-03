"""ApoDesign Save Look - save your own look so it shows up in the Style node.
No torch needed."""
import json

from ..core import styles, userlooks
from ..core.prompt import parse_style_json

_KNOWN = ("name", "description", "desc", "extends", "all") + userlooks.SECTIONS


class ApoDesignSaveLook:
    CATEGORY = "ApoDesign"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("info",)
    OUTPUT_NODE = True
    DESCRIPTION = ("Saves a look file into your looks folder. Connect the "
                   "settings output of the Bitmap, Ascii and/or Pixel Art "
                   "node you tuned, or paste a look written by an LLM into "
                   "look_json. The look then appears (marked with a star) "
                   "in the Style node's list; press R in ComfyUI to refresh.")

    @classmethod
    def INPUT_TYPES(cls):
        sock = {"forceInput": True}
        return {
            "required": {
                "name": ("STRING", {"default": "", "tooltip":
                         "Name of the look, as shown in the Style node. "
                         "Leave empty to use the name inside look_json."}),
                "description": ("STRING", {"default": "", "tooltip":
                                "Optional one-line description."}),
                "overwrite": ("BOOLEAN", {"default": False, "tooltip":
                              "Replace an existing look file with the same name."}),
            },
            "optional": {
                "bitmap_settings": ("STRING", sock),
                "ascii_settings": ("STRING", sock),
                "pixel_art_settings": ("STRING", sock),
                "look_json": ("STRING", {"default": "", "multiline": True, "tooltip":
                              "A whole look as JSON (for example written by an "
                              "LLM), or just widget names and values. The "
                              "settings inputs are added on top of it."}),
                "save_folder": ("STRING", {"default": "", "tooltip":
                                "Full folder path to save into, e.g. D:\\ComfyUI\\MyLooks "
                                "(created if missing). Leave empty to use your looks "
                                "folder. A bare name like 'test1' makes a sub-folder "
                                "of the looks folder. A new folder is remembered "
                                "(looks_folder.txt) so the Style node finds it."}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kw):
        return float("nan")      # always run: saving is a side effect

    def run(self, name, description, overwrite, bitmap_settings="", ascii_settings="",
            pixel_art_settings="", look_json="", save_folder=""):
        base, err = parse_style_json(look_json)
        notes = [err] if err else []
        if base and not any(k in base for k in _KNOWN):
            base = {"all": base}                  # flat widget names: share across nodes
        sections = {sec: dict(base.get(sec) or {}) for sec in userlooks.SECTIONS
                    if isinstance(base.get(sec), dict)}
        for sec, text in (("bitmap", bitmap_settings), ("ascii", ascii_settings),
                          ("pixel_art", pixel_art_settings)):
            data, e = parse_style_json(text)
            if e:
                notes.append("%s_settings: %s" % (sec, e.replace("style_json: ", "")))
                continue
            recipe = userlooks.settings_to_recipe(sec, data)
            if not recipe and data:
                recipe = userlooks.settings_to_recipe(sec, data, full=True)
                if recipe:
                    notes.append("%s_settings: every setting was still at its default, so "
                                 "all of them were saved. Change something on the node first "
                                 "if you want a look that differs from the default." % sec)
            if recipe:
                sections.setdefault(sec, {}).update(recipe)
        shared = base.get("all") if isinstance(base.get("all"), dict) else None
        look_name = (name or "").strip() or str(base.get("name") or "").strip()
        desc = (description or "").strip() or str(base.get("description") or base.get("desc") or "").strip()
        lookup = {l["name"]: l for l in styles.all_looks()[0]}
        added = False
        folder = (save_folder or "").strip()
        ok, msg, path, problems = userlooks.save_look(
            look_name, desc, sections, str(base.get("extends") or ""), shared,
            bool(overwrite), folder or None, lookup)
        if ok and folder:                 # remember the folder only after a good save
            added = userlooks.add_dir_to_config(folder)
        lines = [msg] + notes
        if ok:
            lines.append("It will appear in the Style node as '%s' (a sub-folder shows as a sub-menu). Press R in "
                         "ComfyUI to refresh the list." % userlooks.display_name(path, look_name))
            if added:
                lines.append("Folder remembered in looks_folder.txt.")
        lines += problems
        info = "\n".join(lines)
        print("[ApoDesign] Save Look: " + info.splitlines()[0])
        return (info,)


NODE_CLASS_MAPPINGS = {"ApoDesign_SaveLook": ApoDesignSaveLook}
NODE_DISPLAY_NAME_MAPPINGS = {"ApoDesign_SaveLook": "ApoDesign Save Look"}
