#!/usr/bin/env python3
"""Local text-to-speech for tbb narration (Kokoro-82M), plus a Whisper QA pass.

The TTS stack lives in its own venv (default ~/.cache/tbb-tts, override with TBB_TTS_HOME) so torch
never touches the manim environment. Run this script with any Python 3: commands that need the
TTS libraries re-execute themselves inside that venv.

    python3 narrate.py setup                                  # once per machine
    python3 narrate.py voices                                 # list Kokoro voices
    python3 narrate.py say "Some sentence." -o t.wav --voice am_michael   # audition a voice
    python3 narrate.py synth media/voice/video_lines.jsonl --out media/voice/audio   # (render.py --voice)
    python3 narrate.py qa media/voice/video_lines.jsonl --audio media/voice/audio    # Whisper check
    python3 narrate.py check-voice am_michael                 # exit 2 (with a suggestion) if unknown
    python3 narrate.py python                                 # print the TTS interpreter (exit 2 if missing)

Each lines-file row is {"key", "say", "sentences", "voice", "speed", ...}; audio goes to <out>/<key>.wav
with <key>.json holding word timings, and existing clips are skipped. Each line is seeded from its
key, so with the pinned packages (a new venv resolves them as they were on 2026-10-20) and Kokoro
revision the same text gives identical audio, and `say` sounds exactly like a render. A voice may
be a blend: "af_bella,af_heart".

Environment: TBB_TTS_HOME (venv location), TBB_QA_MODEL (Whisper model for qa; default base.en).
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

TTS_HOME = Path(os.environ.get("TBB_TTS_HOME", Path.home() / ".cache" / "tbb-tts"))
SAMPLE_RATE = 24000
DEFAULT_VOICE, DEFAULT_SPEED = "am_michael", 1.0   # calm US male
# Pinned: audio caching assumes identical output. Bump TTS_REVISION (here and in tbb.py) when
# changing any of these. PINNED_AT freezes the transitive dependencies (torch, numpy, spaCy, ...):
# uv resolves only releases published before it.
TTS_REVISION = 2   # must equal tbb.TTS_REVISION: narration keys (and so seeds) are built from it
PINNED_AT = "2026-10-20T00:00:00Z"
PACKAGES = ["kokoro==0.9.4", "misaki[en]==0.9.4", "soundfile==0.14.0", "faster-whisper==1.2.1",
            "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/"
            "en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"]
KOKORO_REPO, KOKORO_REVISION = "hexgrad/Kokoro-82M", "f3ff3571791e39611d31c381e3a41a3af07b4987"
QA_MODEL = os.environ.get("TBB_QA_MODEL", "base.en")
KOKORO_VOICES = {
    # Grades from hexgrad/Kokoro-82M VOICES.md; a = American, b = British.
    "am_michael": "C+  US male, calm (tbb default)", "am_fenrir": "C+  US male", "am_puck": "C+  US male",
    "bm_george": "C   UK male, measured", "bm_fable": "C   UK male", "af_heart": "A   US female, warm",
    "af_bella": "A-  US female, bright", "af_nicole": "B-  US female, soft", "af_sarah": "C+  US female",
    "bf_emma": "B-  UK female",
}
# Every English voice at KOKORO_REVISION (a/b = US/UK, the G2P installed here; f/m = female/male).
ENGLISH_VOICES = frozenset(
    "af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky "
    "am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa "
    "bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis".split())
_WORD = re.compile(r"[A-Za-z0-9']+")
_MARKUP = re.compile(r"\[([^\]]+)\]\((/[^)]*/)\)")  # misaki phoneme override: [word](/phonemes/)


def strip_markup(s: str) -> str:
    return _MARKUP.sub(r"\1", s)


def narration_key(say: str, voice: str, speed: float) -> str:
    """The clip key tbb.narration_key() computes for the same line (tests keep them in sync)."""
    return hashlib.sha1(f"kokoro|r{TTS_REVISION}|{voice}|{float(speed)}|{say}".encode()).hexdigest()[:16]


def venv_python() -> Path:
    return TTS_HOME / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def not_set_up() -> str:
    return f"Narration isn't set up (no {venv_python()}). Run once:\n  python3 {shlex.quote(__file__)} setup"


def ensure_tts_python(argv: list[str]) -> None:
    """Re-execute inside the TTS venv unless we are already running there."""
    py = venv_python()
    if not py.exists():
        sys.exit(not_set_up())
    if Path(sys.prefix).resolve() != py.parent.parent.resolve():
        if os.environ.get("TBB_TTS_REEXEC"):  # we already re-executed and still aren't in the venv
            sys.exit(f"The TTS venv at {py.parent.parent} is broken (its python isn't a venv). "
                     f"Delete it and run setup again:\n  python3 {shlex.quote(__file__)} setup")
        os.environ["TBB_TTS_REEXEC"] = "1"
        if os.name == "nt":  # Windows execv spawns and returns at once: the caller would see success
            sys.exit(subprocess.call([str(py), __file__, *argv]))
        os.execv(str(py), [str(py), __file__, *argv])


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------
def setup() -> int:
    uv = shutil.which("uv")
    if not uv:
        print("uv is required: curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
        return 1
    py = venv_python()
    venv = py.parent.parent
    if len(str(venv)) > 100:  # espeak-ng silently ignores data paths longer than ~160 characters
        print(f"warning: {venv} is a long path; espeak-ng may fail. Set TBB_TTS_HOME to a short path.",
              file=sys.stderr)
    if not py.exists():
        subprocess.run([uv, "venv", "--python", "3.12", str(venv)], check=True)
    subprocess.run([uv, "pip", "install", "--exclude-newer", PINNED_AT, *PACKAGES], check=True,
                   env=dict(os.environ, VIRTUAL_ENV=str(venv)))
    # Download every model now (with progress bars) so renders and QA also work offline later.
    env = dict(os.environ, HF_HUB_DISABLE_PROGRESS_BARS="0")
    probe = TTS_HOME / "probe.wav"  # smoke test; fetches the pinned Kokoro weights and default voice
    rc = subprocess.run([str(py), __file__, "say", "Setup complete.", "-o", str(probe)], env=env).returncode
    if rc == 0:  # every English voice pack (~0.5 MB each) at the pinned revision
        patterns = [f"voices/{v}.pt" for v in sorted(ENGLISH_VOICES)]
        rc = subprocess.run([str(py), "-c", "from huggingface_hub import snapshot_download; "
                             f"snapshot_download({KOKORO_REPO!r}, revision={KOKORO_REVISION!r}, "
                             f"allow_patterns={patterns!r})"], env=env).returncode
    if rc == 0:
        rc = subprocess.run([str(py), "-c", "from faster_whisper import WhisperModel; "
                             f"WhisperModel({QA_MODEL!r}, device='cpu', compute_type='int8')"], env=env).returncode
    if rc == 0:
        print(f"\nOK: narration ready ({py}). Probe audio: {probe}")
    return rc


# ---------------------------------------------------------------------------
# Text fixes for Kokoro's G2P
# ---------------------------------------------------------------------------
# Single capital letters used as names ("answer A", "prefers A over B") trip two G2P quirks:
#  1. a bare "A" is often read as the article ("uh"), even mid-sentence;
#  2. a letter before sentence punctuation ("pick B. Then...") is taken for an initial and the
#     period is swallowed, so the sentences run together with no pause.
# Both are fixed with misaki's inline phoneme syntax, keeping the punctuation inside the override.
# A sentence-initial "A" before an ordinary word ("A reward model...") stays an article.
_A_LETTER_NEXT = {"is", "was", "wins", "won", "beats", "has", "had", "gets", "got", "and", "or", "over",
                  "versus", "vs", "scores", "loses", "ties", "comes", "goes", "ends", "minus", "plus",
                  "equals", "would", "will", "should", "can", "could", "might", "must", "does", "did",
                  "now", "then", "still", "always", "never", "also", "only", "just", "itself", "here",
                  "there", "above", "below", "first", "second", "ahead", "behind", "times"}
_LETTER = re.compile(r"(?<![\w\[\]./])([A-Z])(?![\w\]])([.!?]?)")


def kokoro_text(text: str, letter_phonemes=None) -> str:
    """Rewrite single-letter names for Kokoro. `letter_phonemes(ch)` returns misaki phonemes for a
    letter name (needed only for letters before sentence punctuation; "A" is built in)."""

    def repl(m):
        ch, punct = m.group(1), m.group(2)
        before, after = text[:m.start()], text[m.end():]
        if ch == "I" and not punct:
            return m.group(0)  # the pronoun
        if ch == "A" and not punct and not after.startswith(("'s", "’s")):
            nxt = re.match(r"\s*([A-Za-z]+)", after)
            initial = re.search(r"(^|[.!?:;]\s+|[\"“(]\s*)$", before) is not None
            if initial and nxt and nxt.group(1)[0].islower() and nxt.group(1).lower() not in _A_LETTER_NEXT:
                return m.group(0)  # "A reward model takes..." is the article
        if ch != "A" and not punct:
            return m.group(0)  # other letters are already read as letter names
        ph = "ˈA" if ch == "A" else (letter_phonemes(ch) if letter_phonemes else None)
        return f"[{ch}{punct}](/{ph}{punct}/)" if ph else m.group(0)

    return _LETTER.sub(repl, text)


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------
def check_voice(voice: str) -> str | None:
    """None if `voice` is an English Kokoro voice, or a comma blend of them ("af_bella,af_heart",
    averaged by Kokoro), else the reason it can't be used."""
    for part in voice.split(","):
        if part in ENGLISH_VOICES:
            continue
        if re.fullmatch(r"[a-z][fm]_[a-z]+", part.lower()) and part[0].lower() not in "ab":
            return (f"{part!r} is not an English voice: only US (a*) and UK (b*) English pronunciation "
                    f"is installed (list: python3 {shlex.quote(__file__)} voices)")
        close = difflib.get_close_matches(part.lower(), ENGLISH_VOICES, n=1)
        hint = f"did you mean {close[0]}? " if close else ""
        return f"unknown voice {part!r}: {hint}(list: python3 {shlex.quote(__file__)} voices)"
    if len({part[0] for part in voice.split(",")}) > 1:
        return f"blend {voice!r} mixes US and UK voices; use one accent (all a* or all b*)"
    return None


