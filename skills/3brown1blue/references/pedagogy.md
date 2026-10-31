# How 3Blue1Brown explains, and how to storyboard a silent version

3b1b's look is the easy half. The hard half is the explanation design. These principles come from Grant Sanderson's own words (Lex Fridman Podcast #64 and #118, the SoME1 and SoME2 results videos, "Advice for using Manim"). Quotations are short excerpts © Grant Sanderson / 3Blue1Brown, used for commentary and analysis; this skill is not affiliated with 3Blue1Brown.

## Grant's principles

1. **Concrete before abstract.** "Always it will be more compelling and easier to understand when you … let someone's brain do the pattern recognition: you just show them a bunch of examples … then by the time you bring in the definition or the formula, it's articulating a thing that's already in the brain." Start at the lowest level you can: concrete lists of numbers, a single arrow.
2. **Visuals force concreteness, and that is the point.** Every image commits to a specific example, and each specific example helps the viewer.
3. **Motivate, at two scales.**
   - *Macro*: hook the whole video with a tangible question or puzzle. Get to the point fast and save the philosophising for the end.
   - *Micro*: every new idea should arrive already half-intuited, so the equation "articulates something that already exists loosely in the viewer's mind." A good template is a naive but flawed attempt, which the video then refines.
4. **Clarity is how slowly you burn the viewer's focus.** Keep one or two examples front and centre. Play with them, tweak them, push them to edge cases. Introduce one pattern at a time.
5. **Use the visual channel implicitly.** When making a general point, show a specific example on screen without dwelling on it.
6. **Clean and to the point beats pretty.** The best visuals direct attention to the details that matter.
7. **Script first, built around one aha moment.** "I'll write the script, I want there to be some kind of aha moment in there and then hopefully the script can revolve around [it]." Then visuals go to each sentence. A script is done when someone who didn't understand could now follow.
8. **Animate programmatically only what benefits from code.** That means motion that relates inputs to outputs (transformations, vector fields, parameter sweeps), and things that scale with loops or parameters.
9. **The goal is ownership.** "My goal is for you to come away … feeling like you could have invented calculus."
10. **Leave room to think.** Pause-and-ponder moments. Optional depth for the curious that doesn't bog down everyone else.

## Turning a topic into a script

Fill in this template before writing code:

```
QUESTION (hook, <= 20 s on screen):   Why ... ?  /  What happens if ... ?
AHA (the one moment):                 ...
CONCRETE EXAMPLE (kept on screen):    ...   PARAMETER TO VARY: ...
NAIVE ATTEMPT (optional):             ... and why it fails
ARC:
  1. Hook       - pose the question with a concrete picture
  2. Explore    - play with the example; let a pattern show itself
  3. Aha        - the key visual insight, given the most time
  4. Formalise  - the formula appears as a label for what's on screen
  5. Check      - verify on a second example / the graph / numbers
  6. Takeaway   - one-line summary; optional generalisation or "what's next"
```

Keep videos short unless asked otherwise: 60–180 s for a single idea and 3–8 minutes for a lesson. A single aha rarely needs more than 2 minutes in silent form.

## Storyboard format

Write it as a table and keep it in a docstring at the top of the scene file:

| Scene | Beat | Visual | Caption (≤ 12 words) | s |
|---|---|---|---|---|
| Opening | title | TitleCard | | 5 |
| GrowingSquare | set up | square, brace labels x, area x² | A square with side x has area x². | 6 |
| | nudge | strips grow from the edges | Now grow each side by a tiny amount, dx. | 4 |
| | read off | copies fly from the strips into the equation | Two thin strips, plus one tiny corner. | 8 |
| | aha | corner dims, equation simplifies, boxed result | Divide by dx: the area grows at a rate of 2x. | 8 |

Guidelines:

- **One scene class per row group, 15–60 s.** Short scenes render fast in parallel and are easy to redo.
- **Each beat has exactly one new thing on screen.** If a beat introduces two things, split it.
- **Every formula has a source.** Before it appears, the pieces it summarises should already be visible, so they can fly in with `FromCopy`.
- **Plan dimming.** At each beat, decide what the viewer should ignore, and dim or clear it.
- **Plan the colour key** before the first scene: each concept gets a colour, defined once as a constant.

## Silent-video adaptation

Audio is excluded, so the narration has to become visual or textual:

| Narrated 3b1b | Silent version |
|---|---|
| Voice explains while the picture moves | A caption names the beat; the picture does the explaining |
| "Notice that…" | Highlight it (`FlashAround`, dim the rest), then caption it |
| "Pause and ponder" | A question caption plus a 3–5 s hold on the frozen picture |
| Asides and jokes | Cut them |
| Long derivation spoken over a static formula | Step-by-step `TransformTex` with each step held for reading |
| Pi-creature reaction shots | A `QuestionCard` ("But why?") or a speech bubble, never the creatures |

Caption style:
- Present tense, concrete, ≤ 12 words.
- No more than one caption per beat.
- Never caption what is obvious from the picture. Caption the meaning ("…so the corner is negligible").

Text that appears inside the picture, such as labels and equations, counts toward reading load. When a caption and a new equation arrive together, give the beat extra hold.

## Scope and quality checklist

- [ ] The hook question is on screen within 20 s.
- [ ] There is exactly one aha, and it gets the most screen time and the slowest pacing.
- [ ] Every formula is preceded by the picture it summarises.
- [ ] Colours are consistent for every concept across all scenes.
- [ ] No frame has more than about 3 focal elements; non-focus content is dimmed or cleared.
- [ ] Every caption is readable in its hold time, and no caption covers content.
- [ ] Contact sheets were inspected for every scene, with no overlaps or off-frame content.
- [ ] The ending restates the result in one line and doesn't introduce new ideas.
