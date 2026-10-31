# Idiom cookbook (ManimCE + tbb)

Every recipe below is a complete scene. All of them were executed on ManimCE 0.22 with `tbb.py`, and each one assumes this header:

```
from manim import *
from tbb import *
```

Copy the parts you need. Names like `tex`, `parts`, `TransformTex`, `FromCopy` and `caption` come from the kit.

---

## Contents

- Equations
- Graphs and calculus
- Highlighting and attention
- Motion, points and paths
- Linear algebra
- Camera
- Data, probability, ML (vivek3141-style)
- Structure and cards

## Equations

### Morph an equation step by step
Matching pieces glide; everything else fades. Isolate shared symbols with `t2c` keys, braced variables, or separate string arguments.

```python
class EquationSteps(TbbScene):
    def construct(self):
        t2c = {"{a}": BLUE, "{b}": TEAL, "{c}": YELLOW}
        steps = [
            tex(r"{a}^2 + {b}^2 = {c}^2", t2c=t2c, font_size=72),
            tex(r"{b}^2 = {c}^2 - {a}^2", t2c=t2c, font_size=72),
            tex(r"{b} = \sqrt{ {c}^2 - {a}^2 }", t2c=t2c, font_size=72),
        ]
        self.play(Write(steps[0]))
        self.wait()
        for a, b in zip(steps, steps[1:]):
            self.play(TransformTex(a, b))
            self.wait()
```

### Map differently written pieces with `key_map`
`TransformTex(src, tgt, key_map={"=": r"\approx", r"x\,dx": r"2x\,dx"})` morphs the source piece `x\,dx` into the target `2x\,dx`. Keys are the pieces' tex strings. Use the kit's `TransformTex`, not CE's `TransformMatchingTex(key_map=...)`, which crashes; see gotchas.md.

### Build an equation from things already on screen
This is 3b1b's most-used move: a copy flies from where a term *comes from*.

```python
class BuildFromPicture(TbbScene):
    def construct(self):
        rect = Rectangle(width=4, height=2).set_stroke(WHITE, 2).set_fill(BLUE_E, 0.8).shift(2 * LEFT)
        w = brace_label(rect, "w", DOWN, color=BLUE)
        h = brace_label(rect, "h", LEFT, color=TEAL)
        self.play(DrawBorderThenFill(rect), FadeIn(w), FadeIn(h))
        eq = tex("A", "=", "w", r"\cdot", "h", font_size=72).to_edge(RIGHT, buff=1.2)
        parts(eq, "w").set_color(BLUE); parts(eq, "h").set_color(TEAL)
        self.play(FromCopy(rect, eq[0]), Write(eq[1]))
        self.play(FromCopy(w[1], eq[2]), Write(eq[3]), FromCopy(h[1], eq[4]))
        self.wait()
```

### Select and emphasise parts (ManimGL's `eq["x"]`)

```python
class SelectParts(TbbScene):
    def construct(self):
        lap = tex(r"F(s) = \int_0^\infty f({t}) e^{\minus s{t}} d{t}", t2c={"{t}": BLUE, "s": YELLOW}, font_size=64)
        self.play(Write(lap))
        ts = parts(lap, "{t}")                  # all three t's; ts[0] is the first
        self.play(*focus_on(lap, ts))           # dim everything else
        self.play(LaggedStart(*[Indicate(t, color=BLUE_A) for t in ts], lag_ratio=0.2))
        self.play(*undim(*lap.submobjects))
        self.play(FlashAround(parts(lap, "s")[1]))
        self.wait()
```

### Live numbers in an equation

```python
class LiveNumber(TbbScene):
    def construct(self):
        k = ValueTracker(1)
        lhs = MathTex(r"e^{k} \approx", font_size=64)
        val = live_number(lambda: np.exp(k.get_value()), decimals=3, font_size=64, color=YELLOW)
        knum = live_number(k, decimals=2, font_size=48, color=BLUE)
        lhs.shift(LEFT)
        val.always.next_to(lhs, RIGHT)
        klabel = MathTex("k =", font_size=48).next_to(lhs, UP, buff=0.8).align_to(lhs, LEFT)
        knum.always.next_to(klabel, RIGHT)
        self.add(lhs, val, klabel, knum)
        self.play(k.animate.set_value(2.5), run_time=3, rate_func=linear)
        self.wait()
```

