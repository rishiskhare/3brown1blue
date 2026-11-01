# Review: fresh eyes on the plan and the draft

When you've written a plan, you read it as what you meant rather than what's on the page. Grant shows early cuts to his patrons before release and revises where they get lost. This step does the same job with a reviewer who has never seen your reasoning. Re-reading your own work rarely finds new problems; this review can because it brings in three things you lack: a fresh context, a test of whether the video can be explained back, and math that is checked by running it.

## Running it (for the author)

- **Two gates, one round each.**
  1. *Plan:* once the plan is in `video.py`'s docstring, before you write any scene code.
  2. *Draft:* after the first `--sheet` render with no errors, and with every `layout:` warning fixed or knowingly accepted, before the final render.
- **Skip both gates for a single-scene clip** (one animation with no storyboard, such as "animate this shear"): there, a review costs more than it can save.
- **Spawn a subagent with fresh context** (in Claude Code, the Agent tool; on other hosts, their subagent feature). Pass only paths, for example: *"Review `<abs path>/video.py`, gate: plan. Follow `<skill>/references/review.md`, section 'Reviewer brief'. Return only the report."* For the draft gate, add the sheet folder `media/sheets/video/`. Don't describe your intent and don't say what you think works: either one biases the review.
- **No subagent available?** Do the review yourself as a separate pass. Re-read this file and the rubric files first, then read the plan from the top as a stranger would.
- **Triage the report yourself.** Fix every blocker, but first confirm each math finding yourself by running it: reviewers sometimes "correct" math that was right. Apply a suggestion unless it conflicts with the user's request or with the rubric, and if you reject one, say why in one line. Don't run a second round unless the aha, the example or the arc changed. Don't ask the user about the review. In the final report, give one line on what it changed.

## Reviewer brief

You are an early viewer and an editor. You see only the files, not the author's reasoning. **Don't edit any file.**

**Read:**
- the docstring of the scene file (the plan: question, aha, example, storyboard and, if narrated, the script)
- `pedagogy.md` (in this folder)
- for a narrated video, the "Rules" and "Anti-patterns" sections of `narration-style.md`
- at the draft gate, every contact sheet (`<Scene>.png`): 12 frames evenly spaced through the scene, read left to right and top to bottom. With `--voice`, the frames carry no captions, so match them against that scene's script paragraphs in order. Read the scene code only to find where something happens.

**1. Explain it back.** Before you judge anything, write one sentence per scene: what a smart viewer who didn't know the topic would understand after that scene. Then name the first moment they would get lost or bored, and why. If you can't write the explain-back from the plan alone, that is the top finding.

**2. Check the math.** Verify every claim, number and formula, and compute the concrete example's numbers (run Python if you can). Check that the aha is true *and* is the actual reason, not just something that happens alongside it. Wrong math is always a blocker.

**3. Check the rubric.**
- *Hook:* a concrete question or picture is on screen within 20 s, with no agenda opener.
- *One aha:* everything before it builds toward it, it gets the most time and the slowest pace, and nothing after it competes with it.
- *Concrete before abstract:* the example comes before the general statement. Every formula has a source, meaning its pieces are on screen before it appears.
- *Motivation:* each new idea arrives already half-intuited, ideally after a naive attempt that fails.
- *Load:* each beat brings one new thing, with no more than about 3 focal elements. The plan says what gets dimmed or cleared.
- *Color:* one color per concept, the same in formulas and pictures across all scenes.
- *Length:* each scene is 15–60 s, and the total fits the scope (60–180 s for a single idea).
- *Silent:* captions are 12 words or fewer, say what the picture means rather than describe it, and are never redundant.
- *Narrated:* none of the anti-patterns. Sentence length varies. "This + noun" points at what's on screen. Things are named only after they're shown, and symbols are read in words.
- *Ending:* the result restated in one line, with no new ideas.
- *Draft gate, each sheet:* do the frames show the scene's beats in the planned order, with each caption (or script paragraph) matching its picture? Look for overlaps, off-frame or unreadable text, labels over content, ugly in-between frames, color drift and too much motion at once. Three or more identical frames in a row is dead air.

**4. Report** in exactly this format: at most 8 findings, most important first.

```
VERDICT: ship | revise
EXPLAIN-BACK:
  <Scene>: <one sentence>
LOST AT: <Scene / beat>: <why>   (or "nowhere")
MATH: <ok, or each error with the correct value>
FINDINGS:
1. [blocker|suggestion] <Scene / beat>: <the problem as the viewer experiences it>. Rule: <which>. Fix: <a concrete change>.
```

A **blocker** is any of these: wrong math, a missing or unclear aha, a step a viewer can't follow, a formula with no source, or a visual bug visible on a sheet. Everything else is a suggestion.

- Report problems only: no praise, and don't restate the plan.
- One structural finding beats five cosmetic ones.
- Don't propose additions that lengthen the video unless the aha fails without them.
- "ship" with no findings is a valid result.
