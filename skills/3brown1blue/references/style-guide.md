# 3Blue1Brown visual style: exact values

Where the numbers come from:
- `3b1b/videos` `custom_config.yml` (Grant's production config)
- `3b1b/manim` `default_config.yml` (ManimGL library defaults)
- token counts over every `.py` file in `3b1b/videos/_2024–_2026`, about 111k lines
- `vivek3141/videos` and `vivek3141/dl-visualization`

`tbb.py` already applies everything marked **(kit)**.

## Contents

- Frame and output
- Palette
- Typography
- Strokes and shapes
- Layout
- Motion
- Timing

## Frame and output

| Setting | 3b1b | ManimCE equivalent |
|---|---|---|
| Frame | 8 units tall × 14.22 wide (16:9) | same default |
| Background | `#000000` (library default is `#333333`; Grant overrides it) | `config.background_color = "#000000"` **(kit)** |
| Resolution / fps | 3840×2160 at **30 fps** | Grant's masters. This skill's final default is 1080p30 (`-q h --fps 30`); `-q k --fps 30` when 4K is asked for; drafts at `-q l` |
| Colour grade | ffmpeg `eq=saturation=1.5` on every output | `render.py` grades every clip (default `--saturation 1.5`) |
| Buffs | SMALL 0.1, MED_SMALL 0.25, MED_LARGE 0.5, LARGE 1.0; `to_edge` 0.5 | identical constants |

Alternative backgrounds: `#1C1C1C` (softer, a common community choice) and `#222222` (vivek3141's 2024 videos). Use `apply_style(background=SOFT_BACKGROUND)` for these. Keep the background pure black unless asked.

## Palette

ManimCE's constants equal ManimGL's **except two**, and the kit fixes both:
- `YELLOW` / `YELLOW_C` is pure yellow `#FFFF00` in 3b1b. CE uses `#F7D96F`, which the kit keeps as `SOFT_YELLOW`.
- `BLUE_E` is `#1C758A` in 3b1b. CE uses `#236B8E`.

| Family | E | D | C (= bare name) | B | A |
|---|---|---|---|---|---|
| BLUE | #1C758A | #29ABCA | #58C4DD | #9CDCEB | #C7E9F1 |
| TEAL | #49A88F | #55C1A7 | #5CD0B3 | #76DDC0 | #ACEAD7 |
| GREEN | #699C52 | #77B05D | #83C167 | #A6CF8C | #C9E2AE |
| YELLOW | #E8C11C | #F4D345 | #FFFF00 | #FFEA94 | #FFF1B6 |
| GOLD | #C78D46 | #E1A158 | #F0AC5F | #F9B775 | #F7C797 |
| RED | #CF5044 | #E65A4C | #FC6255 | #FF8080 | #F7A1A3 |
| MAROON | #94424F | #A24D61 | #C55F73 | #EC92AB | #ECABC1 |
| PURPLE | #644172 | #715582 | #9A72AC | #B189C6 | #CAA3E8 |
| GREY | #222222 | #444444 | #888888 | #BBBBBB | #DDDDDD |

Others: `PINK #D147BD`, `ORANGE #FF862F`, `GREY_BROWN #736357`, `LIGHT_BROWN #CD853F`. The heat map is `COLORMAP_3B1B = [BLUE_E, GREEN, YELLOW, RED]`.

**House logic** (by usage in recent videos, YELLOW and WHITE lead, then BLUE, RED, TEAL):

- **YELLOW** for the thing to look at now (highlights, the moving dot, the key term)
- **BLUE / TEAL** for the primary objects (graphs, the main shape, inputs)
- **RED / PINK** for contrast (a second quantity, the "other" case, errors)
- **GREEN** for x or i-hat, and for "correct"
- **GREY_B / GREY_D** for axes, scaffolding and de-emphasised material
- **WHITE** for ordinary text and math

**Fixed semantic conventions:** i-hat `GREEN_C`, j-hat `RED_C`, k-hat `BLUE_D` (`X_COLOR`, `Y_COLOR`, `Z_COLOR` in the kit). A variable keeps one colour for the entire video, in every equation (`t2c`) and in the geometry it names. Before writing scenes, decide this once as module constants (`X_COL = BLUE`).

**vivek3141 pastels** (ColorBrewer Set3, `A_*` in the kit) are a softer alternative suited to ML and diagram-heavy videos. His roles:

| Color | Role |
|---|---|
| `A_PINK` | input x |
| `A_GREEN` | hidden / output |
| `A_BLUE` | ŷ |
| `A_YELLOW` | time index, constants, slide titles |
| `A_AQUA` | function names (σ, softmax) |
| `A_GREY` | weights W |
| `A_LAVENDER` | probabilities |
| `A_MINT` | indices |

Also `A_RED`, `A_ORANGE`, `A_VIOLET` and `A_GOLD`. Don't mix the two palettes in one video.

## Typography

- **Words** are Pango `Text` in **CMU Serif** (Computer Modern Unicode), centered. Recent 3b1b code uses `Text` about 5× as often as `TexText`. The kit's `text()` uses CMU Serif, then TeX Live's Latin Modern Roman (registered automatically), then LaTeX text mode. Its `font_size` is calibrated so words and `tex()` math match in size (raw Pango renders about 1.3× larger).
- **Math** uses the `threeb1b` LaTeX preamble **(kit)**, with `amsmath`, `amssymb`, `dsfont`, `physics`, `mathrsfs`, `xcolor` and others. `\minus` is a shorter minus sign: `e^{\minus st}`.
- **Sizes** from usage counts:

  | Use | font_size | Most common |
  |---|---|---|
  | Titles | 60–72 | 72 |
  | Big hero equation | 90–96 | |
  | Body equations and labels | 36–48 | |
  | Small labels | 24–30 | |
  | Axis and coordinate numbers | 16–24 | |
  | Captions (kit) | 34 | |

- Titles go `.to_edge(UP, buff=MED_SMALL_BUFF)` with a tight `Underline` (GREY_B, stroke 2) and enter with `FadeIn(title, lag_ratio=0.1)` plus `Create(underline)`. Use `title()` from the kit: it defaults to 60 for a header above content; the cards use 72.
- Keep on-screen prose to a minimum. In silent videos the captions are the only sentences.

## Strokes and shapes

- The default VMobject stroke is 4. Explicit widths in recent code: 2 (443 uses), 1 (339), 3 (217), 5 (52), 0.5 (42). **3b1b lines are thin.**
  - Graphs and curves: 2–3. vivek3141 uses 6 for bold single-curve charts.
  - Grid and helper lines: 1, often at opacity 0.25–0.5.
  - Highlight rectangles: 2–3, YELLOW or WHITE, buff 0.1.
  - Arrows and vectors: 4–6.
- **Axes:** no tips, GREY_B, stroke 2, small ticks, numbers 16–24 **(kit `tbb_axes`)**. CE's `Axes` defaults to tips and should not be used as-is.
- **NumberPlane:** BLUE_D background lines at width 2, plus faded BLUE_E lines at width 1 and opacity 0.25–0.5 **(kit `tbb_plane`)**. Grant often thins these further: `plane.background_lines.set_stroke(BLUE, 1, 0.5)`.
- **Backstroke:** a black stroke behind labels that sit over graphics, width 3–5 (194 uses). Use `backstroke(m)` or `label()`.
- Filled shapes: fill opacity 0.5–0.9 with a thin white or same-colour border (width 1–2).
- Points are a crisp dot plus a glow halo (`glow_dot()`), often with a fading tail (`tracing_tail()`).

## Layout

- **Center the subject.** Put the hero object in the middle; labels go `next_to` it (`next_to` 2553 uses, `to_edge` 641, `arrange` 571).
- **Split screens** sit at `±FRAME_WIDTH/4`, with headers in yellow or white and an optional vertical divider `Line(4*UP, 4*DOWN, stroke_width=1, color=GREY_D)`.
- **Equations** sit on top (`to_edge(UP)`) or to the right of a diagram, never crammed into a corner.
- **Silent videos:** reserve the bottom band (y < −2.75) for captions, and keep 0.1+ units off the frame edges. The kit's audit enforces both.
- **Never stack** more than about 3 equation lines. Transform one line into the next instead.

## Motion

- **Easing:** ManimGL's `smooth` is smootherstep, `t³(10 − 15t + 6t²)`, which the kit sets as the CE default. Use `linear` for continuous sweeps, tracing and passing flashes, and `there_and_back` for wiggles.
- **Most used animations:** FadeIn and FadeOut by far, then Write, ShowCreation (CE `Create`) and **TransformFromCopy** (kit `FromCopy`), then ReplacementTransform, GrowArrow and FadeTransform.
  - `FadeIn` almost always has a `shift` (0.25–0.5 units) or a `scale`.
  - `Write` is for text and equations; `Create` is for curves, lines and rectangles.
  - `TransformFromCopy` uses `path_arc` about 70% of the time (−π/4 … π/2).
- **Lag ratios:** usually 0.1, else 0.2–0.5; 0.01–0.05 for huge groups.
- **Combine camera moves** with content changes in the same `play`.
- **Exits:** fade out, or shift away from the centre in the direction the layout implies. vivek3141 prefers `Uncreate` for exits. Avoid hard cuts inside a scene.

## Timing

The commonest `run_time` is 2 s (then 3, 5, 1), and most plays are followed by a `wait()` (1 s).

| Beat | Duration |
|---|---|
| Simple fade or label | 1 s |
| Meaningful transform, equation step, copy-flight | 1.5–2 s |
| Camera reorientation, parameter sweep, plane warp | 3–8 s, `linear` for sweeps |
| After a reveal | `wait(1–2)` |
| After a key formula or the aha | `wait(2–3)` |
| Ambient 3D rotation or an updater-driven sim | `wait(4–10)` |

Silent captions must hold long enough to read: `caption()` waits `reading_time(s)` = words ÷ 180 wpm + 0.6 s (at least 1.2 s). Pass `hold=` to override.
