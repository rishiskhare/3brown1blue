# ManimGL → ManimCE translation

3b1b's own code (3b1b/videos) and vivek3141's code are written for **ManimGL**, and they do not run under ManimCE. Use this table to port an idea or a snippet. Statuses were checked against ManimCE 0.22.

## Contents

- Scenes and camera
- Text and Tex
- Animations
- Mobjects and styling
- Axes and planes
- Config

## Scenes and camera

| ManimGL | ManimCE (+ tbb) | Notes |
|---|---|---|
| `InteractiveScene` | `TbbScene` / `TbbMovingScene` / `Tbb3DScene` | CE has no interactive selection tools. |
| `self.embed()`, `checkpoint_paste()` | iterate with `render.py --check` (stills of every scene in seconds), or `render.py f.py Scene -- -n 3,5` (manim flags go after `--`) | `self.interactive_embed()` exists only with `--renderer=opengl`. |
| `CONFIG = {...}` | class attributes | e.g. `TitleCard.title_text`. |
| `self.frame.animate.set_height(4).move_to(x)` (2D) | `TbbMovingScene`: `self.camera.frame.animate.set(height=4).move_to(x)` | |
| `frame.reorient(θ, φ, γ, center, height)` (degrees) | `self.set_camera_orientation(**gl_orientation(θ, φ, γ, center, height))` | CE θ = GL θ − 90°; check visually. |
| `self.play(frame.animate.reorient(...), anims, run_time=T)` | `self.move_camera(**gl_orientation(...), added_anims=[...], run_time=T)` | |
| `frame.add_ambient_rotation(k * DEG)` | `self.begin_ambient_camera_rotation(rate=k * DEG)` | Stop it with `stop_ambient_camera_rotation()`. |
| `mob.fix_in_frame()` | `self.add_fixed_in_frame_mobjects(mob)` (ThreeDScene only) | `self.caption()` does this automatically. |
| `apply_depth_test()`, `set_clip_plane`, `always_sort_to_camera` | none (Cairo) | Keep 3D simple. |
| `self.time` | a `ValueTracker` with `add_updater(lambda m, dt: m.increment_value(dt))` | |

## Text and Tex

