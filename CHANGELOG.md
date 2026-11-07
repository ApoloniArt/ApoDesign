# Changelog

Newest first.

## 0.7.5
- New in the Ascii node: **text_order**. Off by default. `in_order` fills the inked cells with your own text, one letter after another in reading order, so the words can be read (for example LEST WE FORGET on a silhouette). `in_order_per_row` starts the text again on every row. Set the words in `order_text` (it repeats) and how much of the picture gets letters with `order_threshold`. Works with ramp and shape modes, respects a transparency mask, and the `text` output holds the same lettering. The three new widgets are at the bottom of the node, so workflows saved before 0.7.5 keep their values.

## 0.7.4
- Fixed (for real): the node fields still shifted after switching ComfyUI tabs, reloading the page or copy/paste (values on the wrong widgets, NaN, null, empty, workflow would not run). Cause: the banner was marked "do not save", so ComfyUI saved the values counting the banner but restored them skipping it. The banner now takes part in saving like every other widget (it is still never sent to ComfyUI when you run), so saving and restoring agree and nothing depends on a patch. A small check still puts values back by position as a safety net. **Workflows saved while the problem was showing contain wrong values: add the nodes fresh (or reopen an earlier save) and set them again.**

## 0.7.3
- Fixed: after switching ComfyUI tabs (or copy/paste, or reloading a workflow) the node fields were shifted by one: values landed on the wrong widgets, some became NaN, null or empty, and the workflow would not run. The banner now puts every saved value back on the right widget. Workflows that were saved while the problem was showing keep their wrong values and need to be set again.
- Fixed: the Bitcount Ink font did not show on newer ComfyUI versions, which block fonts embedded in the page. The font is now loaded from its file in `web/fonts` (the embedded copy stays as a fallback).

## 0.7.2
- `looks_folder.txt` is no longer shipped (it is yours and is ignored by Git); `looks_folder.example.txt` shows the format.
- Banner polish: spacing and font size match ApoGalleria exactly; the Style, Palette and Save Look banners sit the same distance above the first field as on the three render nodes.

## 0.7.1
- The banner font is built into the page script (no separate font download); removed the font route from `__init__.py`.
- Removed the extra tags on the right of each banner; the node name is centred.

## 0.7
- New: a banner at the top of every ApoDesign node with GitHub and Discord icons and the node name in Bitcount Ink (cosmetic only).
- Bitcount Ink (SIL OFL) bundled; the licence text ships with it.

## 0.6.5
- Sub-folders of a listed looks folder are sub-menus in the Style list.
- Two built-in look names that contained "/" were renamed to "CGA (cyan, magenta)" and "CGA (red, green, yellow)" so they no longer turn into menus.

## 0.6.4
- Every folder listed in `looks_folder.txt` is a menu named after it in the Style list.

## 0.6.1 to 0.6.3
- A bare folder name typed into Save Look (for example `test1`) becomes a sub-folder of the looks folder instead of landing in ComfyUI's own start folder.
- A look is no longer listed twice when its folder is inside the looks folder.
- Save Look adds a folder to `looks_folder.txt` only after a successful save.
- Save Look saves a node whose settings are all still at their defaults (it used to say "Nothing to save") and explains it.

## 0.6
- New: your own looks. **ApoDesign Save Look** node, a `looks/` folder, `looks_folder.txt` for folders outside ApoDesign, an LLM system prompt (`looks/_LLM_system_prompt.txt`) and example looks.
- Ascii skips characters a font cannot draw (no empty boxes with custom fonts) and prints a console note when a font falls back.

## 0.5.1 and 0.5
- New: the **Style** node with 47 built-in looks, each with a recipe for all three render nodes.
- New: the **Palette** node (preset, hex list, from image, gradient, harmony).
- Seven new classic palettes: zx_spectrum, nes, apple_ii, msx, amstrad_cpc, teletext, sweetie16.

## 0.4.1
- The `alpha` output is also filled in `rgba` mode, so Join Image with Alpha works in either mode.
- New `invert_mask` widget for loaders whose mask is the other way round.

## 0.4
- Transparency: PNGs with an alpha channel keep it in all three nodes. Pixel Art gets a `mask` input.

## 0.3
- New: the **Pixel Art** node.

## 0.2
- New: the **Ascii** node.
- Lower memory use in Bitmap; `RUN_TESTS.bat`.

## 0.1
- First release: the **Bitmap** node.
