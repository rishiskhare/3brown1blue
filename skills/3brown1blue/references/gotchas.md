# ManimCE gotchas (verified on 0.22.0)

Every item below was reproduced while building this skill. The kit already works around the ones marked **(kit)**.

## LaTeX and equations

1. **`tex_to_color_map` / `substrings_to_isolate` on a single string can silently drop glyphs (kit).**
   - Example: `MathTex(r"f(x) = x^2", tex_to_color_map={"x": GREEN})` renders only the colored pieces; `(`, `)`, `=` and `^2` vanish.
   - The same happens with `Tex(..., tex_to_color_map=...)`.
   - Cause: MathTex marks substrings with nested `\special{dvisvgm:raw <g>}` groups. Older dvisvgm (seen with 2.13.3 from TeX Live 2022) closes the outer group too early, so the glyphs after an inner group fall outside every group.
   - **Fix:** use kit `tex(..., t2c=...)`. It splits the string into separate MathTex arguments, which works with every dvisvgm. You can also pass pieces as separate args yourself (`MathTex("f(", "x", ") = ", "x", "^2")`).
2. **A bare letter key matches inside commands.** Key `"n"` would match the n in `\infty`, and `"t"` the t in `\int`. Wrap variables in braces in the source, as 3b1b does (`f({t})` with key `"{t}"`). The kit skips matches inside control words, but braces are clearer.
3. **`{{ }}` grouping only starts at the beginning of a string or after whitespace**. `f({{x}})` does not split. Write `}}` as `} }` inside regular TeX to avoid accidental grouping.
4. **`TransformMatchingTex(key_map=...)` crashes** with `zip() argument 2 is longer/shorter than argument 1` when mapped pieces have different glyph counts. `fade_transform_mismatches=True` crashes the same way. **Fix:** use kit `TransformTex`, which uses `Transform` for mapped pieces **(kit)**.
5. **TransformMatchingTex matches by tex string of the isolated part,** not by glyph shape. Unsegmented equations morph as one blob. Isolate the shared pieces, or use `TransformMatchingShapes`.
6. **Pieces must assemble into valid LaTeX as a whole,** but each piece need not be valid alone. `tex(r"\frac{", "a", "}{b}")` is fine.
7. **`\;`, `\:` and `\|` fail in math with the 3b1b preamble** (`Command \; invalid in math mode`, `Argument of \T3\| has an extra }`). The preamble loads `tipa`, which redefines them as phonetic shortcuts. The kit's template restores the math meanings **(kit)**. With plain `TexTemplateLibrary.threeb1b`, use `\,\,` and `\Vert` instead.
8. **`get_parts_by_tex` no longer exists.** Use kit `parts(eq, key)`, or `eq.get_part_by_tex(key)` for the first match.

## Rendering pipeline