class Kokoro:
    """Kokoro-82M at the pinned revision; one model shared by the US and UK pipelines."""

    def __init__(self):
        import warnings

        warnings.filterwarnings("ignore")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # cached files: the bars are noise
        import torch
        from huggingface_hub import snapshot_download
        from kokoro import KModel, KPipeline

        try:
            self._root = Path(snapshot_download(KOKORO_REPO, revision=KOKORO_REVISION,
                                                allow_patterns=["config.json", "kokoro-v1_0.pth"]))
        except Exception as e:  # offline before the first download, or a broken cache
            sys.exit(f"Can't load the Kokoro model ({type(e).__name__}). It downloads once (~330 MB): "
                     f"connect to the internet and run setup:\n  python3 {shlex.quote(__file__)} setup")
        device = "cuda" if torch.cuda.is_available() else "cpu"  # what KPipeline itself would pick
        self._model = KModel(repo_id=KOKORO_REPO, config=str(self._root / "config.json"),
                             model=str(self._root / "kokoro-v1_0.pth")).to(device).eval()
        self._KPipeline = KPipeline
        self._pipes: dict[str, object] = {}
        self._letters: dict[tuple[str, str], str] = {}
        self._voices: dict[str, str] = {}

    def _voice_file(self, voice: str) -> str:
        """Local path(s) of a voice pack at the pinned revision (downloaded once); a blend
        "a,b" becomes "path_a,path_b", which Kokoro averages."""
        from huggingface_hub import hf_hub_download

        for part in voice.split(","):
            if part not in self._voices:
                try:
                    self._voices[part] = hf_hub_download(KOKORO_REPO, f"voices/{part}.pt", revision=KOKORO_REVISION)
                except Exception as e:  # offline (OfflineModeIsEnabled, connection errors) or not cached
                    sys.exit(f"Can't load voice {part!r} ({type(e).__name__}). It downloads once: connect to "
                             f"the internet, or run setup again (it fetches every English voice):\n"
                             f"  python3 {shlex.quote(__file__)} setup")
        return ",".join(self._voices[part] for part in voice.split(","))

    def __call__(self, text: str, voice: str, speed: float, seed: int):
        """Returns (audio, words) where words = [(token text, start_s, end_s), ...]."""
        import numpy as np
        import torch

        lang = voice[0]  # the voice prefix selects the G2P: a = US English, b = UK English
        if lang not in self._pipes:
            self._pipes[lang] = self._KPipeline(lang_code=lang, repo_id=KOKORO_REPO, model=self._model)
        pipe = self._pipes[lang]

        def letter(ch):
            if (lang, ch) not in self._letters:
                self._letters[(lang, ch)] = (pipe.g2p(ch)[0] or "").strip(" .")
            return self._letters[(lang, ch)]

        torch.manual_seed(seed)
        chunks, words, offset = [], [], 0.0
        for result in pipe(kokoro_text(text, letter), voice=self._voice_file(voice), speed=speed):
            audio = np.asarray(result.audio, dtype=np.float32)
            words += [(t.text, offset + t.start_ts, offset + t.end_ts) for t in (result.tokens or [])
                      if t.start_ts is not None and t.end_ts is not None]
            chunks.append(audio)
            offset += len(audio) / SAMPLE_RATE
        return (np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)), words