---

## Graphs and calculus

### Graph, moving point, tangent line, readout
```python
class TangentSweep(TbbScene):
    def construct(self):
        ax = tbb_axes(x_range=(-3, 3, 1), y_range=(-1, 5, 1), x_length=8, y_length=5).to_edge(LEFT, buff=0.8)
        f = ax.plot(lambda x: 0.4 * x**2 + 0.3, color=BLUE, stroke_width=3)
        x = ValueTracker(-2)
        tan = tangent_line(ax, f, x, length=3)
        dot = tracked_dot(ax, f, x)
        slope = live_number(lambda: 0.8 * x.get_value(), color=YELLOW)
        slope_label = MathTex(r"\text{slope} =").to_corner(UR, buff=1).shift(LEFT)
        slope.always.next_to(slope_label, RIGHT)
        self.play(Create(ax), Create(f))
        self.play(Create(tan), FadeIn(dot), Write(slope_label), FadeIn(slope))
        self.play(x.animate.set_value(2), run_time=5, rate_func=linear)
        self.wait()
```

### Riemann rectangles that refine into the area
```python
class RiemannRefine(TbbScene):
    def construct(self):
        ax = tbb_axes(x_range=(0, 4, 1), y_range=(0, 4, 1), x_length=8, y_length=5)
        g = ax.plot(lambda x: 0.2 * x**2 + 0.5, color=TEAL, stroke_width=3)
        self.play(Create(ax), Create(g))
        rects = [ax.get_riemann_rectangles(g, x_range=[0.5, 3.5], dx=dx, fill_opacity=0.7,
                                           color=[BLUE_E, TEAL], stroke_width=1 if dx > 0.1 else 0)
                 for dx in (0.5, 0.25, 0.1, 0.05)]
        self.play(lagged(FadeIn, rects[0], shift=0.2 * UP, lag_ratio=0.1))
        for a, b in zip(rects, rects[1:]):
            self.play(ReplacementTransform(a, b), run_time=1.5)
        area = ax.get_area(g, x_range=(0.5, 3.5), color=TEAL, opacity=0.7)
        self.play(FadeIn(area), FadeOut(rects[-1]))
        self.wait()
```

### Secant line collapsing to the tangent (a limit)
```python
class SecantToTangent(TbbScene):
    def construct(self):
        ax = tbb_axes(x_range=(0, 4, 1), y_range=(0, 5, 1), x_length=8, y_length=5)
        g = ax.plot(lambda x: 0.3 * x**2 + 0.3, color=BLUE, stroke_width=3)
        h = ValueTracker(1.5)
        x0 = 1.5
        secant = always_redraw(lambda: ax.get_secant_slope_group(
            x0, g, dx=h.get_value(), dx_line_color=YELLOW, dy_line_color=TEAL,
            dx_label="dx", dy_label="dy", secant_line_color=RED, secant_line_length=5))
        self.play(Create(ax), Create(g))
        self.play(FadeIn(secant))
        self.play(h.animate.set_value(0.05), run_time=4)
        self.wait()
```

---

## Highlighting and attention

```python
class AttentionToolkit(TbbScene):
    def construct(self):
        eq = tex(r"e^{i\pi} + 1 = 0", font_size=96)
        self.play(Write(eq))
        rect = highlight_rect(eq[0][:3])                            # box the first term
        self.play(Create(rect))
        self.play(Transform(rect, highlight_rect(eq[0][4])))        # slide the box to another term
        self.play(FadeOut(rect), FlashAround(eq))                   # streak of light around the whole
        b = brace_label(eq, r"\text{five constants}", font_size=40)
        self.play(GrowFromCenter(b[0]), FadeIn(b[1], shift=0.2 * DOWN))
        self.play(FlashUnder(b[1]))
        self.play(*dim(eq), Indicate(b[1]))                          # push the rest back
        self.wait()
```