9. **Parallel manim processes collide on a shared, cold TeX cache.** You get spurious `does not support converting .dvi files to SVG` or `latex failed but did not produce a log file`. `render.py` gives each scene its own cache at `media/tex_cache/<file>/<Scene>` through a generated `-c` config **(kit)**. Never put subfolders inside `media/Tex`: manim's cleanup unlinks every non-.svg entry there and crashes with `PermissionError`.
10. **`-o/--output_file` is rejected when rendering several scenes** (0.22). render.py locates outputs by path instead. It also always passes `--disable_caching`: with tbb's scenes manim's per-animation cache never hits, and hashing every `play` costs 15–25% of a render (render.py's own per-scene reuse replaces it). `--dry_run` still draws every frame; `-s` is what skips animations.
11. **Quality flags override `config.frame_rate` and resolution set in code.** Pass `--fps 30` on the command line; render.py's `--fps` does this.
12. **The output folder is named after the real frame rate:** `-qh --fps 30` writes to `1080p30/`, not `1080p60/`.
13. **ffmpeg is no longer required by manim** (it uses PyAV), but render.py uses it for concatenation, grading and contact sheets.
14. Removed in 0.22: `--write_to_movie`, `-g/--save_pngs`, `-i/--save_as_gif`, `--flush_cache`, `config.movie_file_extension`. Use `--format png-sequence|gif|...` and `manim cache clear` instead.

15. **ManimCE 0.22.0 can't draw any `ImageMobject` with Pillow 13+** (`ValueError: Invalid mode for data type`, even for a plain PNG). Text and math are unaffected. Fixed in 0.22.1: `uv pip install -U "manim>=0.22.1"`. `check_env.py` requires 0.22.1.
16. **ManimCE 0.22 can't render into a path that contains a single quote** (e.g. `~/it's videos/`). Its partial-movie manifest isn't escaped, and the render ends with `FileNotFoundError: '<none>'`. render.py refuses such a `--media-dir` up front; point `--media-dir` elsewhere.

## API changes people (and LLMs) get wrong

17. **`Axes.get_graph` is gone; use `axes.plot(f)`.** `ShowCreation` is now `Create`. `FadeIn(m, UP)` must be written `FadeIn(m, shift=UP)`.
18. **`SurroundingRectangle(m, RED, 0.3)` positional args are now mobjects.** Write `SurroundingRectangle(m, color=RED, buff=0.3)`.
19. **`Sector(inner_radius=..., outer_radius=...)` was removed.** Use `AnnularSector`.
20. **`Code(...)` has a new API:** `Code(code_string=..., language="python", formatter_style="monokai", background="window")`.
21. **`next_section(type=...)` is now `next_section(section_type=...)`.**
22. **`Mobject.always`** is sugar for an updater (`label.always.next_to(dot, UP)`). Don't pass `ValueTracker.get_value()` results into it, because they are evaluated once. Use `add_updater` or a callable instead.
23. **`ValueTracker` supports arithmetic** (`t + 1`, `2 * t`), but `t.get_value()` is what updaters should read.
24. **`ManimColor`** is the color type (0.18+). Hex strings work anywhere, but `.to_hex()` is needed for comparisons.

## Visual pitfalls

25. **CE `Axes` default to arrow tips and a length of 12.** Use kit `tbb_axes`.
26. **Plane transforms leave empty corners.** Make the plane larger than the frame (`tbb_plane(x_range=(-16, 16, 1), y_range=(-10, 10, 1))`) before shears and rotations.
27. **Text over grids or curves is unreadable** without a backstroke. Use `backstroke(m)`, `label()`, or `BackgroundRectangle`.
28. **Updaters on objects that aren't in the scene don't run.** Add them first with `self.add(...)`, then animate the tracker.
29. **`always_redraw` rebuilds the object every frame,** so there is nothing to `.animate` on it. Animate the tracker it reads.
30. **Fixed-in-frame mobjects exist only in `ThreeDScene`.** In `MovingCameraScene`, a HUD has to follow the frame with an updater (kit captions and voiceover lines already do this in `TbbMovingScene`) (`hud.add_updater(lambda m: m.move_to(self.camera.frame.get_corner(UL) + ...))`), or avoid zooming with HUD elements on screen.
31. **There is no depth test in Cairo.** Interpenetrating surfaces draw in insertion order; ThreeDScene sorts by z-index only roughly.
32. **`DecimalNumber.set_value` re-creates its glyphs,** so a number that grows a digit shifts. Re-anchor it every frame with `.always.next_to(label, RIGHT)`.
33. **Audit warnings are hints, not proof.** They check bounding boxes after each `play`. Always look at the contact sheets.

## Text

- **Pango `Text(font_size=48)` is about 1.3× larger than `Tex(font_size=48)`.** Use kit `text()`, which compensates, so mixed text and math line up.
- **Pango silently substitutes a fallback font for missing font names,** with no error. Check `tbb.TEXT_FONT` to see which face is actually in use.

Installation problems: run `check_env.py`, which prints a `fix:` line for each; narration's install traps are handled by `narrate.py` (see `narration.md` → Troubleshooting).