def finish(audio, trim_db: float = -45.0):
    """Trim edge silence, add 20 ms fades, peak-normalise to -1 dBFS.
    Returns (audio, seconds trimmed from the start) so word timings can be shifted."""
    import numpy as np

    idx = np.where(np.abs(audio) > 10 ** (trim_db / 20))[0]
    lead = 0
    if len(idx):
        pad = int(0.03 * SAMPLE_RATE)
        lead = max(0, idx[0] - pad)
        audio = audio[lead: idx[-1] + pad]
    n = min(len(audio) // 2, int(0.02 * SAMPLE_RATE))
    if n:
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        audio[:n] *= ramp
        audio[-n:] *= ramp[::-1]
    peak = float(np.abs(audio).max()) or 1.0
    return audio * (10 ** (-1 / 20) / peak), lead / SAMPLE_RATE


def sentence_timings(sentences: list[str], words, duration: float) -> list[tuple[float, float]]:
    """Map each sentence to (start, end) seconds by walking the word timestamps and counting words;
    falls back to word-count proportions if the token stream doesn't line up."""
    spoken = [(part, a, b) for w, a, b in words for part in _WORD.findall(w)]  # "fine-tune" -> 2 words
    counts = [len(_WORD.findall(strip_markup(s))) for s in sentences]
    out = []
    if spoken and sum(counts) == len(spoken):
        i = 0
        for c in counts:
            seg = spoken[i:i + c] or spoken[max(i - 1, 0):i]
            out.append((seg[0][1], seg[-1][2]))
            i += c
    else:
        total, acc = max(sum(counts), 1), 0
        for c in counts:
            out.append((duration * acc / total, duration * (acc + c) / total))
            acc += c
    return out


def seed_for(key: str) -> int:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines() if row.strip()]


