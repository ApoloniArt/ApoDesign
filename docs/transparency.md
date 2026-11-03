# Transparency
ComfyUI's Load Image splits a PNG into `image` (the colours) and `mask` (the transparency; **white = transparent**). Connect that `mask` to the `mask` input of any ApoDesign node and transparent areas stay transparent:

- Transparent areas are left out of palettes and never bleed into the pixels next to them (no coloured fringes or halos).
- The transparency follows the node's own grid, so it is as chunky as the pixels, characters or dots.
- Pixel Art outlines also trace the silhouette of the subject.
- Ascii leaves transparent cells empty, and blank in the `text` output.

The `transparency` widget chooses how it comes out:
| Value | Result |
|---|---|
| `rgba` (default) | The `image` output has an alpha channel. Connect it straight to Preview Image or Save Image (no Join Image with Alpha needed) and you get real transparency / a transparent PNG |
| `separate` | `image` stays plain RGB (transparent areas black) and the `alpha` output carries the transparency (white = transparent, same as Load Image), for Join Image with Alpha, or for video. (The `alpha` output is filled in `rgba` mode too.) |
| `off` | The mask is ignored |

**Mask the wrong way round?** Core Load Image gives white = transparent. If your loader gives white = opaque (the subject disappears and only a thin edge is left), turn on `invert_mask`.

A mask that is all black (nothing transparent) is ignored automatically, so ordinary opaque pictures and videos keep their normal 3-channel output.

In Bitmap and Ascii, `mix_mode = mask` still uses the `mask` input to paint where colour appears; in that case it is not used as transparency.

Note: some nodes (for example Create Video) cannot take a 4-channel image. For transparent video use `separate`.
