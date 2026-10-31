#!/usr/bin/env python3
"""Self-test: execute every recipe in references/idioms.md, the bundled example and the template.

    python tests/selftest.py [--python .venv/bin/python] [-j 4] [--render] [--keep]

A development check for the skill itself (not shipped with it). Each ```python block that
defines a Scene subclass is written into a scratch module next to a copy of tbb.py and run with
`manim --dry_run` (full construct, no video), or rendered at 480p15 with --render. Reports
failures and tbb layout warnings; exit 1 on any failure. The scratch folder is deleted when
everything passes (unless --keep); a failed or interrupted run keeps it and prints its path.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import re
import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "3brown1blue"
sys.path.insert(0, str(SKILL / "scripts"))
from render import install_signal_handlers, interrupted, manim_cmd, run_child, tbb_warnings  # noqa: E402

HEADER = "from manim import *\nfrom tbb import *\n\n"
RECIPE_TIMEOUT = 900  # seconds per scene; recipes are small


def blocks(md: Path) -> list[tuple[str, str]]:
    out = []
    for code in re.findall(r"```python\n(.*?)```", md.read_text(encoding="utf-8"), flags=re.S):
        for name in re.findall(r"^class (\w+)\(", code, flags=re.M):
            out.append((name, code))
    return out


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    install_signal_handlers()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", default=sys.executable, help="interpreter whose manim to use")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--render", action="store_true", help="render 480p15 instead of --dry_run")
    ap.add_argument("--keep", action="store_true", help="keep the scratch folder even when all pass")
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error("-j must be at least 1")
    manim = manim_cmd(args.python)

    work = Path(tempfile.mkdtemp(prefix="tbb-selftest-"))
    shutil.copy(SKILL / "templates" / "tbb.py", work)
    jobs = []
    seen = {}
    for name, code in blocks(SKILL / "references" / "idioms.md"):
        if code not in seen:
            seen[code] = work / f"idiom_{len(seen):02d}.py"
            seen[code].write_text(HEADER + code, encoding="utf-8")
        jobs.append((seen[code], name))
    example = SKILL / "examples" / "derivative_of_x_squared.py"
    shutil.copy(example, work)
    for name in re.findall(r"^class (\w+)\(", example.read_text(encoding="utf-8"), flags=re.M):
        jobs.append((work / example.name, name))
    template = SKILL / "templates" / "scene_template.py"
    if template.exists():
        shutil.copy(template, work)
        for name in re.findall(r"^class (\w+)\(", template.read_text(encoding="utf-8"), flags=re.M):
            jobs.append((work / template.name, name))

    def run(job):
        path, scene = job
        flag = ["-ql"] if args.render else ["-ql", "--dry_run"]
        media = work / "media" / f"{path.stem}_{scene}"  # isolated: no shared-TeX-cache races
        code, out = run_child([*manim, "render", *flag, "--media_dir", str(media), path.name, scene],
                              RECIPE_TIMEOUT, cwd=work)
        err = "" if code == 0 else "\n".join(out.strip().splitlines()[-12:])
        return scene, code, tbb_warnings(out), err

    failures = 0
    pool = cf.ThreadPoolExecutor(max_workers=args.jobs)
    try:
        for scene, code, warns, err in pool.map(run, jobs):
            print(f"{'ok  ' if code == 0 else 'FAIL'} {scene}")
            for w in warns:
                print(f"     layout: {w}")
            if code:
                failures += 1
                print("     " + err.replace("\n", "\n     "))
    except KeyboardInterrupt:
        code = interrupted(f"work dir kept: {work}")
        pool.shutdown(wait=True, cancel_futures=True)
        return code
    pool.shutdown()
    keep = failures or args.keep
    print(f"\n{len(jobs) - failures}/{len(jobs)} scenes passed" + (f"  (work dir: {work})" if keep else ""))
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