| ManimGL | ManimCE (+ tbb) |
|---|---|
| `Tex(R"...")` (math) | `MathTex(r"...")`, or kit `tex(...)` |
| `TexText("...")` | `Tex("...")`, or kit `text(...)` |
| `Text("...")` with CMU Serif from config | kit `text(...)` (sets CMU Serif, with a LaTeX fallback) |
| `Tex(..., t2c={"{x}": BLUE})` | kit `tex(..., t2c={"{x}": BLUE})` (CE's `tex_to_color_map` can drop glyphs; see gotchas.md) |
| `eq["x"]`, `eq["x"][1]` | kit `parts(eq, "x")`, `parts(eq, "x")[1]` (the key must be a t2c/isolate key) |
| `TransformMatchingTex` / `TransformMatchingStrings(a, b, key_map=)` | kit `TransformTex(a, b, key_map=)` |
| `tex.make_number_changeable("1.00")` | kit `live_number(tracker)`, placed with `.always.next_to(...)` |
| `CountInFrom(dec, 0)` | `ChangeDecimalToValue(dec, target)` |

## Animations

| ManimGL | ManimCE (+ tbb) | Notes |
|---|---|---|
| `ShowCreation` | `Create` | |
| `FadeIn(m, UP)` | `FadeIn(m, shift=UP)` | **CE treats positional args as more mobjects.** |
| `FadeOut(m, DOWN)` | `FadeOut(m, shift=DOWN)` | |
| `VFadeIn` / `VFadeOut` | `FadeIn` / `FadeOut` | |
| `VFadeInThenOut(m)` | `FadeIn(m, rate_func=there_and_back, remover=True)` | |
| `VShowPassingFlash(path, time_width=)` | kit `pulse_along(path)` / `ShowPassingFlash(path.copy(), time_width=)` | |
| `ShowCreationThenFadeOut(m)` | `Succession(Create(m), FadeOut(m))` | |
| `WiggleOutThenIn` | `Wiggle` | |
| `anim(time_span=(a, b))` | kit `time_span(anim, a, b, run_time)` | |
| `LaggedStartMap(FadeIn, group, shift=UP)` | kit `lagged(FadeIn, group, shift=UP)` | |
| `LaggedStart(gen, group_type=Group)` | `LaggedStart(*list(gen))` | |
| `self.play(mob.method, arg)` / `ApplyMethod` | `self.play(mob.animate.method(arg))` | |
| `self.play(v.increment_value, 5)` | `self.play(v.animate.increment_value(5))` | |
| `Transform(a, b, replace_mobject_with_target_in_scene=True)` | `ReplacementTransform(a, b)` | |
| GL `smooth` rate func | `smootherstep` (kit default) | CE's `smooth` is a different sigmoid. |

## Mobjects and styling

| ManimGL | ManimCE (+ tbb) |
|---|---|
| `m.set_backstroke(BLACK, 5)` | kit `backstroke(m, stroke_width=5)`, i.e. `set_stroke(BLACK, 5, background=True)` |
| `m.set_width(w)` / `set_height(h)` | `m.scale_to_fit_width(w)` or `m.set(width=w)` |
| `m.set_max_width(w)` | `if m.width > w: m.scale_to_fit_width(w)` |
| `m.replicate(n)` | `VGroup(*[m.copy() for _ in range(n)])` |
| `m.f_always.move_to(func)` | `m.add_updater(lambda m: m.move_to(func()))` |
| `m.get_points()`, `m.data["points"]` | `m.points` |
| `m.pfp(a)` | `m.point_from_proportion(a)` |
| `GlowDot`, `Group(TrueDot(), GlowDot())` | kit `glow_dot(point, color)` |
| `TracingTail(m, time_traced=1)` | kit `tracing_tail(m, time_traced=1)` |
| `DotCloud(points)` | `VGroup(*[Dot(p, radius=r) for p in points])` |
| `Arrow(a, b, thickness=3)` | `Arrow(a, b, stroke_width=4–6, buff=0)` |
| `Arrow(..., max_width_to_Length_ratio=inf)` (vivek, a typo GL ignored) | `max_stroke_width_to_length_ratio=`, `max_tip_length_to_length_ratio=` |
| `SpeechBubble`, `ThoughtBubble` | kit `speech_bubble(content)` |
| `PiCreature`, `Randolph`, `Mortimer`, `TeacherStudentsScene` | **don't** (copyrighted). Use `QuestionCard`, `speech_bubble`, or a plain caption. |
| `FullScreenRectangle()` | `FullScreenRectangle().set_fill(GREY_E, 1).set_stroke(width=0)` |
| `Checkmark` / `Exmark` | `Tex(r"\ding{51}")` / `Tex(r"\ding{55}")` (the kit template loads pifont) |
| `ParametricSurface`, `TexturedSurface` | `Surface(...)`; no textures in Cairo |
| `SGroup` | `Group` |
| `ParametricCurve(f, t_range=(a, b, dt))` | `ParametricFunction(f, t_range=[a, b, dt])` |

## Axes and planes

| ManimGL | ManimCE (+ tbb) | Notes |
|---|---|---|
| `Axes((0, 10), (-1, 1), width=6, height=3)` | kit `tbb_axes((0, 10, 1), (-1, 1, 1), x_length=6, y_length=3)` | CE `Axes` defaults to tips and length 12. |
| `axes.get_graph(f)` | `axes.plot(f)` | `get_graph` was removed. |
| `axes.get_area_under_graph(g, (a, b))` | `axes.get_area(g, x_range=(a, b))` | |
| `axes.get_v_line_to_graph(x, g)` | `axes.get_vertical_line(axes.i2gp(x, g))` | |
| `axes.get_tangent_line(x, g)` | kit `tangent_line(axes, g, tracker)` or `TangentLine(g, alpha)` | |
| `plane.add_coordinate_labels(font_size=16)` | `plane.add_coordinates()` | |
| `NumberPlane(faded_line_ratio=4, background_line_style=...)` | same kwargs; kit `tbb_plane()` | |
| `ApplyMethod(plane.apply_complex_function, f)` | `plane.animate.apply_complex_function(f)` | Call `prepare_for_nonlinear_transform()` first. |
| `color_gradient(cs, n, interp_by_hsl=True)` | `color_gradient(cs, n)` | |

## Config

| ManimGL `custom_config.yml` | ManimCE |
|---|---|
| `camera.background_color: "#000000"` | kit `apply_style()`; `manim.cfg` |
| `camera.fps: 30`, `resolution: (3840, 2160)` | `render.py -q k --fps 30` |
| `file_writer.saturation: 1.5` | `render.py` (default `--saturation 1.5`) |
| `text.font: "CMU Serif"` | kit (`Text.set_default(font="CMU Serif")`) |
| `tex.template: default` | kit (`TexTemplateLibrary.threeb1b` + pifont + `\minus`) |
