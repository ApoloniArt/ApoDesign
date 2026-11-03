# Widget reference

Generated from the code, so it always matches the nodes. Every widget below can also be set from `style_prompt`, `style_json`, a Style-node look or your own look file, using the widget's name.

## ApoDesign Bitmap

| Widget | Type | Default | Range / choices | What it does |
|---|---|---|---|---|
| `style_prompt` | string | (empty) |  | Optional plain-English style, e.g. 'gameboy palette, atkinson dither, 96 wide, high contrast'. Sets the widgets below. |
| `prompt_priority` | combo | `prompt` | `prompt`, `widgets` | prompt: the style prompt overrides the widgets. widgets: the prompt only fills widgets you left at their defaults. |
| `method` | combo | `bayer` | `bayer`, `blue_noise`, `floyd_steinberg`, `atkinson`, `sierra`, `sierra_lite`, `stucki`, `jarvis`, `burkes`, `halftone_dots`, `halftone_lines`, `threshold` | bayer / blue_noise / halftone_* / threshold are ordered and perfectly steady across video frames. The error-diffusion methods (floyd_steinberg ... burkes) look organic but shimmer slightly between frames. |
| `bayer_size` | combo | `8` | `2`, `4`, `8`, `16` | Matrix size for the bayer method. 2 and 4 are coarse and crunchy, 8 and 16 are smooth. |
| `pixel_size` | int | `3` | 1 to 128 | Size of each chunky pixel, in source pixels. |
| `target_width` | int | `0` | 0 to 4096 | Alternative to pixel_size: the number of pixels across the image (0 = off). Allows non-integer scaling, e.g. 256 across a 1920 image. |
| `output_scale` | int | `1` | 1 to 8 | Extra whole-number enlargement of the final image, always crisp nearest-neighbour. |
| `palette_preset` | combo | `ink_paper` | `ink_paper`, `adaptive_kmeans`, `black_white`, `grey_4`, `gameboy`, `mint_plum`, `ice_blue`, `newspaper`, `sepia`, `amber_crt`, `green_phosphor`, `virtual_boy`, `cga_pal1`, `cga_pal0`, `ega`, `c64`, `pico8`, `zx_spectrum`, `nes`, `apple_ii`, `msx`, `amstrad_cpc`, `teletext`, `sweetie16` | ink_paper uses the two colours below. adaptive_kmeans builds a palette from your image (shared by every frame of a batch). The rest are classic palettes. |
| `ink_color` | string | `#000000` |  | Dark colour (hex) for palette_preset = ink_paper. |
| `paper_color` | string | `#ffffff` |  | Light colour (hex) for palette_preset = ink_paper. Swap ink and paper for a negative look. |
| `custom_palette` | string | (empty) |  | Your own palette as hex codes, e.g. #0f380f,#306230,#8bac0f. Overrides the preset when it holds 2 or more colours. |
| `palette_size` | int | `4` | 2 to 32 | Number of colours for palette_preset = adaptive_kmeans. |
| `color_mode` | combo | `tonal` | `tonal`, `palette`, `channels` | tonal: brightness is dithered through the palette (classic 1-bit / duotone look). palette: colours are matched to the palette, keeping the picture's hues. channels: red, green and blue are dithered separately (true colour dither). |
| `color_levels` | int | `2` | 2 to 16 | Levels per channel when color_mode = channels (2 = 8 colours). |
| `color_mix` | float | `1.0` | 0.0 to 1.0 | How much of the colour layer (palette / channels) is mixed over the tonal layer. 0 = pure tonal. Ignored in tonal mode. |
| `mix_mode` | combo | `global` | `global`, `highlights`, `shadows`, `saturation`, `edges_mono`, `edges_colour`, `centre`, `mask` | Where colour shows when color_mix is below 1: highlights, shadows, saturated areas, edges_mono (mono line work over colour), edges_colour, centre, or a MASK you connect. |
| `dither_strength` | float | `1.0` | 0.0 to 2.0 | Strength of the dither pattern. 0 = plain posterize. For error diffusion it scales how much error is passed on. |
| `halftone_cell` | int | `6` | 2 to 64 | Dot or line spacing for halftone methods, measured in grid pixels (use pixel_size 1 for smooth dots). |
| `halftone_angle` | float | `45.0` | 0.0 to 90.0 | Screen angle for halftone methods. |
| `brightness` | float | `0.0` | -1.0 to 1.0 | Brightness before dithering. |
| `contrast` | float | `1.0` | 0.0 to 4.0 | Contrast before dithering. |
| `gamma` | float | `1.0` | 0.1 to 4.0 | Midtone curve. Above 1 brightens the midtones. |
| `sharpen` | float | `0.0` | 0.0 to 4.0 | Sharpen before dithering, so fine detail survives. |
| `local_contrast` | float | `0.0` | 0.0 to 2.0 | Local contrast boost (CLAHE-style) so shadows and highlights keep their structure. |
| `invert` | bool | `False` |  | Invert the picture before dithering. |
| `ink_mask_output` | bool | `False` |  | Off: the ink_mask output is plain black and uses no memory. On: it holds the ink coverage (white where there is ink). Leave off unless you connect ink_mask; it saves about a third of the node's memory on long videos. |
| `transparency` | combo | `rgba` | `rgba`, `separate`, `off` | What to do when the connected mask makes parts of the picture transparent (white = transparent, as core Load Image outputs it). rgba: the image output carries its own alpha channel, so Preview and Save Image show / write real transparency - do NOT add Join Image with Alpha. separate: the image stays plain RGB (transparent areas black) and the alpha output holds the transparency, for Join Image with Alpha or video. off: ignore the mask. An all-opaque mask is ignored automatically. |
| `invert_mask` | bool | `False` |  | Turn on if the transparency comes out the wrong way round (the subject vanishes and the background stays). Some loaders output white = opaque instead of white = transparent. |