def synth(lines_path: Path, out: Path) -> int:
    import soundfile as sf

    out.mkdir(parents=True, exist_ok=True)
    lines = _read_lines(lines_path)
    todo = [ln for ln in lines if not ((out / f"{ln['key']}.wav").exists() and (out / f"{ln['key']}.json").exists())]
    print(f"narration: {len(lines)} line(s), {len(todo)} to synthesise, {len(lines) - len(todo)} cached")
    bad = {v for v in (ln.get("voice", DEFAULT_VOICE) for ln in todo) if check_voice(v)}
    if bad:
        print("\n".join(check_voice(v) for v in sorted(bad)), file=sys.stderr)
        return 2
    engine = Kokoro() if todo else None
    t0, total = time.time(), 0.0
    for i, line in enumerate(todo, 1):
        key = line["key"]
        sentences = line.get("sentences") or [line["say"]]
        raw, words = engine(" ".join(sentences), line.get("voice", DEFAULT_VOICE),
                            float(line.get("speed", DEFAULT_SPEED)), seed_for(key))
        audio, lead = finish(raw)
        duration = len(audio) / SAMPLE_RATE
        words = [(w, max(a - lead, 0.0), max(b - lead, 0.0)) for w, a, b in words]
        timing = {"duration": duration,
                  "sentences": [{"start": a, "end": b} for a, b in sentence_timings(sentences, words, duration)],
                  "words": [{"text": w, "start": a, "end": b} for w, a, b in words]}
        tmp_wav, tmp_json = out / f".{key}.tmp.wav", out / f".{key}.tmp.json"
        sf.write(tmp_wav, audio, SAMPLE_RATE, subtype="PCM_16")
        tmp_json.write_text(json.dumps(timing), encoding="utf-8")
        tmp_json.replace(out / f"{key}.json")  # atomic; a clip counts as cached only when both exist
        tmp_wav.replace(out / f"{key}.wav")
        total += duration
        print(f"  [{i}/{len(todo)}] {duration:5.2f}s  {line['say'][:70]}")
    if todo:
        secs = time.time() - t0
        print(f"synthesised {total:.1f}s of speech in {secs:.1f}s ({total / max(secs, 1e-6):.1f}x real time)")
    return 0


