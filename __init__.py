"""ApoDesign - retro graphic styles for ComfyUI. No dependencies beyond ComfyUI."""
from .nodes.ascii_art import NODE_CLASS_MAPPINGS as _ascii_nodes
from .nodes.ascii_art import NODE_DISPLAY_NAME_MAPPINGS as _ascii_names
from .nodes.bitmap import NODE_CLASS_MAPPINGS as _bitmap_nodes
from .nodes.bitmap import NODE_DISPLAY_NAME_MAPPINGS as _bitmap_names
from .nodes.pixel_art import NODE_CLASS_MAPPINGS as _pixel_nodes
from .nodes.pixel_art import NODE_DISPLAY_NAME_MAPPINGS as _pixel_names
from .nodes.palette import NODE_CLASS_MAPPINGS as _palette_nodes
from .nodes.palette import NODE_DISPLAY_NAME_MAPPINGS as _palette_names
from .nodes.save_look import NODE_CLASS_MAPPINGS as _save_nodes
from .nodes.save_look import NODE_DISPLAY_NAME_MAPPINGS as _save_names
from .nodes.style import NODE_CLASS_MAPPINGS as _style_nodes
from .nodes.style import NODE_DISPLAY_NAME_MAPPINGS as _style_names

NODE_CLASS_MAPPINGS = {**_bitmap_nodes, **_ascii_nodes, **_pixel_nodes,
                       **_style_nodes, **_palette_nodes, **_save_nodes}
NODE_DISPLAY_NAME_MAPPINGS = {**_bitmap_names, **_ascii_names, **_pixel_names,
                               **_style_names, **_palette_names, **_save_names}

# The banner (GitHub / Discord icons and the node name) is a small browser-side
# script in web/ with its font built in. Cosmetic only: the nodes work the same
# without it.
WEB_DIRECTORY = "./web"


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
