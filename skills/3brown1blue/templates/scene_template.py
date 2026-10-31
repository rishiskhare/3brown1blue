"""<Video title>

QUESTION: <the hook, on screen within 20 s>
AHA:      <the one moment this video exists for>
EXAMPLE:  <the concrete example kept on screen>   VARY: <parameter>

Storyboard
| Scene    | Beat     | Visual                          | Caption (<= 12 words)            | s |
|----------|----------|---------------------------------|----------------------------------|---|
| Opening  | title    | TitleCard                       |                                  | 5 |
| Hook     | question | the concrete picture + question | <question>                       | 6 |
| Explore  | ...      | ...                             | ...                              |   |
| Aha      | ...      | ...                             | ...                              |   |
| Takeaway | summary  | boxed result                    | <one-line takeaway>              | 6 |

Render:  python3 <skill>/scripts/render.py <this file> --check        (seconds: all errors + stills)
         python3 <skill>/scripts/render.py <this file> --sheet        (draft, inspect the new sheets)
         python3 <skill>/scripts/render.py <this file> -q h --fps 30  (final)
"""
from manim import *
from tbb import *

SCENES = ["Opening", "Hook", "Takeaway"]

# Colour key: one colour per concept, used in formulas and pictures alike.
MAIN_COL = BLUE
ACCENT_COL = YELLOW
OTHER_COL = RED


class Opening(TitleCard):
    title_text = "Video title"
    subtitle_text = "A visual explanation"


class Hook(TbbScene):
    def construct(self):
        # Set up the concrete picture
        shape = Circle(radius=1.5, color=MAIN_COL, stroke_width=3).set_fill(MAIN_COL, 0.3)
        self.play(Create(shape))
        self.caption("Start with one concrete example.")

        # Pose the question
        question = title("Why does this happen?")
        self.play(FadeIn(question[0], lag_ratio=0.1), Create(question[1]))
        self.play(FlashAround(shape, color=ACCENT_COL))
        self.wait()
        self.caption(None, hold=0.5)

        # Narrated videos (render.py --voice) replace the captions with voiceover paragraphs:
        # with self.voiceover("""Start with one concrete example, a circle. Now here's the
        #                        question that this whole video is about.""") as v:
        #     self.play(Create(shape))
        #     v.wait_until("question")
        #     self.play(FadeIn(question[0], lag_ratio=0.1), Create(question[1]))


class Takeaway(TbbScene):
    def construct(self):
        result = tex(r"{a}^2 + {b}^2 = {c}^2", t2c={"{a}": MAIN_COL, "{b}": OTHER_COL, "{c}": ACCENT_COL},
                     font_size=84)
        self.play(Write(result))
        box = highlight_rect(result, buff=0.25)
        self.play(Create(box))
        self.caption("The one-line takeaway goes here.")
        self.caption(None, hold=1)
        self.play(FadeOut(VGroup(result, box)))