# ---------------------------------------------------------------------------
# QA
# ---------------------------------------------------------------------------
_NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
        "7": "seven", "8": "eight", "9": "nine"}
_FILLER = {"the", "a", "an", "uh", "um"}


def _norm_words(s: str) -> list[str]:
    s = re.sub(r"(\d)", r" \1 ", s.lower().replace("’", "'"))
    return [_NUM.get(w, w) for w in re.findall(r"[a-z0-9']+", s) if w not in _FILLER]


def _load_16k(path: Path):
    """16 kHz mono float32 for Whisper (decoded here: faster-whisper's own PyAV decoder breaks
    across PyAV releases). Linear resampling is plenty for speech recognition."""
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        t_new = np.arange(int(len(audio) * 16000 / sr)) * (sr / 16000)
        audio = np.interp(t_new, np.arange(len(audio)), audio).astype(np.float32)
    return audio


def wer(script: str, heard: str) -> float:
    """Word error rate of `heard` against `script` (articles and fillers ignored, digits spelled out)."""
    ref, hyp = _norm_words(strip_markup(script)), _norm_words(heard)
    ops = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False).get_opcodes()
    return sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in ops if op != "equal") / max(len(ref), 1)


def qa(lines_path: Path, audio_dir: Path, max_wer: float = 0.25) -> int:
    """Transcribe every clip with Whisper and flag lines whose word error rate against the script
    exceeds `max_wer` (skipped, repeated or garbled words). Each clip's transcript is cached in
    <key>.qa.json, so only new clips are transcribed (and Whisper loads only if there are any)."""
    lines = _read_lines(lines_path)
    model = None
    bad = 0
    for line in lines:
        wav = audio_dir / f"{line['key']}.wav"
        if not wav.exists():
            continue
        cache = wav.with_suffix(".qa.json")
        try:
            hit = json.loads(cache.read_text(encoding="utf-8"))
            heard = hit["heard"] if hit.get("model") == QA_MODEL and cache.stat().st_mtime >= wav.stat().st_mtime else None
        except (OSError, ValueError, KeyError):
            heard = None
        if heard is None:
            if model is None:
                from faster_whisper import WhisperModel
                model = WhisperModel(QA_MODEL, device="cpu", compute_type="int8")
            segs, _ = model.transcribe(_load_16k(wav), beam_size=1, language="en",
                                       condition_on_previous_text=False, without_timestamps=True)
            heard = " ".join(s.text for s in segs).strip()
            cache.write_text(json.dumps({"model": QA_MODEL, "heard": heard}), encoding="utf-8")
        err = wer(line["say"], heard)
        flag = err > max_wer
        bad += flag
        print(f"  {'FLAG' if flag else 'ok  '} wer={err:4.2f}  {line['say'][:60]!r}")
        if flag:
            stale = " ".join(shlex.quote(str(p)) for p in (wav, wav.with_suffix(".json"), cache))
            print(f"        heard: {heard[:80]!r}\n        fix: rephrase, or `rm {stale}` to resynthesise")
    print(f"QA: {len(lines) - bad}/{len(lines)} line(s) match the script (max WER {max_wer})")
    return 1 if bad else 0


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    sys.stdout.reconfigure(line_buffering=True)  # keep stdout and stderr in order when piped
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="create the TTS venv and download the models (once per machine)")
    sub.add_parser("voices", help="list Kokoro voices")
    s = sub.add_parser("say", help="synthesise one line to a wav (audition a voice or wording)")
    s.add_argument("text")
    s.add_argument("-o", "--out", default="say.wav")
    s.add_argument("--voice", default=DEFAULT_VOICE)
    s.add_argument("--speed", type=float, default=DEFAULT_SPEED, help="speaking rate (1.0 = natural)")
    s = sub.add_parser("check-voice", help="exit 2 with the reason if a voice name can't be used")
    s.add_argument("voice")
    s = sub.add_parser("synth", help="synthesise every missing line of a <video>_lines.jsonl")
    s.add_argument("lines", type=Path)
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("qa", help="transcribe clips with Whisper and diff against the script")
    s.add_argument("lines", type=Path)
    s.add_argument("--audio", type=Path, required=True)
    sub.add_parser("python", help="print the TTS interpreter path; exit 2 if narration isn't set up")
    args = ap.parse_args(argv)

    if args.cmd == "setup":
        return setup()
    if args.cmd == "voices":
        for v, d in KOKORO_VOICES.items():
            print(f"  {v:<11} {d}")
        others = sorted(ENGLISH_VOICES - KOKORO_VOICES.keys())
        print(f"Also available: {', '.join(others)}")
        print("Grades and samples: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md")
        return 0
    if args.cmd == "python":
        py = venv_python()
        if not py.exists():
            print(not_set_up(), file=sys.stderr)
            return 2
        print(py)
        return 0
    if args.cmd == "check-voice":
        why = check_voice(args.voice)
        if why:
            print(why, file=sys.stderr)
        return 2 if why else 0
    if args.cmd == "say" and check_voice(args.voice):
        print(check_voice(args.voice), file=sys.stderr)
        return 2
    ensure_tts_python(argv)
    if args.cmd == "say":
        import soundfile as sf

        text = " ".join(args.text.split())  # renders collapse whitespace too
        if re.search(r"[^\x00-\x7f]|[*^|/<>=+_]", text):
            print("note: a render first spells out symbols (tbb.speakable), so this line will be spoken "
                  "differently there; audition the spoken form instead", file=sys.stderr)
        seed = seed_for(narration_key(text, args.voice, args.speed))  # same seed as a render
        audio, _ = finish(Kokoro()(text, args.voice, args.speed, seed)[0])
        sf.write(args.out, audio, SAMPLE_RATE, subtype="PCM_16")
        print(f"wrote {args.out} ({len(audio) / SAMPLE_RATE:.2f}s)")
        return 0
    if args.cmd == "synth":
        return synth(args.lines, args.out)
    return qa(args.lines, args.audio)


if __name__ == "__main__":
    sys.exit(main())