Use them roughly in this order of strength:
1. `dim`, for "ignore this"
2. `highlight_rect`, for "this one"
3. `Indicate`, a quick pulse
4. `FlashAround` / `FlashUnder`, for "important!"
5. `Circumscribe`

Don't stack more than two on one beat.

---

## Motion, points and paths

### Glowing point with a comet tail, plus the classic circle-to-sine trace
```python
class CircleToSine(TbbScene):
    def construct(self):
        circle = Circle(radius=1.2, color=GREY_B, stroke_width=2).shift(4.5 * LEFT)
        ax = tbb_axes(x_range=(0, TAU, PI / 2), y_range=(-1.5, 1.5, 1), x_length=7, y_length=3.6,
                      numbers=False).shift(1.5 * RIGHT)
        t = ValueTracker(0)
        dot = glow_dot(color=YELLOW)
        dot.add_updater(lambda d: d.move_to(circle.point_at_angle(t.get_value())))
        tail = tracing_tail(dot[1], time_traced=0.8, color=YELLOW)
        radius = always_redraw(lambda: Line(circle.get_center(), dot.get_center(), color=YELLOW, stroke_width=2))
        wave = always_redraw(lambda: ax.plot(np.sin,  # y unit = 1.2 = circle radius
                                              x_range=[0, max(t.get_value(), 1e-3)], color=YELLOW, stroke_width=3))
        link = always_redraw(lambda: DashedLine(dot.get_center(), ax.c2p(t.get_value(), np.sin(t.get_value())),
                                                stroke_width=1, color=GREY_B))
        self.play(Create(circle), Create(ax))
        self.add(radius, tail, dot, wave, link)
        self.play(t.animate.set_value(TAU), run_time=6, rate_func=linear)
        self.wait()
```

### A pulse travelling along a path (signal flow, a highlighted route)
`self.play(pulse_along(path, color=YELLOW))` sends a flash along any VMobject: a curve, an arrow, a network edge. For many edges at once, use `LaggedStart(*[pulse_along(e) for e in edges], lag_ratio=0.01)`.

---

## Linear algebra

### Shear with basis vectors (keep the plane larger than the frame)
```python
class Shear(TbbScene):
    def construct(self):
        plane = tbb_plane(x_range=(-16, 16, 1), y_range=(-10, 10, 1))   # oversized: corners stay covered
        ghost_grid = tbb_plane().set_opacity(0.15)
        i_hat = Vector(RIGHT, color=X_COLOR); j_hat = Vector(UP, color=Y_COLOR)
        m = [[1, 1], [0, 1]]
        matrix = Matrix(m, h_buff=0.8).scale(0.8).to_corner(UL)
        matrix.get_columns()[0].set_color(X_COLOR); matrix.get_columns()[1].set_color(Y_COLOR)
        bg = BackgroundRectangle(matrix, fill_opacity=0.85, buff=0.15)
        self.add(ghost_grid)
        self.play(Create(plane, lag_ratio=0.02, run_time=2))
        self.play(GrowArrow(i_hat), GrowArrow(j_hat), FadeIn(bg), Write(matrix))
        self.play(plane.animate.apply_matrix(m),
                  j_hat.animate.put_start_and_end_on(ORIGIN, [1, 1, 0]), run_time=3)
        self.wait()
```
CE's built-in `LinearTransformationScene` (`self.apply_matrix(m)`, with `leave_ghost_vectors=True`) does the same with less control over styling.

### Nonlinear warp of the plane (complex function, or a neural net layer)
```python
class ComplexWarp(TbbScene):
    def construct(self):
        plane = tbb_plane(x_range=(-4, 4, 0.5), y_range=(-3, 3, 0.5), faded_line_ratio=1)
        plane.prepare_for_nonlinear_transform(num_inserted_curves=40)
        label = tex(r"z \mapsto z^2", font_size=56).to_corner(UL)
        backstroke(label, stroke_width=6)
        self.play(Create(plane, lag_ratio=0.02))
        self.play(Write(label))
        self.play(plane.animate.apply_complex_function(lambda z: z**2 / 2.5), run_time=5)
        self.wait()
```
vivek3141 warps the plane with a *real* trained model: `func = lambda z: complex(*model(torch.tensor([z.real, z.imag])))`. Compute data outside manim (torch, numpy), save it with `np.save`, and load it in the scene.

