# Testing

Double-click `RUN_TESTS.bat`. It looks for your ComfyUI's `python_embeded` (three folders up from `custom_nodes/ComfyUI-ApoDesign`) and asks you to drag `python.exe` into the window if it cannot find it. It prints one PASS / FAIL line per test and saves them to `tests/test_results.txt`.

| File | Needs | Covers |
|---|---|---|
| `tests/test_pure.py` | Python only | Widget specs, prompts, looks (built-in and your own, folders, menus, Save Look), the LLM prompt file, node registration, banner files in place |
| `tests/test_fonts.py` | numpy, Pillow | Glyph atlases, braille, block characters |
| `tests/test_torch.py` | torch (ships with ComfyUI) | The engines, including that parallel error diffusion matches a plain sequential loop for every kernel, and that Ascii shape mode and braille reproduce known patterns exactly |

Tests that need torch print SKIPPED (not FAIL) when torch is not available, for example when run with a system Python instead of ComfyUI's.