## ApoDesign Ascii

| Widget | Type | Default | Range / choices | What it does |
|---|---|---|---|---|
| `style_prompt` | string | (empty) |  | Optional plain-English style, e.g. 'braille, 160 columns, green phosphor' or 'dense characters, edges, colour'. Sets the widgets below. |
| `prompt_priority` | combo | `prompt` | `prompt`, `widgets` | prompt: the style prompt overrides the widgets. widgets: the prompt only fills widgets you left at their defaults. |
| `glyph_match` | combo | `ramp` | `ramp`, `shape`, `braille` | ramp: brightness picks the character, like classic ASCII art. shape: each cell gets the character whose SHAPE best matches the picture there, so edges follow the drawing (try it with the standard or quadrants charset). braille: 2x4 dots per cell, the finest detail. |
| `charset` | combo | `standard` | `classic`, `standard`, `simple`, `blocks`, `quadrants`, `binary`, `letters`, `custom` | Which characters may be used (ramp and shape modes). standard is the 70-character ramp; blocks and quadrants give a chunky mosaic look; custom uses custom_charset. |
| `custom_charset` | string | (empty) |  | Your own characters for charset = custom, e.g. ' .oO0@'. Include a space for the darkest cells. |
| `columns` | int | `120` | 8 to 1000 | Number of characters across. More = finer detail. |
| `cell_aspect` | float | `2.0` | 1.0 to 3.0 | Height of a character cell divided by its width. 2.0 suits most monospace fonts. |
| `output_scale` | int | `1` | 1 to 4 | Whole-number enlargement of the final image. Characters are drawn fresh at the larger size, so they stay sharp. |
| `font` | combo | `builtin` | `builtin`, `consolas`, `courier_new`, `lucida_console`, `custom_file` | builtin is DejaVu Sans Mono, bundled with ApoDesign. The others are used if installed on this computer, otherwise builtin is used. custom_file uses font_file. |
| `font_file` | string | (empty) |  | Full path to a .ttf / .otf monospace font, for font = custom_file. |
| `font_bold` | bool | `False` |  | Use the bold weight of the font. |
| `glyph_style` | combo | `smooth` | `smooth`, `crisp` | smooth: anti-aliased characters. crisp: hard-edged, bitmap-font look. |
| `method` | combo | `none` | `none`, `bayer`, `blue_noise`, `floyd_steinberg`, `atkinson`, `sierra`, `sierra_lite`, `stucki`, `jarvis`, `burkes` | Dithering of the character choice (and of colours). none is clean classic ASCII. bayer / blue_noise are steady on video; the error-diffusion methods look organic but shimmer slightly between frames. |
| `bayer_size` | combo | `8` | `2`, `4`, `8`, `16` | Matrix size for the bayer method. |
| `dither_strength` | float | `1.0` | 0.0 to 2.0 | Strength of the dithering. 0 = plain nearest character. |
| `edge_strength` | float | `0.0` | 0.0 to 1.0 | Ramp mode only: draw \| / - \ along strong edges, so outlines read as line work. 0 = off. |
| `polarity` | combo | `light_on_dark` | `light_on_dark`, `dark_on_light` | light_on_dark: bright characters on a dark page (terminal look), bright picture areas get dense characters. dark_on_light: ink on paper, dark areas get dense characters. |
| `palette_preset` | combo | `ink_paper` | `ink_paper`, `adaptive_kmeans`, `black_white`, `grey_4`, `gameboy`, `mint_plum`, `ice_blue`, `newspaper`, `sepia`, `amber_crt`, `green_phosphor`, `virtual_boy`, `cga_pal1`, `cga_pal0`, `ega`, `c64`, `pico8`, `zx_spectrum`, `nes`, `apple_ii`, `msx`, `amstrad_cpc`, `teletext`, `sweetie16` | Colours of the page and characters. The darkest palette colour and the lightest one become page and ink (see polarity). adaptive_kmeans builds a palette from your image. |
| `ink_color` | string | `#000000` |  | One of the two colours for palette_preset = ink_paper. |
| `paper_color` | string | `#ffffff` |  | The other colour for ink_paper. polarity decides which one is the page and which one the characters. |
| `custom_palette` | string | (empty) |  | Your own palette as hex codes, e.g. #0f380f,#306230,#8bac0f. Overrides the preset when it holds 2 or more colours. |
| `palette_size` | int | `4` | 2 to 32 | Number of colours for palette_preset = adaptive_kmeans. |
| `color_mode` | combo | `tonal` | `tonal`, `palette`, `channels` | tonal: one ink colour on one page colour. palette: every character takes the nearest palette colour to the picture. channels: every character takes the picture's own colour (quantised to color_levels per channel). |
| `color_levels` | int | `4` | 2 to 16 | Levels per channel when color_mode = channels. 2 = 8 colours, 4 = 64, 16 = 4096. |
| `color_mix` | float | `1.0` | 0.0 to 1.0 | How much colour is mixed over the plain ink colour. 0 = none. |
| `mix_mode` | combo | `global` | `global`, `highlights`, `shadows`, `saturation`, `edges_mono`, `edges_colour`, `centre`, `mask` | Where colour shows when color_mix is below 1: highlights, shadows, saturated areas, edges_mono, edges_colour, centre, or a MASK you connect. |
| `color_boost` | float | `0.5` | 0.0 to 1.0 | channels mode on a dark page: brightens each character's colour to full vividness, because the character's density already carries the brightness. 0 = true colour. |
| `background` | combo | `paper` | `paper`, `tint` | paper: plain page colour behind every character. tint: the page takes a faint shade of the cell's colour. |
| `bg_tint` | float | `0.2` | 0.0 to 1.0 | How strongly the page takes the cell colour when background = tint. |
| `brightness` | float | `0.0` | -1.0 to 1.0 | Brightness before conversion. |
| `contrast` | float | `1.0` | 0.0 to 4.0 | Contrast before conversion. |
| `gamma` | float | `1.0` | 0.1 to 4.0 | Midtone curve. Above 1 brightens the midtones. |
| `sharpen` | float | `0.0` | 0.0 to 4.0 | Sharpen before conversion, so fine detail survives. |
| `local_contrast` | float | `0.0` | 0.0 to 2.0 | Local contrast boost so shadows and highlights keep structure. |
| `invert` | bool | `False` |  | Invert the picture before conversion. |
| `text_frame` | int | `0` | -1 to 100000 | Which frame to put in the text output (0 = first). -1 = every frame, separated by a line containing only a form feed. |
| `glyph_mask_output` | bool | `False` |  | Off: the glyph_mask output is plain black and uses no memory. On: it holds the characters' coverage (white where there is ink). Leave off unless you connect glyph_mask. |
| `transparency` | combo | `rgba` | `rgba`, `separate`, `off` | What to do when the connected mask makes parts of the picture transparent (white = transparent, as core Load Image outputs it). rgba: the image output carries its own alpha channel, so Preview and Save Image show / write real transparency - do NOT add Join Image with Alpha. separate: the image stays plain RGB (transparent areas black) and the alpha output holds the transparency, for Join Image with Alpha or video. off: ignore the mask. An all-opaque mask is ignored automatically. |
| `invert_mask` | bool | `False` |  | Turn on if the transparency comes out the wrong way round (the subject vanishes and the background stays). Some loaders output white = opaque instead of white = transparent. |

