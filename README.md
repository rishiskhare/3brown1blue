# 3brown1blue

**Ask your coding agent for a math explainer. Get a 3Blue1Brown-style video.**

![MIT license](https://img.shields.io/badge/license-MIT-24292f?style=flat-square)![Manim Community 0.22](https://img.shields.io/badge/Manim_Community-0.22-58C4DD?style=flat-square)![An Agent Skill for Claude Code, Codex, Cursor and other hosts](https://img.shields.io/badge/Agent_Skill-Claude_Code_%7C_Codex_%7C_Cursor-7C3AED?style=flat-square)

Unofficial: not affiliated with or endorsed by 3Blue1Brown or Grant Sanderson. It makes videos *in the style of* 3Blue1Brown.



```bash
npx skills add rishiskhare/3brown1blue -g
```

Then ask in plain words:

- *"Make a 3Blue1Brown-style video explaining why the derivative of x² is 2x."*
- *"Animate the shear matrix [[1,1],[0,1]] acting on the plane, 3b1b style."*
- *"Make a narrated 3b1b-style explainer of how attention works in transformers."*

Your agent plans the explanation, writes the [Manim](https://www.manim.community/) scenes, checks its own frames and hands you an MP4: silent with captions, or narrated by a voice model that runs on your machine.

Ask from any folder. Unless you're already in that video's folder, the agent makes a new one named after the topic and keeps everything in it.

## Why

This skill specifically gives the agent four things:

- **3b1b inspired appearance:** Grant's color palette, Computer Modern font, LaTeX preamble, easing curve, thin strokes, backstroked labels and the 1.5× saturation grade.
- **Grant's teaching philosophy:** One "aha" moment per video, a concrete example before the abstraction, the picture before the formula, one color per idea. These rules come from Grant's own talks and interviews, along with a storyboard format.
- **A voice (optional).** The agent writes the narration and it's spoken locally by the on-device [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) text-to-speech model and animations land on the exact word. Every clip is checked by Whisper, the mix is −16 LUFS, and you get `.srt` subtitles.

## How it works

1. **Plan:** The agent finds the question, the aha and one concrete example, then storyboards 15–60 s scenes.
2. **Review:** A fresh subagent that never saw the agent's reasoning reads the plan cold. It explains the video back, finds where a viewer would get lost, checks the math and returns ranked fixes before any code is written.
3. **Write:** It writes ordinary ManimCE code with the kit's helpers: `tex(..., t2c=...)` colors terms safely, `TransformTex` rearranges equations, `FromCopy` flies a term from where it came from, and there are cards, captions and `voiceover()` blocks.
4. **Check:** `render.py --check` runs every scene with animations skipped and reports every LaTeX and Python error plus the layout warnings in one pass. For a 3-minute video that takes about 4 s.
5. **Draft and look:** It renders a 480p draft with a contact sheet per scene, reads the sheets and fixes what it sees, then a fresh reviewer checks the sheets once more. Re-renders are incremental: unchanged scenes are reused, so a fix costs only the scene it touches.
6. **Final:** It renders 1080p30, Grant's frame rate, with each clip graded as it finishes and joined without re-encoding. A 3-minute video takes about 20 s on an M1 Max.

## Requirements

| | |
|---|---|
| Everyone | Python ≥ 3.11 and Manim Community ≥ 0.22.1: `uv venv && uv pip install "manim>=0.22.1"` |
| macOS | First `brew install cairo pango pkg-config ffmpeg`, and install [MacTeX](https://www.tug.org/mactex/) |
| Debian/Ubuntu | `sudo apt install libcairo2-dev libpango1.0-dev pkg-config python3-dev ffmpeg texlive-latex-extra texlive-fonts-extra texlive-science tipa dvisvgm fonts-cmu` |
| Narration (optional) | [uv](https://docs.astral.sh/uv/), then `python3 <skill>/scripts/narrate.py setup` once (about 2 GB, then offline) |

`<skill>` is the installed `3brown1blue` folder, for example `~/.claude/skills/3brown1blue`. The agent runs this check itself, and you can too:

```bash
python3 <skill>/scripts/check_env.py --python .venv/bin/python
```

The installer asks which agents to install for; `-a claude-code -y` skips the questions. To install by hand, copy `skills/3brown1blue/` into your agent's skills folder.

## FAQ

**Is this ManimGL, Grant's own Manim?** No. It uses Manim Community, which has releases, docs and a renderer that runs headless anywhere. The kit reproduces ManimGL's look on top of it.

**Which agents does it work with?** Any agent that reads [Agent Skills](https://skills.sh) and can run shell commands. It's developed and tested with Claude Code on macOS and Linux.

**Where does narration run?** On your machine. Kokoro-82M (on a CUDA GPU if there is one, else the CPU) and Whisper run locally; setup downloads a pinned model revision with all 28 English voices.

## What's inside

```
skills/3brown1blue/
├── SKILL.md      the workflow the agent follows, plus the kit's API
├── templates/    the style kit (tbb.py), a scene skeleton and manim.cfg
├── scripts/      check_env.py, render.py (check, render, sheets, grade, join, --voice), narrate.py, style_lint.py
├── examples/     a complete ~73 s video
└── references/   pedagogy, style guide, tested idioms, gotchas, ManimGL porting, narration, review brief
tests/            unit tests and selftest.py (runs every idioms.md recipe, the example and the template)
```

## Development

```bash
python -m unittest discover -s tests     # unit tests (the tbb ones need manim)
python tests/selftest.py -j 4            # runs every idioms.md recipe, the example and the template
```

## Credits and license

MIT (see `LICENSE`; the installed skill carries the same text as `LICENSE.txt`).

- **3Blue1Brown:** the skill describes the style and reimplements it independently. Its style numbers (stroke widths, timings, color use) were measured from [3b1b/videos](https://github.com/3b1b/videos), and none of that code is included. The palette values and the "smooth" easing match [3b1b/manim](https://github.com/3b1b/manim) (MIT). The Pi creatures and the logo are copyrighted, and the skill tells agents not to recreate them. The skill is MIT and contains no code from [3b1b/videos](https://github.com/3b1b/videos), which is non-commercial, and it tells agents never to draw the Pi creatures or the 3b1b logo.
- **Grant Sanderson's words:** `pedagogy.md` and `narration-style.md` quote short excerpts from his videos and interviews for commentary (© Grant Sanderson / 3Blue1Brown). The sources are the [3Blue1Brown channel](https://www.youtube.com/@3blue1brown), the Lex Fridman Podcast [#64](https://www.youtube.com/watch?v=U_lKUK2MCsg) and #118, the [SoME1](https://www.youtube.com/watch?v=F3Qixy-r_rQ) and [SoME2](https://www.youtube.com/watch?v=cDofhN-RJqg) results, and ["Advice for using Manim"](https://www.youtube.com/watch?v=ruUfqQPDdDs).
- **Models:** [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache-2.0) for narration and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT) for transcription checks.