---

## Camera

### 2D zoom into a detail and back out
```python
class ZoomDetail(TbbMovingScene):
    def construct(self):
        ax = tbb_axes(x_range=(-3, 3, 1), y_range=(-2, 2, 1))
        g = ax.plot(lambda x: np.sin(3 * x) * np.exp(-x**2 / 4), color=BLUE, stroke_width=3)
        self.add(ax, g)
        spot = ax.i2gp(0.5, g)
        frame = self.camera.frame
        self.play(frame.animate.set(width=3).move_to(spot), run_time=3)
        self.wait()
        self.play(frame.animate.set(width=config.frame_width).move_to(ORIGIN), run_time=2)
```

### 3D surface, camera move, fixed HUD
```python
class Surface3D(Tbb3DScene):
    def construct(self):
        ax = ThreeDAxes(x_range=[-3, 3], y_range=[-3, 3], z_range=[-2, 2], x_length=6, y_length=6, z_length=3)
        surf = Surface(lambda u, v: ax.c2p(u, v, np.sin(u) * np.cos(v)), u_range=[-3, 3], v_range=[-3, 3],
                       resolution=(24, 24), fill_opacity=0.8, checkerboard_colors=[BLUE_D, BLUE_E],
                       stroke_color=BLUE_B, stroke_width=0.5)
        hud = title("z = sin(x) cos(y)", font_size=48)
        self.set_camera_orientation(**gl_orientation(-30, 70))
        self.add_fixed_in_frame_mobjects(hud)
        self.play(FadeIn(hud), Create(ax))
        self.play(Create(surf), run_time=2)
        self.move_camera(**gl_orientation(20, 55), run_time=3)
        self.begin_ambient_camera_rotation(rate=5 * DEG)
        self.wait(3)
        self.stop_ambient_camera_rotation()
```
Notes on 3D:
- 3b1b uses semi-transparent surfaces (opacity 0.5–0.8) with a thin mesh, and a slow ambient rotation of about 1–5°/s under long waits.
- CE's Cairo renderer has no depth test. Keep scenes simple and avoid interpenetrating surfaces.
- Captions (`self.caption`) are automatically fixed in frame in `Tbb3DScene`. The layout audit is skipped in 3D.

---

## Data, probability, ML (vivek3141-style)

### Neural network with signal flow and a probability readout
```python
class NetworkDemo(TbbScene):
    def construct(self):
        nn = NeuralNetwork([3, 6, 6, 2]).scale(0.9).shift(2.8 * LEFT)
        self.play(lagged(Create, nn.layers, lag_ratio=0.3), Write(nn.dots))
        self.play(lagged(Create, nn.edges, lag_ratio=0.2, run_time=2))
        self.play(nn.activate(0, [0.9, 0.2, 0.6]))
        edges = [e for g in nn.edges for e in g]
        self.play(LaggedStart(*[pulse_along(e, color=A_GREEN, stroke_width=3) for e in edges[::2]],
                              lag_ratio=0.005, run_time=2))
        bars = ProbabilityBars(["cat", "dog"], [0.5, 0.5], max_width=3).to_edge(RIGHT, buff=1.2)
        self.play(bars.reveal())
        self.play(bars.animate_to([0.15, 0.85]))
        self.wait()
```
For text models, vivek3141 shows next-token distributions as `ProbabilityBars`. He `Indicate`s the sampled token, `TransformFromCopy`s it into the running sentence, and `FadeOut(..., shift=UP)`s the old distribution as the new one fades in.

