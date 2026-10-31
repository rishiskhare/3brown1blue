#!/usr/bin/env python3
"""Lint a narration script against Grant Sanderson's measured style (references/narration-style.md).

    python3 style_lint.py media/voice/video_lines.jsonl   # what render.py --voice collected
    python3 style_lint.py final/video_narration.txt        # or any plain-text script

Reports the script's numbers next to the 3b1b corpus targets and flags anti-patterns
(agenda openers, hype words, over-signposting, caption-speak, exclamation marks). It is advisory:
exit 0 whatever it finds (fix the warnings or have a reason); 2 for a missing file or bad usage.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORD = re.compile(r"[A-Za-z0-9']+")
# Same splitter as tbb.split_sentences (this script must run without manim; a test keeps them equal).
_SENTENCE_END = re.compile(r"[.!?…]+[\"”’)\]]*(?=\s+[\"“(\[A-Z0-9])")
_ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "prof", "st", "vs", "e.g", "i.e", "cf", "fig", "eq", "approx"}

AGENDA_OPENER = re.compile(r"^\s*(in this video|today,? we|welcome|hi everyone|hey everyone|let's (dive|explore|get started)|"
                           r"we('re| are) going to (explore|look at|learn|dive))", re.I)
NEVER = {  # phrases that occur ~0 times in 52k words of 3b1b narration
    "delve": "hype word", "unlock": "hype word", "harness": "hype word",
    "game-changer": "hype word", "game changer": "hype word", "mind-blowing": "hype word",
    "mind blowing": "hype word", "tapestry": "hype word", "embark": "hype word",
    "seamless": "hype word", "here's the thing": "over-signposting",
    "let's break it down": "over-signposting", "let's break this down": "over-signposting",
    "it's important to note": "over-signposting", "it is important to note": "over-signposting",
    "simply put": "over-signposting", "in conclusion": "essay register", "in summary": "essay register",
    "furthermore": "essay register", "additionally": "essay register",
    "pause and ponder": "3b1b catchphrase: use the behaviour, not the trademark wording",
    "subscribe": "channel furniture", "patreon": "channel furniture", "grant here": "channel furniture",
    "deep dive": "hype phrase",
}
# Grant does use these, but about once per video at most (counts per ~3000 words).
RATIONED = {"fascinating": 1, "crucial": 1, "in other words": 1, "essentially": 2, "amazing": 0,
            "journey": 1, "dive in": 1, "moreover": 1, "incredible": 1, "realm": 1}
CAPTION_FRAGMENT = re.compile(r"^[^.?!:]{1,28}:\s+[^.?!]{1,40}[.]$")


MARKUP = re.compile(r"\[([^\]]+)\]\((/[^)]*/)\)")  # phoneme overrides: lint the word, not the IPA


def phrase_pattern(phrase: str) -> str:
    """Regex for a listed phrase. Single words also match their inflections (delve, delves,
    delved, delving); multi-word phrases match as written."""
    if " " in phrase or "-" in phrase or "'" in phrase:
        return rf"\b{re.escape(phrase)}\b"
    if phrase.endswith("e"):  # delve -> delve, delves, delved, delving
        return rf"\b{re.escape(phrase[:-1])}(?:e|es|ed|ing)\b"
    return rf"\b{re.escape(phrase)}(?:s|es|ed|ing)?\b"  # unlock(s/ed/ing), harness(es)


def split_sentences(paragraph: str) -> list[str]:
    s = re.sub(r"\s+", " ", paragraph).strip()
    out, start = [], 0
    for m in _SENTENCE_END.finditer(s):
        word = s[start:m.start()].rsplit(" ", 1)[-1].lstrip("\"“([").lower()
        if s[m.start()] == "." and word in _ABBREVIATIONS:
            continue
        out.append(s[start:m.end()].strip())
        start = m.end()
    tail = s[start:].strip()
    return [x for x in [*out, tail] if x]


def load(path: Path) -> list[str]:
    rows = [r for r in path.read_text(encoding="utf-8").splitlines() if r.strip()]
    if path.suffix == ".jsonl":
        lines = [json.loads(r)["say"] for r in rows]
    else:
        lines = [re.sub(r"^\[\w+\] ", "", r) for r in rows]  # _narration.txt: "[Scene] text"
    return [MARKUP.sub(r"\1", line) for line in lines]


def lint(lines: list[str]) -> list[str]:
    lines = [line.replace("’", "'").replace("‘", "'") for line in lines]  # curly apostrophes: "let’s"
    text = " ".join(lines)
    sentences = [s for line in lines for s in split_sentences(line)]
    words = WORD.findall(text)
    n = max(len(words), 1)

    def per_k(count: int) -> float:
        return count / n * 1000

    lengths = [len(WORD.findall(s)) for s in sentences] or [0]
    mean_len = sum(lengths) / len(lengths)
    short = sum(1 for k in lengths if k <= 5) / len(lengths)
    questions = sum(1 for s in sentences if s.endswith("?")) / max(len(sentences), 1)
    exclaim = text.count("!")
    low = text.lower()
    you = len(re.findall(r"\byou\b|\byour\b", low))
    we = len(re.findall(r"\bwe\b|\bus\b|\bour\b|\blet's\b", low))
    and_start = sum(1 for s in sentences if re.match(r"(And|So|But|Now)\b", s)) / max(len(sentences), 1)

    print(f"narration style check: {len(words)} words, {len(sentences)} sentences")
    rows = [
        ("mean sentence length (words)", f"{mean_len:.1f}", "~23-25", 15 <= mean_len <= 33),
        ("sentences <= 5 words", f"{short:.0%}", "~3%", short <= 0.10),
        ("questions", f"{questions:.0%}", "~5% (puzzle videos ~18%)", questions <= 0.15),
        ("'you/your' per 1k words", f"{per_k(you):.1f}", "~21", per_k(you) >= 10),
        ("'we/us/let's' per 1k words", f"{per_k(we):.1f}", "~12", True),
        ("starts with And/So/But/Now", f"{and_start:.0%}", "~22%", and_start >= 0.08 or len(sentences) < 12),
        ("exclamation marks", f"{exclaim}", "~0", exclaim <= max(2, len(words) // 3000)),
    ]
    for name, got, target, ok in rows:
        print(f"  {'ok  ' if ok else 'WARN'} {name:<30} {got:>7}   3b1b: {target}")

    warnings = []
    if lines and AGENDA_OPENER.search(lines[0]):
        warnings.append(f"agenda opener: {lines[0][:70]!r} -> open on the object or the puzzle instead")
    for phrase, why in NEVER.items():
        for s in sentences:
            if re.search(phrase_pattern(phrase), s, re.I):
                warnings.append(f"{why}: {phrase!r} in {s[:70]!r}")
    for phrase, limit in RATIONED.items():
        c = len(re.findall(phrase_pattern(phrase), low))
        allowed = limit * max(1, len(words) // 3000)
        if c > allowed:
            warnings.append(f"{phrase!r} used {c}x (3b1b: rare; allow ~{allowed} here)")
    frags = [s for s in sentences if CAPTION_FRAGMENT.match(s)]
    if frags:
        warnings.append(f"{len(frags)} caption-style fragment(s), e.g. {frags[0]!r} -> write the full spoken sentence")
    if not rows[0][3] and mean_len < 15:
        warnings.append("sentences are short and choppy: chain related clauses with commas and 'and', as Grant does")
    for w in warnings:
        print(f"  WARN {w}")
    if not warnings and all(r[3] for r in rows):
        print("  script matches the 3b1b narration profile")
    return warnings


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"style_lint: {path} is not a file", file=sys.stderr)
        return 2
    try:
        lines = load(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"style_lint: can't read {path}: {type(e).__name__}: {e} "
              "(expected render.py's *_lines.jsonl or a plain-text script)", file=sys.stderr)
        return 2
    lint(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
