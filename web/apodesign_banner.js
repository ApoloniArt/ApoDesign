// ApoDesign: a slim banner at the top of every ApoDesign node, with GitHub and
// Discord icons and the node's name. Purely cosmetic: it adds no inputs, sends
// nothing to ComfyUI, and the nodes work the same if this file fails.
import { app } from "../../scripts/app.js";
import { FONT_DATA } from "./apodesign_font.js";

// ---- things you may want to change ---------------------------------------
const LINKS = {
  github:  { url: "https://github.com/ApoloniArt",     tip: "ApoloniArt on GitHub" },
  discord: { url: "https://discord.gg/XDExAUzuZp",     tip: "Join the Discord" },
};
const TITLE_COLOR = "#a78bfa";   // node name colour (same as ApoGalleria)
const BAR_COLOR   = "#1a1a1a";   // banner background (same as ApoGalleria)
const BAR_HEIGHT  = 26;          // pixels
const FONT_SIZE   = 19.5;        // pixels (same as ApoGalleria)
const NODES = {                  // node class -> [name shown, first widget below is a text box?]
  ApoDesign_Bitmap:   ["ApoDesign - Bitmap",    true],
  ApoDesign_Ascii:    ["ApoDesign - Ascii",     true],
  ApoDesign_PixelArt: ["ApoDesign - Pixel Art", true],
  ApoDesign_Style:    ["ApoDesign - Style",     false],
  ApoDesign_Palette:  ["ApoDesign - Palette",   false],
  ApoDesign_SaveLook: ["ApoDesign - Save Look", false],
};
// ---------------------------------------------------------------------------

// Height reserved for the banner. Nodes whose first widget below it is a text
// box (Bitmap, Ascii, Pixel Art) are laid out by ComfyUI with this height as it
// is; the other nodes need a few more pixels to get the same gap.
const SLOT_TEXT  = BAR_HEIGHT + 4;
const SLOT_OTHER = BAR_HEIGHT + 9;
const CHAR_WIDTH = 11.8;         // approx. width of one banner character at FONT_SIZE 19.5
const SIDE_ROOM  = 130;          // icons on the left + the same room on the right + margins

// The font is loaded from a file next to this script (same origin as ComfyUI, so
// the browser's content security policy allows it); the copy embedded in
// apodesign_font.js is only a fallback, because newer ComfyUI versions block
// fonts embedded in the page itself.
const FONT_URL = new URL("./fonts/BitcountInk-500.woff2", import.meta.url).href;

const ICONS = {
  github: `<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>`,
  discord: `<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M13.5 3.2A13 13 0 0 0 10.4 2.2c-.14.25-.3.6-.4.86a12 12 0 0 0-3.6 0c-.1-.27-.27-.61-.4-.86a13 13 0 0 0-3.1 1c-2 2.9-2.5 5.8-2.3 8.6a13 13 0 0 0 3.9 2c.32-.43.6-.9.83-1.4-.46-.17-.9-.38-1.3-.63.1-.08.22-.16.32-.25 2.5 1.15 5.2 1.15 7.7 0 .1.09.2.17.32.25-.4.25-.85.46-1.3.63.23.5.5.97.83 1.4a13 13 0 0 0 3.9-2c.24-3.2-.6-6.1-2.6-8.6zM5.85 10.1c-.77 0-1.4-.7-1.4-1.55 0-.86.6-1.56 1.4-1.56.8 0 1.42.71 1.4 1.56 0 .85-.6 1.55-1.4 1.55zm4.3 0c-.77 0-1.4-.7-1.4-1.55 0-.86.6-1.56 1.4-1.56.8 0 1.42.71 1.4 1.56 0 .85-.6 1.55-1.4 1.55z"/></svg>`,
};

function injectStyle() {
  if (document.getElementById("apodesign-banner-style")) return;
  const css = `
@font-face { font-family: "Bitcount Ink"; src: url("${FONT_URL}") format("woff2"), url("${FONT_DATA}") format("woff2");
  font-weight: 500; font-style: normal; font-display: block; }
.apod-banner { box-sizing: border-box; position: relative; width: 100%; height: ${BAR_HEIGHT}px;
  display: flex; align-items: center; justify-content: center; padding: 0 56px;
  background: ${BAR_COLOR}; border-radius: 6px; overflow: hidden; user-select: none; }
.apod-banner .apod-icons { position: absolute; left: 6px; top: 0; bottom: 0; display: flex;
  align-items: center; gap: 2px; }
.apod-banner a { display: flex; align-items: center; justify-content: center; color: #888;
  flex-shrink: 0; padding: 4px; border-radius: 4px; cursor: pointer; transition: color 0.15s, background 0.15s; }
.apod-banner a:hover { color: #a78bfa; background: rgba(167, 139, 250, 0.12); }
.apod-banner .apod-title { flex: 1; min-width: 0; text-align: center; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; pointer-events: none;
  font-family: "Bitcount Ink", "Courier New", monospace; font-size: ${FONT_SIZE}px;
  font-variation-settings: "wght" 500; line-height: 1.2; color: ${TITLE_COLOR}; }`;
  const el = document.createElement("style");
  el.id = "apodesign-banner-style";
  el.textContent = css;
  document.head.appendChild(el);
}