### Counting / grid patterns (sum of odd numbers is a square)
```python
class OddSquares(TbbScene):
    def construct(self):
        n = 5
        squares = VGroup()
        layers = VGroup()
        colors = color_gradient([BLUE, TEAL, GREEN, YELLOW, GOLD], n)
        for k in range(n):
            layer = VGroup(*[Square(0.6).set_stroke(WHITE, 1).set_fill(colors[k], 0.85)
                             .move_to([0.6 * i, 0.6 * j, 0])
                             for i in range(k + 1) for j in range(k + 1) if i == k or j == k])
            layers.add(layer)
        layers.move_to(ORIGIN).shift(2 * LEFT)
        sums = tex(*[s for k in range(n) for s in ([str(2 * k + 1)] if k == 0 else ["+", str(2 * k + 1)])],
                   font_size=56).to_edge(RIGHT, buff=1).shift(UP)
        for k, layer in enumerate(layers):
            idx = 0 if k == 0 else 2 * k
            parts_k = sums[idx] if k == 0 else VGroup(sums[idx - 1], sums[idx])
            parts_k.set_color(colors[k])
            self.play(lagged(FadeIn, layer, scale=0.5, lag_ratio=0.05), Write(parts_k), run_time=1)
        result = tex("=", f"{n}^2", font_size=56).next_to(sums, DOWN, buff=0.5)
        self.play(Write(result), FlashAround(layers))
        self.wait()
```

---

## Structure and cards

```python
class Opening(TitleCard):
    title_text = "Why the derivative of x² is 2x"
    subtitle_text = "A visual walkthrough"

class PartTwo(ChapterCard):
    number = 2
    chapter_title = "Checking against the graph"
    color = TEAL

class Hook(QuestionCard):
    question = "Where does the 2 come from?"

class Epigraph(QuoteCard):
    quote = "The art of doing mathematics consists in finding\nthat special case which contains all the germs of generality."
    author = "David Hilbert"
```

### Precise overlap inside one `play` (ManimGL `time_span`)
```python
class Overlap(TbbScene):
    def construct(self):
        ax = tbb_axes()
        dots = VGroup(*[Dot(ax.c2p(x, np.sin(x) + 2)) for x in np.linspace(0, 5, 12)])
        self.play(Create(ax, run_time=3), time_span(lagged(FadeIn, dots), 1.5, 3, 3), run_time=3)
        self.wait()
```

### Narrated paragraph with cues (silent-safe)
Renders silent with sentence captions. With `render.py --voice`, the same code is narrated and the cues use real word timings.

```python
class NarratedGap(TbbScene):
    def construct(self):
        line = tbb_number_line((-4, 4, 1), length=10).shift(UP)
        ra, rb = Dot(line.n2p(1.2), color=GREEN), Dot(line.n2p(-0.5), color=RED)
        with self.voiceover("""Let's say a person looks at two answers to the same question and tells you which one they prefer.
                               What you want is a single number for each answer, a score, so that the preferred one tends to come out ahead.
                               In the business this is called a reward model, and here's the important part.
                               The score on its own doesn't mean much, and what matters is the gap between the two.""") as v:
            self.play(Write(title("Comparisons to scores")))   # runs during sentence 0
            v.wait_until("single number")                       # sync to a phrase as it is spoken
            self.play(Create(line), run_time=v.span(1) * 0.5)
            self.play(FadeIn(ra, rb))
            v.wait_until(3)                                     # sync to the start of sentence 3
            gap = Line(rb.get_center(), ra.get_center(), color=YELLOW, stroke_width=6)
            self.play(Create(gap), run_time=v.until("gap between"))  # lands exactly on the word
        self.wait(0.5)                                          # a visual beat before the next paragraph
```

### Beat transitions
- **Keeper transition:** `self.clear_except(eq)` fades everything except the thing that carries over.
- **Shift-fade:** `FadeOut(old, shift=UP)` together with `FadeIn(new, shift=UP)` moves the content forward.
- **Collapse into a symbol:** `ReplacementTransform(diagram, symbol)` turns a picture into its name.
- **Zoom-through:** in `TbbMovingScene`, zoom into a detail, swap content, then zoom out.
