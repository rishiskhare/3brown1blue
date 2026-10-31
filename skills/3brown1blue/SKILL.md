---
name: 3brown1blue
description: Makes math/science explainer videos in the visual style of 3Blue1Brown using Manim Community (ManimCE), either silent with captions or narrated by a local TTS voice (Kokoro). Use when the user asks for a "3b1b-style" or "3Blue1Brown-style" video or animation, a Manim explainer, an animated proof or derivation, a visual math lesson, narration or voice-over for such a video, or animations of equations, graphs, linear transformations, 3D surfaces or neural-network diagrams. Ships a tested style kit (tbb.py), a render/concat/grade pipeline with optional narration, loudness normalisation and subtitles, and a layout audit.
license: MIT (see LICENSE.txt)
compatibility: Python 3.11+, Manim Community 0.22.1+, ffmpeg and LaTeX. Narration needs uv and about 2 GB for the local voice model.
---

# 3Blue1Brown-style videos with Manim Community

It is unofficial, "in the style of" only. **Never recreate the Pi creatures or the 3b1b logo**, and don't copy scene code from 3b1b/videos (it is CC BY-NC-SA). [ManimCE's docs](https://docs.manim.community/en/stable/) also ask users not to use the Pi creatures.

`<skill>` below means the folder containing this SKILL.md: `.claude/skills/3brown1blue` (or `.agents/skills/3brown1blue`) inside the project, or the same under `~` for a global install.

## Files

**Read first:** this file, `examples/derivative_of_x_squared.py` (a complete ~73 s video and the best usage reference) and `references/pedagogy.md` (how Grant structures explanations). Then, only as needed, in `references/`:
- `idioms.md`: tested recipes for every signature move
- `style-guide.md`: exact colours, sizes, strokes, layout and timing
- `gotchas.md`: ManimCE 0.22 bugs and their workarounds
- `manimgl-to-ce.md`: porting ManimGL code
- `narration.md` (pipeline, API, troubleshooting) and `narration-style.md` (how Grant writes narration): when the user wants audio

`templates/` holds the kit (`tbb.py`), `manim.cfg` and `scene_template.py`. `scripts/` holds `check_env.py` and `render.py`, which renders, writes contact sheets, joins, grades and (with `--voice`) narrates.

Don't read `tbb.py`'s source; its API is below. Signatures are abbreviated: for every keyword argument, run e.g. `.venv/bin/python -c "import tbb; help(tbb.tex)"` (the python that has manim) or `help(tbb.TbbScene.caption)` from the project folder.

## Kit API (`from tbb import *`)

Conventions: the target comes first, then the text (`label(mob, s)`, `brace_label(mob, s)`); stroke sizes are `stroke_width=`; placement is `direction=`; `t2c=` colours words; `show=` toggles drawn captions.

**Scenes.** Use `TbbScene` by default, `TbbMovingScene` only for zooms and pans (camera via `self.camera.frame`; captions follow it), and `Tbb3DScene` for surfaces (it has no layout audit, so rely on the contact sheets). All three provide:
- **`self.caption(s, hold=None, color=GREY_A, run_time=0.8, t2c=None, added_anims=(), say=None, show=True)`**
  - With `hold=None`, it waits for reading time, or for the length of the speech with `--voice`.
  - `hold=0` returns at once so you can keep animating while the line plays; the next `caption()` waits for the speech to end.
  - `say=` gives the spoken form of the line. `caption(None)` clears it; `caption(None, say=...)` speaks without a caption.
- **`with self.voiceover(paragraph, captions=None, show=True, t2c=None) as v:`** narrates a paragraph and times the block to its speech; `v.wait_until(i | "phrase")` waits for sentence `i` or a phrase (cue API: `narration.md`). Without `--voice`, the sentences become captions at speaking pace.
- **`self.clear_except(*keep)`** fades out everything else (a kept piece may sit inside a group), and **`self.fade_all()`**.
- **A layout audit**, in 2D only. It warns about off-frame content and caption collisions. Set `audit_layout = False` to disable it.

**Cards.** Silent Scenes configured by class attributes (`class Opening(TitleCard): title_text = "..."`), not constructor arguments:

| Card | Attributes (all also take `hold`) |
|---|---|
| `TitleCard` | `title_text`, `subtitle_text`, `title_color`, `subtitle_color` |
| `ChapterCard` | `number`, `chapter_title`, `color` |
| `QuestionCard` | `question`, `color` |
| `QuoteCard` | `quote`, `author` |
| `EndScreen` | `message` |

**Text and math**
- `tex(*strings, t2c=None, isolate=(), font_size=48)`: every t2c/isolate key and every string becomes its own submobject. `parts(eq, key)` selects them.
- `text(s, font_size=48, color=WHITE, t2c=None)`: Computer Modern words, sized to match `tex`.
- `title(s, font_size=60, underlined=True)` returns `VGroup(words, underline)`. `underline(mob)` underlines anything.
- `label(mob, s, direction=UP, color=WHITE, math=True)` makes a backstroked label beside a mobject or point.
- `brace_label(mob, s, direction=DOWN, color=WHITE)` and `labeled_arrow(start, end, s, direction=UP)` return `VGroup(shape, label)`.
- `speech_bubble(content)` draws a plain bubble. Use it instead of characters.
- Don't name variables after kit functions (`title = title("...")` raises UnboundLocalError).

**Emphasis and animation**
- Highlights: `highlight_rect(mob)`, `FlashAround(mob)`, `FlashUnder(mob)`, `pulse_along(path)`, `glow_dot(point, color)` and `tracing_tail(mob, time_traced=1, color=None)`.
- Dimming: `dim(*mobs, opacity=0.25)` and `undim(*mobs)` return lists of animations, so unpack them with `*`. Each part keeps its own proportions (images and self-redrawing objects too) and `undim` restores the originals. `focus_on(eq, *keep)` dims everything in `eq` except the kept parts, at any depth.
- `backstroke(mob, stroke_width=3)` keeps labels readable over graphics.
- Transforms: `TransformTex(src, tgt, key_map=None)` morphs equations, and `FromCopy(src, tgt)` flies a copy from where a term comes from.
- Timing: `lagged(AnimCls, mobs, lag_ratio=0.1, **kw)` staggers a group. `time_span(anim, start, end, run_time)` confines one animation to part of a `play`.

**Math objects**
- `tbb_axes(x_range, y_range, x_length=10, y_length=5.5, numbers=True)` has no tips and thin grey lines. Plot on it with `ax.plot(f, stroke_width=3)`.
- `tbb_plane(...)` and `tbb_number_line(...)`.
- `live_number(tracker_or_fn, decimals=2, font_size=40, color=WHITE)`; place it with `.always.next_to(...)`.
- `tracked_dot(ax, graph, tracker)`, `tangent_line(ax, graph, tracker, length=4)` and `ghost(mob)`.
- `NeuralNetwork(sizes)` has `.layers`, `.edges` and `.activate(layer, values)`.
- `ProbabilityBars(labels, probs, max_width=4)` has `.reveal()` and `.animate_to(probs)`.
- `gl_orientation(theta, phi, ...)` returns kwargs for `set_camera_orientation` and `move_camera`.

**Palette** (roles and hexes: `style-guide.md`). Default: ManimCE colour names with 3b1b's `YELLOW` and `BLUE_E`, plus `SOFT_YELLOW`. ML/diagram videos may use vivek3141's `A_*` pastels instead; one palette per video. Also `X_COLOR`, `Y_COLOR`, `Z_COLOR`, `HIGHLIGHT`, `COLORMAP_3B1B`, `DEG`, and `apply_style(background=SOFT_BACKGROUND)` for a non-black background.

**LaTeX.** The template loads amsmath, amssymb, dsfont, physics, mathrsfs, xcolor and pifont (`\ding{51}`). It also defines `\minus`, and `\;` `\:` `\|` work in math.

## Workflow

### 0. Set up (once per project)

Work in the project folder. Run the skill's scripts by path from there; never copy or `cd` into `<skill>/scripts/`.

```bash
python3 <skill>/scripts/check_env.py [--python .venv/bin/python]   # apply each fix: line for a FAIL
cp <skill>/templates/tbb.py <skill>/templates/manim.cfg .
cp <skill>/templates/scene_template.py video.py
```

If manim is missing, `uv venv && uv pip install "manim>=0.22.1"` (check_env prints the system packages to install first). Whenever manim lives in a venv, pass `--python .venv/bin/python` to check_env.py and render.py.

### 1. Find the one "aha" and plan it

Before writing any code, pin down the question, the aha, one concrete example and the arc, then storyboard (both in `pedagogy.md`). Make each scene 15–60 s and one class, listed in a module-level `SCENES = [...]`. Show the storyboard to the user only if the scope is ambiguous.

- *Silent* (the default): one caption per beat via `self.caption()`.
- *Narrated* (the user wants audio): run `python3 <skill>/scripts/narrate.py setup` once per machine (~2 GB), read `references/narration-style.md` and write the full script in Grant's register. Then animate inside `self.voiceover(paragraph)` blocks. Never narrate caption fragments: they sound robotic.

### 2. Implement

In `video.py` (from the template):

- **Imports:** `from manim import *`, then `from tbb import *`, in that order.
- **Beats:** mark each one with a comment, and end it with a `wait` or a `caption`.
- **Colours:** define one colour per concept, once, as a module constant, and use it in both the formula and the picture.
- **Equations:** build them with `tex(..., t2c={"{x}": X_COL})` and wrap variables in braces. Rearrange with `TransformTex`, and show where a term comes from with `FromCopy`.
- **Layout:** keep content above y = −2.75 when captions are on, and 0.1 inside the frame edge. Sizes and timing are in `style-guide.md`.
- **Idioms:** look up moves in `idioms.md`, for example tangent lines, Riemann sums, linear maps, 3D, neural nets and probability bars.

### 3. Verify visually (mandatory, but cheaply)

Take few, large steps: check, render, read the new sheets, fix everything, repeat.

```bash
python3 <skill>/scripts/render.py video.py --check     # seconds: every LaTeX/Python error, layout warnings, stills
python3 <skill>/scripts/render.py video.py --sheet     # 480p draft + contact sheets [--voice]
```

- **Run `--check` first** after every edit. It skips animations, reports *every* LaTeX error and the first Python error of each scene in one pass, prints the layout warnings and saves each scene's last frame (open those PNGs for a quick look). A formula with a LaTeX error is drawn as `?`, so code that indexes into it may report a follow-on error: fix the LaTeX first. Then render.
- **Renders are incremental:** scenes whose code and settings are unchanged are `reused`, so re-running the whole file costs only what changed. A scene re-renders when its class, a class it uses, module-level code, an imported local module (`tbb.py`, helpers) or any other file in the project folder (images, data, `manim.cfg`) changes; `--force` re-renders everything.
- **Read the contact sheets listed under `New sheets:`** (`media/sheets/video/<Scene>.png`, 12 frames each); the others haven't changed. Fix every `layout:` warning. Look for overlaps, off-frame text, captions over content, ugly in-between frames, inconsistent colours, too much motion at once, and dead air.
- **Batch your fixes** into one edit per iteration.
- **With `--voice`, captions go to the `.srt` only** and the caption-collision audit is skipped. If the user wants captions burned in, pass `--captions` to the drafts and the final alike.
- **If a scene fails,** render.py prints the error with the failing line of `video.py`, or for LaTeX the TeX error and the formula, with `|` marking piece boundaries. Fix it from that output.

### 4. Final render

```bash
python3 <skill>/scripts/render.py video.py -q h --fps 30           # silent: 1080p30, Grant's frame rate
python3 <skill>/scripts/render.py video.py -q h --fps 30 --voice   # narrated
```

This writes `final/video_1080p30.mp4` (use `-q k` only if the user asks for 4K). With `--voice` it also writes `final/video_1080p30.srt` and `final/video_narration.txt`. Report the paths, the duration and the scene list.

### Running renders

- **Render in the foreground, not as background tasks,** which have been killed silently. Set the shell tool's timeout to its maximum (e.g. 600000 ms) for every render. Ctrl-C stops every scene.
- **Keep each command under ~10 minutes.** Render long videos in batches and then join them:

  ```bash
  python3 <skill>/scripts/render.py video.py S1 S2 S3 -q h --fps 30 --no-concat [--voice]
  python3 <skill>/scripts/render.py video.py S4 S5 -q h --fps 30 --no-concat [--voice]
  python3 <skill>/scripts/render.py video.py -q h --fps 30 --concat-only [--voice]
  ```

  Scenes render in parallel (one per core, up to 8), longest first; at 1080p30 a scene takes about 0.3× its own length, so the longest scene sets the time.
- **With `--voice`,** read the `Audio check:` line: any silence over 4 s is a beat without speech.

## Narration

`--voice` narrates locally with Kokoro-82M `am_michael` (pipeline and troubleshooting: `narration.md`). For a silent video meant for a later voice-over, `--no-captions` keeps every beat's timing but draws no text.
