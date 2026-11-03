# ApoDesign Bitmap

Turns any image (or batch / video frames) into dithered or halftone bitmap art: the Mac Plus, Game Boy and print-engraving look.
![ApoDesign]([assets/bitmap1.jpg)

## Look and size
| Widget | What it does |
|---|---|
| `method` | `bayer`, `blue_noise`, `halftone_dots`, `halftone_lines`, `threshold` (ordered, steady on video) or `floyd_steinberg`, `atkinson`, `sierra`, `sierra_lite`, `stucki`, `jarvis`, `burkes` (error diffusion, organic but shimmers slightly on video) |
| `bayer_size` | 2 / 4 / 8 / 16. Small = coarse, large = smooth |
| `pixel_size` | Chunky pixel size in source pixels |
| `target_width` | Pixels across instead (0 = off). Allows non-integer scaling, e.g. 256 across 1920 |
| `output_scale` | Extra whole-number crisp enlargement |
| `halftone_cell`, `halftone_angle` | Screen spacing and angle for the halftone methods |
| `dither_strength` | 0 = plain posterize, 1 = normal, above 1 = harsher |

## Colour: black & white, colour, or any mix
| Widget | What it does |
|---|---|
| `palette_preset` | `ink_paper` (your two colours), `adaptive_kmeans` (palette from your image), or Game Boy, mint_plum, ice_blue, newspaper, sepia, amber_crt, green_phosphor, virtual_boy, CGA, EGA, C64, PICO-8 |
| `ink_color`, `paper_color` | The two colours for `ink_paper`. Swap them for a negative look |
| `custom_palette` | Paste hex codes: `#0f380f,#306230,#8bac0f`. Overrides the preset |
| `color_mode` | `tonal` = brightness dithered through the palette (classic 1-bit / duotone). `palette` = picture colours matched to the palette. `channels` = R, G, B dithered separately (true colour dither) |
| `color_mix` + `mix_mode` | Blend the colour result over the tonal one by region: `highlights`, `shadows`, `saturation`, `edges_mono`, `edges_colour`, `centre`, or `mask` (connect a MASK) |

Example: *B&W shadows, colour highlights* = `palette_preset` black_white, `color_mode` channels, `mix_mode` highlights, `color_mix` 0.5.

## Prompting
- **`style_prompt`**: plain English, no LLM needed. `gameboy palette, atkinson dither, 96 wide, high contrast` or `dark purple on mint, bayer 4, chunky`. The `settings` output shows exactly what it resolved to.
- **`style_json`** (optional input): JSON with widget names, e.g. from an LM Studio / LLM node: `{"method":"stucki","palette_preset":"c64","pixel_size":4}`. Always wins.
- `prompt_priority`: `prompt` = the prompt overrides widgets; `widgets` = it only fills widgets left at default.

## Outputs
`image` (final), `lowres` (the true 1:1 pixel grid), `ink_mask`, `palette` (hex string), `settings` (JSON of everything used).

`ink_mask` is only filled in when the `ink_mask_output` widget is on. Off (the default), it is plain black and costs no memory.

## Video and batches
Ordered methods use a fixed pattern locked to the pixel grid, so frames don't shimmer. A k-means palette is computed once across the whole batch. Error diffusion works per frame, so it is more organic but may shimmer slightly in motion. Frames are processed in chunks of 8, so long clips don't exhaust VRAM; if the GPU runs out of memory the node retries on the CPU.
