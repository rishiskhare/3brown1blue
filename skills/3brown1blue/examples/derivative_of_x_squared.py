"""Example: "Why is the derivative of x^2 equal to 2x?" — a complete silent explainer.

Render (from a folder containing this file and a copy of tbb.py):
    python3 <skill>/scripts/render.py derivative_of_x_squared.py --sheet -j 4       # 480p draft + sheets
    python3 <skill>/scripts/render.py derivative_of_x_squared.py -q h --fps 30 -j 4 # final

Story (one aha): a square of side x grows by a sliver dx; the new area is two thin strips
plus a negligible corner, so d(x^2) ~= 2x dx. Then we check the claim against the slope of
the graph. Concrete picture first, formula second, verification last.
"""
from manim import *
from tbb import *

SCENES = ["Opening", "GrowingSquare", "SlopeCheck", "Takeaway"]

X_COL = BLUE          # the side length x, everywhere
DX_COL = YELLOW       # the nudge dx, everywhere
STRIP_COL = TEAL      # area x*dx


class Opening(TitleCard):
    title_text = "The derivative of x²"
    subtitle_text = "seen as a growing square"


class GrowingSquare(TbbScene):
    side = 3.0
    dx = 0.45

    def construct(self):
        s, dx = self.side, self.dx

        # Set up the square
        square = Square(side_length=s).set_stroke(WHITE, 2).set_fill(BLUE_E, 0.9)
        square.move_to(3.2 * LEFT + 0.2 * DOWN)
        bottom = brace_label(square, "x", DOWN, color=X_COL, font_size=44)
        left = brace_label(square, "x", LEFT, color=X_COL, font_size=44)
        area = tex("x^2", font_size=60).move_to(square)
        self.play(DrawBorderThenFill(square), run_time=1.5)
        self.play(GrowFromCenter(bottom[0]), FadeIn(bottom[1], shift=0.2 * UP),
                  GrowFromCenter(left[0]), FadeIn(left[1], shift=0.2 * RIGHT))
        self.play(Write(area))
        self.caption("A square with side x has area x².")

        # Nudge the side by dx
        right_strip = Rectangle(width=dx, height=s).set_stroke(WHITE, 1).set_fill(STRIP_COL, 0.85)
        right_strip.next_to(square, RIGHT, buff=0)
        top_strip = Rectangle(width=s, height=dx).set_stroke(WHITE, 1).set_fill(STRIP_COL, 0.85)
        top_strip.next_to(square, UP, buff=0)
        corner = Square(side_length=dx).set_stroke(WHITE, 1).set_fill(DX_COL, 0.9)
        corner.next_to(right_strip, UP, buff=0)
        dx_label = label(right_strip, "dx", DOWN, color=DX_COL, font_size=36)
        self.caption("Now grow each side by a tiny amount, dx.", hold=0,
                     added_anims=[FadeOut(bottom), FadeOut(left)])
        self.play(LaggedStart(GrowFromEdge(right_strip, LEFT), GrowFromEdge(top_strip, DOWN),
                              GrowFromEdge(corner, DL), lag_ratio=0.4), FadeIn(dx_label), run_time=2)
        self.wait()

        # Read off the new area
        eq = tex(r"d(x^2)", "=", r"x\,dx", "+", r"x\,dx", "+", r"(dx)^2", font_size=52)
        eq.to_edge(RIGHT, buff=0.6).shift(1.2 * UP)
        eq[2].set_color(STRIP_COL)
        eq[4].set_color(STRIP_COL)
        eq[6].set_color(DX_COL)
        self.caption("How much new area did that add?", hold=0.5)
        self.play(Write(eq[:2]))
        self.play(FromCopy(right_strip, eq[2]))
        self.play(Write(eq[3]), FromCopy(top_strip, eq[4]))
        self.play(Write(eq[5]), FromCopy(corner, eq[6]))
        self.caption("Two thin strips, plus one tiny corner.")

        # The corner doesn't matter
        self.play(FlashAround(corner, color=DX_COL), FlashAround(eq[6], color=DX_COL))
        self.caption("As dx shrinks, the corner shrinks far faster: it is negligible.", hold=0,
                     added_anims=[*dim(eq[5], eq[6], corner)])
        self.wait(1.5)

        simplified = tex(r"d(x^2)", r"\approx", r"2x\,dx", font_size=52).move_to(eq, LEFT)
        simplified[2].set_color(STRIP_COL)
        self.play(TransformTex(eq, simplified, key_map={"=": r"\approx", r"x\,dx": r"2x\,dx"}),
                  run_time=2)
        ratio = tex(r"{d(x^2) \over dx}", "=", "2x", font_size=60).next_to(simplified, DOWN, buff=1.0)
        ratio.align_to(simplified, LEFT)
        ratio[2].set_color(STRIP_COL)
        self.play(FromCopy(simplified, ratio))
        box = highlight_rect(ratio, buff=0.2)
        self.play(Create(box))
        self.caption("Divide by dx: the area grows at a rate of 2x.")
        self.caption(None, hold=0.5)


