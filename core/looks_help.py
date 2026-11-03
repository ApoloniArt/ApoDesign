"""Writes the instructions an LLM needs to create look files. Pure Python."""
from . import styles, userlooks
from .palettes import PRESETS


def _short(tip):
    tip = " ".join((tip or "").split())
    cut = tip.find(". ")
    tip = tip[:cut + 1] if 0 < cut < 170 else tip
    return tip if len(tip) <= 170 else tip[:167] + "..."


def _rng(s):
    if s.kind == "combo":
        return "one of: " + ", ".join(s.choices)
    if s.kind in ("int", "float"):
        return "%s to %s" % (s.min, s.max)
    return "true/false" if s.kind == "bool" else "text"


def llm_prompt():
    out = []
    w = out.append
    w("You create \"look\" files for ApoDesign, ComfyUI nodes that turn images and video into retro")
    w("styles: Bitmap (1-bit and dithered art), Ascii (text art) and Pixel Art.")
    w("")
    w("Reply with ONE JSON object and nothing else (no explanation, no code fence).")
    w("")
    w("FORMAT")
    w("{")
    w("  \"name\": \"Short name\",")
    w("  \"description\": \"One sentence.\",")
    w("  \"extends\": \"Optional: the name of an existing look to start from\",")
    w("  \"all\": { widgets that mean the same in every node, e.g. palette_preset },")
    w("  \"bitmap\": { ... },")
    w("  \"ascii\": { ... },")
    w("  \"pixel_art\": { ... }")
    w("}")
    w("")
    w("RULES")
    w("- Use only the widget names and values listed below. Leave out anything you do not want to")
    w("  change: unlisted widgets keep their defaults. Out-of-range numbers are clamped.")
    w("- Always give all three sections (or use \"all\") so the look works in every node and feels the same.")
    w("- Colours are #rrggbb. custom_palette is a comma-separated list of 2 to 64 colours, for example")
    w("  \"#0f380f,#306230,#8bac0f,#9bbc0f\". palette_preset names a ready-made palette; if you use")
    w("  custom_palette, leave palette_preset alone: a custom palette wins.")
    w("- One-hue palettes (dark to light of the same colour): color_mode \"tonal\" (Bitmap/Ascii) or match \"tone\"")
    w("  (Pixel Art). Multi-colour palettes: color_mode \"palette\" and match \"colour\".")
    w("- For animation and video prefer the steady methods bayer, blue_noise, halftone_dots,")
    w("  halftone_lines, threshold. floyd_steinberg, atkinson, sierra, sierra_lite, stucki, jarvis,")
    w("  burkes are organic but shimmer a little between frames.")
    w("- Size: pixel_size (bigger = chunkier) or target_width (pixels across; wins over pixel_size).")
    w("  Ascii: columns (fewer = chunkier).")
    w("- Words like \"retro\", \"console\", \"newspaper\", \"CRT\", \"comic\" suggest: palette, size, method.")
    w("")
    w("EXAMPLE")
    w("{")
    w("  \"name\": \"Neon arcade\",")
    w("  \"description\": \"Bright 16-colour arcade look with clean steady dithering.\",")
    w("  \"all\": {\"palette_preset\": \"pico8\"},")
    w("  \"bitmap\": {\"method\": \"bayer\", \"bayer_size\": \"4\", \"target_width\": 200, \"color_mode\": \"palette\"},")
    w("  \"ascii\": {\"columns\": 110, \"charset\": \"standard\", \"color_mode\": \"palette\"},")
    w("  \"pixel_art\": {\"target_width\": 200, \"match\": \"colour\", \"outline\": \"dark\"}")
    w("}")
    w("")
    w("EXISTING LOOKS you can name in \"extends\":")
    w(", ".join(styles.LOOK_NAMES))
    w("")
    w("PALETTE PRESETS (palette_preset):")
    w(", ".join(list(PRESETS) + ["adaptive_kmeans (colours taken from the picture; set palette_size)",
                                  "ink_paper (two colours: ink_color and paper_color)"]))
    w("")
    w("WIDGETS (name - allowed values - default - what it does)")
    for sec, title in (("bitmap", "bitmap"), ("ascii", "ascii"), ("pixel_art", "pixel_art")):
        w("")
        w("[%s]" % title)
        for s in styles.ALL_SPECS[sec]:
            if not s.promptable or s.name in userlooks.NOT_SAVED or s.name == "palette_preset":
                continue
            w("- %s - %s - default %s - %s" % (s.name, _rng(s), s.default, _short(s.tip)))
    w("")
    return "\n".join(out)


if __name__ == "__main__":
    print(llm_prompt())