function makeBanner(name) {
  const bar = document.createElement("div");
  bar.className = "apod-banner";
  const icons = document.createElement("div");
  icons.className = "apod-icons";
  for (const key of ["github", "discord"]) {
    const a = document.createElement("a");
    a.className = "apod-" + key;
    a.href = LINKS[key].url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.title = LINKS[key].tip;
    a.innerHTML = ICONS[key];
    // a click must open the link, not drag or select the node
    a.addEventListener("pointerdown", (e) => e.stopPropagation());
    icons.appendChild(a);
  }
  const title = document.createElement("div");
  title.className = "apod-title";
  title.textContent = name;
  bar.append(icons, title);
  return bar;
}

function fitNode(node, minWidth) {
  try {
    const need = node.computeSize();
    const w = Math.max(node.size[0], need[0], minWidth || 0);
    const h = Math.max(node.size[1], need[1]);
    if (w !== node.size[0] || h !== node.size[1]) node.setSize([w, h]);
  } catch (e) { /* cosmetic only */ }
}

app.registerExtension({
  name: "ApoDesign.Banner",
  nodeCreated(node) {
    try {
      const info = NODES[node.comfyClass];
      if (!info || typeof node.addDOMWidget !== "function") return;
      if ((node.widgets || []).some((w) => w.name === "apodesign_banner")) return;
      const [name, belowIsTextBox] = info;
      const slot = belowIsTextBox ? SLOT_TEXT : SLOT_OTHER;
      const minWidth = Math.ceil(name.length * CHAR_WIDTH + SIDE_ROOM);
      injectStyle();
      const widget = node.addDOMWidget("apodesign_banner", "apodesign_banner", makeBanner(name), {
        serialize: false,        // keep it out of the prompt sent to ComfyUI (same as ComfyUI's own seed control)
        hideOnZoom: false,
        getMinHeight: () => slot,
        getMaxHeight: () => slot,
        getHeight: () => slot,
      });
      // IMPORTANT: the banner must take part in the saved widget list like every
      // other widget. ComfyUI saves values by position (the banner is position 0)
      // but, if the banner were marked "do not serialize", it restores them
      // skipping the banner, so every field gets its neighbour's value after a
      // tab switch, copy/paste or reload (NaN, null, empty fields). Keeping the
      // banner in the list makes saving and restoring agree. It is kept out of
      // the prompt by serializeValue below, so ComfyUI never receives it.
      widget.serialize = true;
      widget.serializeValue = () => undefined;
      if (!belowIsTextBox) {
        // widgets drawn by ComfyUI itself (not text boxes) sit straight under the
        // banner: tell every layout method the same height
        widget.computeSize = (width) => [width || 0, slot];
        widget.computeLayoutSize = () => ({ minHeight: slot, maxHeight: slot, minWidth: 0 });
        widget.computedHeight = slot;
      }
      // put the banner first (addDOMWidget adds it last)
      const i = node.widgets.indexOf(widget);
      if (i > 0) { node.widgets.splice(i, 1); node.widgets.unshift(widget); }
      // Safety net: every list saved with the banner (this version, and 0.7.0-0.7.3)
      // has one entry per widget, banner first. If ComfyUI put the values on the
      // wrong widgets, put each one back by its position.
      const reapply = (saved) => {
        try {
          const vals = saved && saved.widgets_values;
          const all = node.widgets || [];
          if (!Array.isArray(vals) || vals.length < all.length) return;
          all.forEach((w, k) => {
            if (w === widget) return;
            const v = vals[k];
            if (v !== undefined && v !== null && w.value !== v) w.value = v;
          });
        } catch (e) { console.warn("[ApoDesign] value check skipped:", e); }
      };
      // saved workflows keep their old node size: make room for the banner
      const oldConfigure = node.onConfigure;
      node.onConfigure = function (saved) {
        const r = oldConfigure ? oldConfigure.apply(this, arguments) : undefined;
        reapply(saved);
        requestAnimationFrame(() => { reapply(saved); fitNode(this, minWidth); });
        return r;
      };
      requestAnimationFrame(() => fitNode(node, minWidth));
    } catch (e) {
      console.warn("[ApoDesign] banner skipped:", e);
    }
  },
});