class SlopeCheck(TbbScene):
    def construct(self):
        # Set up the graph
        ax = tbb_axes(x_range=(0, 3, 1), y_range=(0, 9, 3), x_length=6.5, y_length=5.2)
        ax.to_edge(LEFT, buff=1.0).to_edge(UP, buff=0.6)  # stay above the caption band
        graph = ax.plot(lambda x: x**2, x_range=[0, 3], color=X_COL, stroke_width=3)
        graph_label = label(graph.get_end(), "y = x^2", LEFT, color=X_COL, font_size=36, buff=0.3)
        self.play(Create(ax), run_time=1.5)
        self.play(Create(graph), FadeIn(graph_label))
        self.caption("Check it against the graph of y = x².")

        # Slide a tangent line along it
        x = ValueTracker(0.6)
        dot = tracked_dot(ax, graph, x, color=DX_COL)
        tangent = tangent_line(ax, graph, x, length=3.2, color=DX_COL)

        def slope():
            h = 1e-4
            return ((x.get_value() + h) ** 2 - (x.get_value() - h) ** 2) / (2 * h)

        rows = VGroup(
            VGroup(MathTex(r"x =", font_size=44), live_number(x, font_size=44, color=X_COL)),
            VGroup(MathTex(r"\text{slope} =", font_size=44), live_number(slope, font_size=44, color=DX_COL)),
            VGroup(MathTex(r"2x =", font_size=44), live_number(lambda: 2 * x.get_value(), font_size=44, color=STRIP_COL)),
        )
        for row in rows:
            row[1].always.next_to(row[0], RIGHT, buff=0.2)
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.45).to_edge(RIGHT, buff=1.3).shift(0.6 * UP)
        for row in rows:
            row[1].next_to(row[0], RIGHT, buff=0.2)

        self.play(FadeIn(dot, scale=0.5), Create(tangent), lagged(FadeIn, rows, shift=0.2 * LEFT, lag_ratio=0.2))
        self.caption("The tangent's slope always equals 2x.", hold=0)
        self.play(x.animate.set_value(2.6), run_time=4)
        self.play(x.animate.set_value(1.2), run_time=3)
        self.play(FlashAround(VGroup(rows[1], rows[2])))
        self.wait()
        self.caption(None, hold=0.5)


class Takeaway(TbbScene):
    def construct(self):
        result = tex(r"{d \over dx}", "x^2", "=", "2x", font_size=96)
        result[1].set_color(X_COL)
        result[3].set_color(STRIP_COL)
        self.play(Write(result))
        self.caption("Two strips of area x·dx: that's where the 2 comes from.", t2c={"x·dx": STRIP_COL})
        self.play(FlashAround(result[3], color=STRIP_COL))
        self.caption(None, hold=1)
        self.play(FadeOut(result))
