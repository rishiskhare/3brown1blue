# Narration: local, production-grade voice-over

Narrated videos are written **script first**, the way 3b1b videos are made: narration paragraph, then voice, then animation timed to the voice. Use `self.voiceover(paragraph)` blocks. The same scene code also renders silent, with each sentence shown as a caption at speaking pace.

```bash
python3 <skill>/scripts/narrate.py setup                       # once per machine: ~1 GB venv in ~/.cache/tbb-tts + ~1 GB of weights in the Hugging Face cache; offline afterwards
python3 <skill>/scripts/render.py video.py --voice --sheet      # draft with voice
python3 <skill>/scripts/render.py video.py -q h --fps 30 --voice   # final
```

## Contents

- The scene API
- Writing narration
- Pipeline
- Voice
- Troubleshooting (all verified)

## The scene API

The complete, runnable example is `NarratedGap` in `idioms.md` (Structure and cards): one paragraph, with animations synced to a phrase, a sentence start and a word. Leaving the block waits for the speech, plus a 0.35 s breath, to finish.

| Call | Meaning |
|---|---|
| `v.wait_until(i)` | Wait until sentence `i` (0-based) starts. |
| `v.wait_until("phrase", offset=0)` | Wait until those words are spoken. Matching uses the spoken words, so `"β"` matches "beta". A phrase spoken twice matches its next occurrence that hasn't passed. |
| `v.until(cue)` | Seconds from now until a cue. Use it as `run_time=` so a motion lands exactly on a word. |
| `v.span(i)` | Length of sentence `i`. |
| `v.remaining` | Seconds left in the paragraph. |
| `v.at(cue)` | Absolute scene time of a cue. |
| `captions=[...]` | One on-screen line per sentence, when the written form should differ from the spoken one (math). |
| `show=False` | Narrate without drawing captions (they still go to the `.srt`). |
| `t2c={...}` | Colour words in the captions, as in `caption()`. |

How timing works:
- Cue times come from Kokoro's word timestamps; without audio they are estimated at about 2.9 words/s (~175 wpm).
- A cue the speech has already passed doesn't wait: the animation simply runs late.
- A phrase the narration doesn't contain raises an error. That error also fires in the fast collect pass, so typos surface before rendering.

`self.caption(line)` still works for silent-first videos, and gets spoken too with `--voice`. For anything meant to be narrated, use `voiceover`: one paragraph synthesised in a single pass has natural intonation, while separately spoken lines sound like a list being read out.

## Writing narration

**Read `narration-style.md` before writing a narrated script.** Two mechanics specific to tbb:
- **One `voiceover` block per beat cluster** (about 60–200 words). Start a new block wherever the visuals need to pause or reset. Between blocks, `self.wait(0.5–1.5)` is the natural breath.
- **Keep the narration nearly continuous.** Narrate over long animations, or shorten them with `v.until(...)` and `v.span(...)`, rather than leaving silence.

## Pipeline

1. **Collect.** Every changed scene runs in parallel with animations skipped (`-s`) and `TBB_AUDIO=collect`. Each `voiceover`/`caption` records its spoken text in `media/voice/lines/<file>/<Scene>.jsonl`; they are merged, in scene order, into `media/voice/<file>_lines.jsonl`. The full script is also written to `final/<file>_narration.txt`.
2. **Synthesise.** Kokoro synthesises every paragraph not already cached as one clip, `media/voice/audio/<key>.wav` plus `<key>.json` with word timestamps. The key hashes the voice, speed and text, so editing one paragraph re-synthesises only that paragraph, and output is reproducible.
3. **QA.** Whisper (`faster-whisper base.en`) transcribes every new clip (results are cached per clip) and diffs it against the script, alongside the render pass. A word error rate above 0.25 is flagged, along with what was heard.
4. **Render.** With `TBB_AUDIO=on` (and manim's cache disabled), blocks add their clip and time cues from the real timestamps. Burned-in captions are off unless `--captions` is passed; subtitle cues are recorded either way.
5. **Mix.** Each scene's audio is padded to its video length (no drift across cuts), and the joined track is normalised to **−16 LUFS**. Subtitles go to a sidecar `.srt` (upload it with the video); `--embed-subs` also embeds a soft track, which many players show automatically.
6. **Audio check.** The final cut is scanned for silence. The check reports the voiced percentage (3b1b runs about 85–90%) and every gap over 4 s, with its scene.

## Voice

The default is Kokoro-82M (Apache-2.0) with the **`am_michael` voice at speed 1.0**, a calm US male. It's small (82M parameters) and runs on CPU several times faster than real time. It isn't autoregressive, so it doesn't drift or babble on long text, and the Whisper QA pass still checks every clip.

- `narrate.py voices` lists the 28 English voices; audition one with `narrate.py say "..." --voice bm_george` (same seed as a render, so it sounds exactly like the final line).
- Switch with `--voice-name`, and keep one voice for the whole video. A misspelled name stops render.py before any rendering, with a suggestion.

## Troubleshooting (all verified)

| Symptom | Cause and fix |
|---|---|
| Narration sounds choppy or robotic | It was written as caption fragments, or as many `caption()` lines. Rewrite it as `voiceover` paragraphs of connected prose. |
| Long silences while things animate | The animation is longer than its narration. Narrate over it, or shorten `run_time` with `v.until(...)` / `v.span(...)`. |
| `cue '...' not found in narration` | The phrase isn't in the paragraph's spoken words. Check spelling, and remember symbols are matched by their spoken form. |
| `Error processing file '/Users/runner/.../phontab'` | espeak-ng ignores data paths longer than ~160 characters. Keep the TTS venv at a short path (setup uses `~/.cache/tbb-tts`; override with `TBB_TTS_HOME`). |
| `tbb voice: no audio for '...'` | The text changed between the collect and render passes, or the render ran without `--voice`. Re-run with `--voice`. |
| QA `FLAG` | Usually an unspeakable symbol. Spell it out in the narration, or delete the files the `fix:` line lists to force re-synthesis. |
| The final cut has long silent stretches while the visuals and subtitles continue (the `Audio check:` line reports big gaps) | ManimCE 0.22 misplaces `add_sound` audio after cached animations, so each scene's speech piles into its first seconds. `render.py --voice` always passes `--disable_caching`. If you call manim directly, pass `--disable_caching` yourself. |
| "Answer A" is spoken as "Answer uh", or two sentences run together after "...pick B." | These are G2P quirks with single capital letters. `narrate.py` rewrites letter names with misaki phoneme overrides (`[A](/ˈA/)`), keeping the sentence punctuation, while a sentence-initial article ("A reward model…") stays an article. For any other misread word, write the override in the narration yourself, e.g. `[Kokoro](/kˈOkəɹO/)`. It reaches the TTS intact, and captions and subtitles show just the word. |
| `cannot find narrate.py: run render.py from the skill's scripts/ folder, or set TBB_SKILL_DIR` | `render.py` was copied into the project. Run it by path from the skill folder (`python3 <skill>/scripts/render.py`). A copy still finds a skill installed in `./.claude/skills`, `./.agents/skills` or the same folders under `~`, or the folder in `TBB_SKILL_DIR`. |
| Subtitles show although captions are off | An embedded subtitle track (`--embed-subs`) gets flagged default in MP4, and players show it. Leave embedding off and use the sidecar `.srt`. |
