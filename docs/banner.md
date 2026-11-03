# The banner

Every ApoDesign node has a slim banner at the top: a GitHub icon, a Discord icon and the node's name in the Bitcount Ink font. It is cosmetic only: it adds no inputs, saves nothing into workflows, and the nodes work the same if it fails to load.

It lives in `web/apodesign_banner.js` (the browser side) and loads through `WEB_DIRECTORY = "./web"` in `__init__.py`. The font is embedded in `web/apodesign_font.js` as base64, so nothing needs installing and ComfyUI's file rules are not an issue.

## Changing it

The top of `web/apodesign_banner.js` holds the things you may want to change: the two links (`LINKS`), the name colour, bar colour, bar height, font size, and the table of node names. After a change press **F5** in the browser; no ComfyUI restart is needed for JavaScript.

## Font licence

Bitcount Ink is released under the SIL Open Font License 1.1. Its licence text is in `web/fonts/OFL.txt` and it is credited in `NOTICE`.
