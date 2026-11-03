ApoDesign - your own looks
==========================

Put look files (*.json) in this folder and they appear at the end of the
ApoDesign Style node's list, marked with a star. Press R in ComfyUI to
refresh the list (no restart needed).

Three ways to make a look
  1. In ComfyUI: tune a Bitmap / Ascii / Pixel Art node, then connect its
     "settings" output to an "ApoDesign Save Look" node (give it a name, run).
  2. Ask an LLM: give it the text of _LLM_system_prompt.txt as its system
     prompt, describe the look in plain words, and paste its reply into
     Save Look's look_json box (or save the reply as a .json file here).
  3. Write one by hand: copy a file from the _examples folder.

Keeping your looks safe when you update ApoDesign
  Put them in a folder of your own and list that folder in
  looks_folder.txt (next to the nodes' __init__.py; create it, or let Save Look create
  it). Then updating ApoDesign
  can never touch them.

Rules
  - Every folder you list in looks_folder.txt becomes a menu named after
    it in the Style node's list, and its sub-folders become sub-menus: a look
    in D:\\MyLooks\\Arcade shows as "* MyLooks > Arcade > Look name". (Inside
    the built-in looks folder, its sub-folders are the menus.)
  - Files and folders starting with _ or . are ignored (that is why the
    examples do not show up in the list until you copy them out).
  - A look with a mistake still loads; the mistake is skipped and reported in
    the Style node's info output.
  - "extends" starts from another look (built-in or yours); "all" sets
    widgets for every node that has them; "bitmap", "ascii" and "pixel_art"
    set widgets for one node.