## ApoDesign Pixel Art

| Widget | Type | Default | Range / choices | What it does |
|---|---|---|---|---|
| `style_prompt` | string | (empty) |  | Optional plain-English style, e.g. '24 colours, outline, 160 wide, painterly'. Sets the widgets below. |
| `prompt_priority` | combo | `prompt` | `prompt`, `widgets` | prompt: the style prompt overrides the widgets. widgets: the prompt only fills widgets you left at their defaults. |
| `pixel_size` | int | `4` | 1 to 128 | Size of each chunky pixel, in source pixels. |
| `target_width` | int | `0` | 0 to 4096 | Alternative to pixel_size: the number of pixels across the image (0 = off). Allows non-integer scaling, e.g. 160 across a 1920 image. |
| `output_scale` | int | `1` | 1 to 8 | Extra whole-number enlargement of the final image, always crisp nearest-neighbour. |
| `pixel_mode` | combo | `dominant` | `dominant`, `average`, `nearest` | How each pixel gets its colour. dominant: the most common palette colour in the block, which keeps edges crisp like hand-made pixel art. average: the block's mean colour (softer, can be muddy). nearest: one sample from the block's centre. |
| `simplify` | float | `0.0` | 0.0 to 1.0 | Painterly flattening before pixelating (Kuwahara filter): noise and texture melt into clean colour regions while edges stay sharp. 0 = off. |
| `palette_preset` | combo | `adaptive_kmeans` | `adaptive_kmeans`, `none`, `black_white`, `grey_4`, `gameboy`, `mint_plum`, `ice_blue`, `newspaper`, `sepia`, `amber_crt`, `green_phosphor`, `virtual_boy`, `cga_pal1`, `cga_pal0`, `ega`, `c64`, `pico8`, `zx_spectrum`, `nes`, `apple_ii`, `msx`, `amstrad_cpc`, `teletext`, `sweetie16` | adaptive_kmeans builds a palette from your image (shared by every frame of a video). none keeps the full colours. The rest are classic palettes. |
| `palette_size` | int | `16` | 2 to 64 | Number of colours for palette_preset = adaptive_kmeans. |
| `custom_palette` | string | (empty) |  | Your own palette as hex codes, e.g. #0f380f,#306230,#8bac0f. Overrides the preset when it holds 2 or more colours. |
| `match` | combo | `colour` | `colour`, `tone` | How pixels are matched to the palette. colour: nearest colour (use for full-colour palettes). tone: by brightness only (use for Game Boy, phosphor, sepia and other one-hue palettes). |
| `method` | combo | `none` | `none`, `bayer`, `blue_noise`, `floyd_steinberg`, `atkinson`, `sierra`, `sierra_lite`, `stucki`, `jarvis`, `burkes` | Dithering when snapping to the palette (pixel_mode average or nearest). none is clean. bayer / blue_noise are steady on video; error diffusion shimmers slightly between frames. |
| `bayer_size` | combo | `4` | `2`, `4`, `8`, `16` | Matrix size for the bayer method. |
| `dither_strength` | float | `1.0` | 0.0 to 2.0 | Strength of the dithering. 0 = plain nearest palette colour. |
| `cleanup` | int | `1` | 0 to 3 | Removes stray pixels that do not belong: 1 = isolated single pixels, 2 and 3 = progressively more. Gives the clean hand-placed look. Turn it off when using dithering. |
| `outline` | combo | `none` | `none`, `dark`, `colour` | Draws a one-pixel line along edges, on the darker side. dark: a darker shade of the pixel's own colour (selective outline). colour: the outline_color below. |
| `outline_color` | string | `#000000` |  | Outline colour (hex) for outline = colour. |
| `outline_threshold` | float | `0.12` | 0.01 to 0.6 | How big a brightness step must be to get an outline. Lower = more lines. |
| `saturation` | float | `1.0` | 0.0 to 3.0 | Colour intensity before palette matching. Above 1 gives punchy pixel-art colours. |
| `brightness` | float | `0.0` | -1.0 to 1.0 | Brightness before matching. |
| `contrast` | float | `1.0` | 0.0 to 4.0 | Contrast before matching. |
| `gamma` | float | `1.0` | 0.1 to 4.0 | Midtone curve. Above 1 brightens the midtones. |
| `sharpen` | float | `0.0` | 0.0 to 4.0 | Sharpen before matching, so fine detail survives. |
| `local_contrast` | float | `0.0` | 0.0 to 2.0 | Local contrast boost so shadows and highlights keep structure. |
| `invert` | bool | `False` |  | Invert the picture before matching. |
| `transparency` | combo | `rgba` | `rgba`, `separate`, `off` | What to do when the connected mask makes parts of the picture transparent (white = transparent, as core Load Image outputs it). rgba: the image output carries its own alpha channel, so Preview and Save Image show / write real transparency - do NOT add Join Image with Alpha. separate: the image stays plain RGB (transparent areas black) and the alpha output holds the transparency, for Join Image with Alpha or video. off: ignore the mask. An all-opaque mask is ignored automatically. |
| `invert_mask` | bool | `False` |  | Turn on if the transparency comes out the wrong way round (the subject vanishes and the background stays). Some loaders output white = opaque instead of white = transparent. |
