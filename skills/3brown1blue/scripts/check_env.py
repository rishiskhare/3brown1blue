#!/usr/bin/env python3
"""Check that everything needed to render 3b1b-style Manim Community videos is installed.

    python3 check_env.py                        # check the manim of this interpreter
    python3 check_env.py --python .venv/bin/python   # check the manim of a venv

Required: manim >= 0.22.1, ffmpeg + ffprobe, latex + dvisvgm, and the LaTeX packages of the tbb
template. Optional: CMU Serif, narration (uv + the Kokoro venv). Exit code 1 if anything required
is missing.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MIN_MANIM = (0, 22, 1)  # 0.22.0 can't draw images with Pillow >= 13
# One apt line for everything (same as the README), so a Debian/Ubuntu fix is a single command.
APT_ALL = ("sudo apt install libcairo2-dev libpango1.0-dev pkg-config python3-dev ffmpeg texlive-latex-extra "
           "texlive-fonts-extra texlive-science tipa dvisvgm fonts-cmu")
LATEX_PACKAGES = [  # CE's TexTemplateLibrary.threeb1b preamble + pifont (what tbb.py loads)
    "standalone.cls", "preview.sty", "babel.sty", "inputenc.sty", "fontenc.sty", "lmodern.sty",
    "amsmath.sty", "amssymb.sty", "dsfont.sty", "setspace.sty", "tipa.sty", "relsize.sty",
    "textcomp.sty", "mathrsfs.sty", "calligra.sty", "wasysym.sty", "ragged2e.sty", "physics.sty",
    "xcolor.sty", "microtype.sty", "pifont.sty",
]
# Runs in the target interpreter: manim's version and whether CMU Serif is installed.
PROBE = r"""
import json
out = {}
try:
    import manim, manimpango
    out["version"] = manim.__version__
    out["cmu"] = "CMU Serif" in manimpango.list_fonts()
except Exception as e:  # ImportError, or a native library (cairo, pango) failing to load
    out["error"] = f"{type(e).__name__}: {e}"[:300]
print("TBBPROBE" + json.dumps(out))
"""


def _run(cmd: list[str], timeout: float = 30) -> str:
    """stdout of a command that succeeded, else ""."""
    out, _, ok = _run_full(cmd, timeout)
    return out if ok else ""


def _run_full(cmd: list[str], timeout: float = 30) -> tuple[str, str, bool]:
    """(stdout, stderr, exited 0) of a command, or ("", reason, False) if it couldn't run."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, stdin=subprocess.DEVNULL)
        return proc.stdout.strip(), proc.stderr.strip(), proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", str(e), False


def parse_version(v: str) -> tuple[int, int, int]:
    """'0.22.0' -> (0, 22, 0); pre-releases and local tags ('0.22.0rc1', '0.23.dev4') keep their numbers."""
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", v)
    return (int(m[1]), int(m[2]), int(m[3] or 0)) if m else (0, 0, 0)


def check(python: str) -> list[dict]:
    results = []

    def add(name, ok, detail, required=True, fix=""):
        results.append({"name": name, "ok": bool(ok), "detail": detail, "required": required, "fix": fix})

    raw, err, _ = _run_full([python, "-c", PROBE], timeout=180)
    if "TBBPROBE" in raw:
        probe = json.loads(raw.split("TBBPROBE", 1)[1])
    else:
        tail = " | ".join(err.splitlines()[-3:])
        probe = {"error": "probe failed to run" + (f": {tail}" if tail else "")}
    if "version" in probe:
        add("manim", parse_version(probe["version"]) >= MIN_MANIM, f"Manim Community v{probe['version']} ({python})",
            fix='uv pip install -U "manim>=0.22.1"')
    else:
        add("manim", False, f"not importable from {python}: {probe.get('error', '')}",
            fix="uv venv && uv pip install 'manim>=0.22.1'   (first, macOS: brew install cairo pango pkg-config "
                f"ffmpeg + MacTeX; Debian/Ubuntu: {APT_ALL})")

    for tool, why in (("ffmpeg", "joins, grades and mixes clips"), ("ffprobe", "measures clips")):
        path = shutil.which(tool)
        add(tool, path, path or f"not on PATH ({why})", fix=f"macOS: brew install ffmpeg | Debian/Ubuntu: {APT_ALL}")
    for tool in ("latex", "dvisvgm"):
        path = shutil.which(tool)
        add(tool, path, path or "not on PATH",
            fix=f"macOS: install MacTeX | Debian/Ubuntu: {APT_ALL}")

    kpse = shutil.which("kpsewhich")
    for pkg in LATEX_PACKAGES:
        found = _run([kpse, pkg]) if kpse else ""
        add(f"latex:{pkg}", found, found or "missing",
            fix=f"tlmgr install {pkg.rsplit('.', 1)[0]}  (Debian/Ubuntu: {APT_ALL})")

    lm = _run([kpse, "lmroman10-regular.otf"]) if kpse else ""
    add("font:CMU Serif", probe.get("cmu"),
        "installed" if probe.get("cmu") else
        ("missing - tbb uses TeX Live's Latin Modern Roman instead (same face)" if lm else
         "missing - tbb.text() falls back to LaTeX text (same face, slower)"),
        required=False, fix="macOS: brew install --cask font-computer-modern | Debian/Ubuntu: apt install fonts-cmu")

    narrate = Path(__file__).with_name("narrate.py")
    tts = _run([sys.executable, str(narrate), "python"])
    uv = shutil.which("uv")
    add("narration (optional)", bool(tts),
        f"Kokoro ready ({tts})" if tts else "not set up - only needed for render.py --voice"
        + ("" if uv else "; also needs uv"), required=False,
        fix=("" if uv else "curl -LsSf https://astral.sh/uv/install.sh | sh && ") + f"python3 {narrate} setup")
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", default=sys.executable, help="interpreter whose manim to check")
    args = ap.parse_args()
    results = check(args.python)
    for r in results:
        mark = "OK  " if r["ok"] else ("FAIL" if r["required"] else "WARN")
        print(f"[{mark}] {r['name']:<22} {r['detail']}" + (f"\n         fix: {r['fix']}" if not r["ok"] and r["fix"] else ""))
    return 0 if all(r["ok"] for r in results if r["required"]) else 1


if __name__ == "__main__":
    sys.exit(main())
