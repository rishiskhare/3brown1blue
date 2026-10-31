#!/usr/bin/env python3
"""Render a multi-scene Manim Community file into one 3b1b-style video (silent, or narrated).

Scene order: a module-level ``SCENES = ["Intro", "Main", ...]`` list if present, otherwise every
scene class in source order: derived from a Scene class (``TbbScene``, ``ThreeDScene``...) or a tbb
card (``class Opening(TitleCard)``), with a ``construct`` of its own or inherited. Names starting
with ``_`` are skipped.

Examples:
    render.py video.py --check               # seconds: every LaTeX/Python error + layout warnings + stills
    render.py video.py --sheet               # draft: 480p15 + contact sheets -> final/video_480p15.mp4
    render.py video.py -q h --fps 30         # 1080p30 final (Grant renders at 30 fps)
    render.py video.py -q h --fps 30 --voice # narrate voiceover()/caption() lines locally (Kokoro)
    render.py video.py A B -q h --voice --no-concat    # long videos: render in batches...
    render.py video.py -q h --voice --concat-only      # ...then join them without re-rendering
    render.py video.py -- -n 3,5             # anything after `--` goes to manim verbatim

Re-renders are incremental: a scene whose code, the classes and local modules it uses, the
project's other files and the settings are unchanged reuses its clip (--force renders everything).
Each clip is graded (ffmpeg `eq=saturation=1.5`, the grade in Grant's config) as soon as it
renders, and the final cut joins the graded clips without re-encoding. Clips go to <media-dir>/
(default ./media), the cut to ./final/. Audio is stripped unless --voice, which adds a
loudness-normalised narration track and a sidecar .srt.
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ENV = dict(os.environ, COLUMNS="400")  # widen manim's log lines (rich still wraps tracebacks at ~100)
QUALITY = {"l": "480p15", "m": "720p30", "h": "1080p60", "p": "1440p60", "k": "2160p60"}
SCENE_TIMEOUT = 3600   # seconds; a hung scene is reported as failed instead of blocking forever
FFMPEG_TIMEOUT = 3600  # seconds for one ffmpeg/ffprobe call (a 4K join of a long video is minutes)
# tbb's cards define construct(), so `class Opening(TitleCard): ...` is a scene without one.
TBB_CARD_SCENES = {"TitleCard", "ChapterCard", "QuestionCard", "QuoteCard", "EndScreen"}
RENDER_REVISION = 2    # bump when a change here alters clips: every scene's fingerprint then misses
# Manim's own clips are intermediates (each is graded and re-encoded once), so encode them fast at
# near-lossless quality; the grade below is the real encode. veryfast vs medium: SSIM 0.9998.
INTERMEDIATE = ["--encoder-option", "preset=ultrafast", "--encoder-option", "crf=14"]
FINISH = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"]


# ---------------------------------------------------------------------------
# Helpers shared with selftest.py
# ---------------------------------------------------------------------------
def helper(name: str) -> Path:
    """Locate a sibling skill script (narrate.py, style_lint.py), even if this file was copied
    out of the skill into a project folder."""
    candidates = [Path(__file__).resolve().parent / name]
    if os.environ.get("TBB_SKILL_DIR"):
        candidates.append(Path(os.environ["TBB_SKILL_DIR"]) / "scripts" / name)
    # `npx skills add` installs into the project by default (-g: the home folder).
    for base in (Path.cwd(), Path.home()):
        for agent_dir in (".claude", ".agents"):
            candidates.append(base / agent_dir / "skills" / "3brown1blue" / "scripts" / name)
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit(f"cannot find {name}: run render.py from the skill's scripts/ folder, or set TBB_SKILL_DIR")


def manim_cmd(python: str) -> list[str]:
    """The manim CLI that belongs to `python` (a venv's manim beats one on PATH)."""
    venv_manim = Path(python).absolute().with_name("manim.exe" if os.name == "nt" else "manim")
    if venv_manim.exists():
        return [str(venv_manim)]
    return [python, "-m", "manim"]


def tbb_warnings(output: str) -> list[str]:
    """tbb layout-audit and voice warnings from manim's log (rich may wrap them over lines)."""
    flat = re.sub(r"\s+", " ", re.sub(r"\s\S+\.py:\d+\s", " ", output))
    warns = re.findall(r"tbb layout: (.*?\))", flat)
    warns += ["voice: " + w for w in re.findall(r"tbb voice: (.*?estimating)", flat)]
    return list(dict.fromkeys(warns))


def _base_names(n: ast.ClassDef) -> set[str]:
    return {b.id if isinstance(b, ast.Name) else getattr(b, "attr", "") for b in n.bases}


def _scene_classes(tree: ast.Module) -> set[str]:
    """Scene classes of the file: derived from a manim/tbb Scene class (any base named ...Scene),
    a tbb card or an earlier scene class here, and with a construct(): their own, inherited from
    an earlier class here, or a card's. A helper class with a construct(self, scene) is not one."""
    scene_like, has_construct = set(TBB_CARD_SCENES), set(TBB_CARD_SCENES)
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            bases = _base_names(n)
            if bases & scene_like or any(b.endswith("Scene") for b in bases):
                scene_like.add(n.name)
            if any(isinstance(b, ast.FunctionDef) and b.name == "construct" for b in n.body) or bases & has_construct:
                has_construct.add(n.name)
    return (scene_like & has_construct) - TBB_CARD_SCENES


def _parse(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        raise SystemExit(f"{path}:{e.lineno}: {e.msg} (fix the scene file, then re-run)") from None


def _is_scenes_list(node: ast.stmt) -> bool:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
    return any(getattr(t, "id", None) == "SCENES" for t in targets) and getattr(node, "value", None) is not None


def _scenes_list(path: Path, tree: ast.Module) -> list[str] | None:
    for node in tree.body:
        if _is_scenes_list(node):
            try:
                return [str(s) for s in ast.literal_eval(node.value)]
            except (ValueError, TypeError, SyntaxError):
                raise SystemExit(f"{path}: SCENES must be a literal list of class names") from None
    return None


def discover_scenes(path: Path) -> list[str]:
    """SCENES if the module defines it, else every public scene class (see _scene_classes), in
    source order."""
    tree = _parse(path)
    listed = _scenes_list(path, tree)
    if listed is not None:
        return listed
    scenes = _scene_classes(tree)
    return [n.name for n in tree.body if isinstance(n, ast.ClassDef) and n.name in scenes and not n.name.startswith("_")]


# ---------------------------------------------------------------------------
# Incremental renders: a scene's fingerprint covers everything its clip depends on
# ---------------------------------------------------------------------------
def source_fingerprint(path: Path, scene: str, exclude: tuple[Path, ...] = ()) -> str:
    """Hash of everything this scene's clip can depend on, so an unchanged hash means the old clip
    is still right:
    - the module code it can reach: all module-level code and helper classes, its own class and
      every class it references (bases, or `OtherScene.helper(self)`), transitively; other scenes'
      classes and the SCENES list don't count, nor do comments and formatting;
    - the local modules the file imports (the kit, helpers), transitively, by content;
    - every other file in the project folder tree (images, data, manim.cfg...) by size and mtime,
      except render outputs (`exclude`, media/, final/) and caches;
    - the manim.cfg files manim reads from the working directory and the user's config folder."""
    tree = _parse(path)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    scenes = _scene_classes(tree) | set(_scenes_list(path, tree) or [])

    def names(node: ast.AST) -> set[str]:
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}

    todo = [scene] + [c for c in classes if c not in scenes]
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) and not _is_scenes_list(node):
            todo += names(node)
    included: set[str] = set()
    while todo:
        name = todo.pop()
        if name in classes and name not in included:
            included.add(name)
            todo += names(classes[name])
    h = hashlib.sha256()
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name not in included) and not _is_scenes_list(node):
            h.update(ast.dump(node).encode() + b"\0")
    h.update(_project_hash(path, tuple(sorted(str(p.resolve()) for p in exclude))).encode())
    return h.hexdigest()


def _local_modules(path: Path) -> list[Path]:
    """Python files of the project that `path` imports, directly or through each other."""
    root, seen, todo = path.parent.resolve(), set(), [path.resolve()]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = (f.parent if node.level else root)
                for _ in range(max(node.level - 1, 0)):
                    base = base.parent
                prefix = node.module or ""
                mods += [(base, prefix)] + [(base, f"{prefix}.{a.name}".strip(".")) for a in node.names]
        for m in mods:
            base, dotted = (root, m) if isinstance(m, str) else m
            rel = Path(*dotted.split(".")) if dotted else Path()
            for cand in (base / rel.with_suffix(".py") if dotted else None, base / rel / "__init__.py"):
                if cand is not None and cand.is_file():
                    todo.append(cand.resolve())
    seen.discard(path.resolve())
    return sorted(seen)


_PROJECT_HASH: dict[tuple, str] = {}
_PRUNE_DIRS = {"__pycache__", "node_modules", "final"}
_SKIP_FILES = {".DS_Store", "say.wav"}  # say.wav: narrate.py say's default output


def _project_hash(path: Path, exclude: tuple[str, ...]) -> str:
    """Local imports by content; every other project file by size and mtime (computed once per run)."""
    key = (str(path.resolve()), exclude)
    if key in _PROJECT_HASH:
        return _PROJECT_HASH[key]
    h = hashlib.sha256()
    for mod in _local_modules(path):
        h.update(f"{mod}|".encode() + mod.read_bytes() + b"\0")
    root, skip = path.parent.resolve(), set(exclude)
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in _PRUNE_DIRS
                         and str(Path(d, x).resolve()) not in skip and not Path(d, x, "pyvenv.cfg").exists())
        for name in sorted(files):
            f = Path(d, name)
            if name.endswith((".py", ".pyc")) or name in _SKIP_FILES or name.startswith(".") or str(f.resolve()) in skip:
                continue
            st = f.stat()
            h.update(f"{f.relative_to(root)}|{st.st_size}|{st.st_mtime_ns}\0".encode())
    user_cfg = (Path(os.environ.get("APPDATA", "")) / "Manim" if os.name == "nt" else Path.home() / ".config" / "manim")
    for cfg in (Path.cwd() / "manim.cfg", user_cfg / "manim.cfg"):  # manim reads both, wherever the file is
        if cfg.is_file():
            h.update(b"cfg|" + cfg.read_bytes() + b"\0")
    _PROJECT_HASH[key] = h.hexdigest()
    return _PROJECT_HASH[key]


_MANIM_VERSION: dict[str, str] = {}


def manim_version(python: str) -> str:
    """The manim version installed for `python` (cheap: reads package metadata, imports nothing)."""
    if python not in _MANIM_VERSION:
        code, out = run_child([python, "-c", "import importlib.metadata as m; print(m.version('manim'))"], 60)
        _MANIM_VERSION[python] = out.strip() if code == 0 else "?"
    return _MANIM_VERSION[python]


def file_id(p: Path) -> list | None:
    try:
        st = p.stat()
        return [st.st_size, st.st_mtime_ns]
    except OSError:
        return None


def scene_fingerprint(args, scene: str, mode: str, extra: list[str]) -> str:
    env = {k: v for k, v in ENV.items() if k.startswith("TBB_") and k != "TBB_CHECK_FILE"}
    python = str(Path(shutil.which(args.python) or args.python).resolve())
    if mode == "collect":  # the narration text depends on neither the quality nor drawn captions
        env.pop("TBB_CAPTIONS", None)
        parts = [RENDER_REVISION, mode, python, manim_version(args.python), extra, sorted(env.items())]
    else:
        parts = [RENDER_REVISION, mode, args.quality, args.fps, python, manim_version(args.python), extra,
                 sorted(env.items())]
    parts.append(source_fingerprint(args.file, scene, getattr(args, "outputs", ())))
    if mode == "clip" and env.get("TBB_AUDIO") == "on":  # a voiced clip also depends on its audio
        lines = Path(env.get("TBB_LINES_DIR", "")) / f"{scene}.jsonl"
        keys = [json.loads(r)["key"] for r in lines.read_text(encoding="utf-8").splitlines() if r.strip()] \
            if lines.exists() else []
        audio = Path(env.get("TBB_VOICE_DIR", "media/voice")) / "audio"
        parts.append([(k, file_id(audio / f"{k}.wav")) for k in keys])
    return hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()


def state_path(args, scene: str, tag: str) -> Path:
    return args.media_dir / "tbb_state" / args.file.stem / f"{scene}.{tag}.json"


def load_state(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def scene_config(media_dir: Path, module: str, scene: str) -> tuple[Path, Path]:
    """A tiny manim config giving this scene its own TeX cache; returns (config, tex_dir).
    Parallel manim processes that compile the same formula into one shared cache collide;
    per-scene caches never do, and each still persists across re-renders. (Not under media/Tex:
    manim's cleanup unlinks every non-.svg entry of its tex_dir, and a subdirectory there crashes
    plain `manim` runs.) Encoding overlaps with drawing (max_inflight_encoders, ManimCE 0.21+)."""
    cfg = media_dir / "tbb_cfg" / module / f"{scene}.cfg"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    tex_dir = (media_dir / "tex_cache" / module / scene).resolve()
    cfg.write_text(f"[CLI]\ntex_dir = {str(tex_dir).replace('%', '%%')}\nmax_inflight_encoders = 4\n",
                   encoding="utf-8")  # configparser escapes % as %%
    return cfg, tex_dir


def latex_error_summary(out: str, tex_dir: Path, since: float) -> str:
    """For a LaTeX failure: the TeX error lines and the formula that caused them, read from the
    newest log in this scene's TeX cache (manim's traceback wraps the log path unpredictably)."""
    if not re.search(r"latex error converting|LaTeX compilation error", out, re.I):
        return ""
    logs = [p for p in tex_dir.glob("*.log") if p.stat().st_mtime >= since - 1]
    if not logs:
        return ""
    log = max(logs, key=lambda p: p.stat().st_mtime)
    lines: list[str] = []
    log_lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(log_lines):
        if line.startswith("!") or "invalid in math mode" in line:
            lines.append(line.strip())
            if line.startswith("!") and i + 1 < len(log_lines):
                lines.append("    " + log_lines[i + 1].strip())
        if len(lines) >= 8:
            break
    tex = log.with_suffix(".tex")
    if tex.exists():
        body = re.search(r"\\begin\{document\}(.*)\\end\{document\}", tex.read_text(encoding="utf-8", errors="replace"), re.S)
        if body:
            formula = re.sub(r"\\special\{dvisvgm:raw[^}]*\}", " | ", body.group(1)).strip()
            lines.append("formula (| marks piece boundaries): " + re.sub(r"\s+", " ", formula)[:400])
    return "LaTeX failed:\n" + "\n".join(lines) if lines else ""


def user_frame(out: str, file: Path) -> str:
    """'at video.py:17 in construct: <source line>' for the deepest traceback frame in the user's
    own scene file (module level included), or "".

    Rich draws tracebacks in boxes and wraps long paths, even mid-number, so every space and box
    character is removed and the file's full path is matched, never just its name (a user file
    "ops.py" must not match manim's "module_ops.py"). Plain Python tracebacks are handled too."""
    paths = {str(file.absolute()), str(file.resolve())}
    hits = []
    for p in paths:  # plain traceback: File "/abs/video.py", line 17, in construct
        hits += re.findall(rf'File "{re.escape(p)}", line (\d+), in (\S+)', out)
    if not hits:
        flat = re.sub(r"[\s│╭╮╰╯─❱]", "", out)
        alt = "|".join(re.escape(re.sub(r"\s", "", p)) for p in paths)
        # Rich: "/abs/video.py:17 in construct" followed by numbered source lines.
        hits = re.findall(rf"(?:{alt}):(\d+)in(<module>|[A-Za-z_]\w*?)(?=\d|$)", flat)
    if not hits:
        return ""
    line, fn = int(hits[-1][0]), hits[-1][1]
    src = file.read_text(encoding="utf-8", errors="replace").splitlines()
    code = src[line - 1].strip() if 0 < line <= len(src) else ""
    return f"at {file.name}:{line} in {fn}: {code}"


# Every running manim/ffmpeg/ffprobe child, so Ctrl-C or SIGTERM can stop them all. _STOPPING is
# set, and children are registered, under the same lock: no child can start after stop_children().
_CHILDREN: set[subprocess.Popen] = set()
_CHILDREN_LOCK = threading.Lock()
_STOPPING = threading.Event()
KILL_GRACE = 5.0  # seconds a child gets to exit after SIGTERM before it is killed


def run_child(cmd: list[str], timeout: float, env=None, cwd=None, started: list | None = None) -> tuple[int, str]:
    """Run a command, capturing combined output; returns (exit code, output). 124 = timed out,
    130 = cancelled because render.py is stopping. An interrupt while waiting stops the child.
    `started`, if given, receives the process (so another thread can stop it)."""
    with _CHILDREN_LOCK:
        if _STOPPING.is_set():
            return 130, "cancelled"
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace", env=env, cwd=cwd,
                                start_new_session=os.name == "posix")  # own group: LaTeX/ffmpeg go too
        _CHILDREN.add(proc)
    if started is not None:
        started.append(proc)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return (130 if _STOPPING.is_set() else proc.returncode), out
    except subprocess.TimeoutExpired:
        _terminate_all([proc])
        return 124, _drain(proc) + f"\ntimed out after {timeout:g}s"
    except BaseException:  # Ctrl-C/SIGTERM while this thread waited (ffmpeg)
        _terminate_all([proc])
        raise
    finally:
        with _CHILDREN_LOCK:
            _CHILDREN.discard(proc)


def _drain(proc: subprocess.Popen) -> str:
    """Remaining output of a stopped child. Bounded: on Windows a surviving grandchild can hold
    the pipe open forever."""
    try:
        return proc.communicate(timeout=KILL_GRACE)[0] or ""
    except subprocess.TimeoutExpired:
        return ""


def _signal_tree(proc: subprocess.Popen, kill: bool) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL if kill else signal.SIGTERM)
        else:  # no process groups: taskkill /T takes the LaTeX/ffmpeg grandchildren as well
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _terminate_all(procs: list[subprocess.Popen]) -> None:
    """SIGTERM every process tree at once, give them KILL_GRACE in total, then kill survivors."""
    for p in procs:
        _signal_tree(p, kill=False)
    deadline = time.monotonic() + KILL_GRACE
    for p in procs:
        try:
            p.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            _signal_tree(p, kill=True)


def stop_children() -> None:
    with _CHILDREN_LOCK:
        _STOPPING.set()
        procs = list(_CHILDREN)
    _terminate_all(procs)



@dataclass
class SceneResult:
    scene: str
    code: int
    seconds: float
    detail: str              # warnings on success; the error on failure
    reused: bool = False     # unchanged since the last render: its clip was reused
    sheet_new: bool = False  # a contact sheet was (re)written this run


def clips_dir(args) -> Path:
    """Where manim writes this run's clips. Voiced clips get their own folder, so switching
    between silent and --voice renders reuses both sets instead of overwriting one."""
    return args.media_dir / "tbb_voiced" if args.voice else args.media_dir


def graded_path(args, scene: str) -> Path:
    qdir = quality_dir(args.quality, args.fps) + ("-voice" if args.voice else "")
    return args.media_dir / "tbb_graded" / args.file.stem / qdir / f"{scene}_s{args.saturation:g}.mp4"


def _partial(out: Path) -> Path:
    return out.with_name(f".{out.stem}.partial{out.suffix}")


def finish_clip(raw: Path, graded: Path, saturation: float) -> bool:
    """The real encode of a clip: the 3b1b grade (unless saturation is 1), video only. Written to
    a temporary file and renamed, so an interrupted or failed encode never leaves a short clip
    that a later --concat-only would join."""
    graded.parent.mkdir(parents=True, exist_ok=True)
    tmp = _partial(graded)
    vf = ["-vf", f"eq=saturation={saturation}"] if abs(saturation - 1.0) > 1e-9 else []
    try:
        if not _ffmpeg("-i", str(raw), *vf, *FINISH, "-an", "-movflags", "+faststart", str(tmp)):
            return False
        os.replace(tmp, graded)
        return True
    finally:
        tmp.unlink(missing_ok=True)


def _fresh(out: Path, src: Path) -> bool:
    return out.exists() and src.exists() and out.stat().st_mtime_ns >= src.stat().st_mtime_ns


def ensure_graded(raw: Path, graded: Path, saturation: float) -> bool:
    """Grade `raw` unless `graded` is already its grade (renamed into place after `raw` was
    written, so a newer graded file is a complete one)."""
    return _fresh(graded, raw) or finish_clip(raw, graded, saturation)


def ensure_sheet(args, scene: str, clip: Path) -> bool:
    """Write the scene's contact sheet unless it was made from exactly this clip (a sidecar
    records which); True if written. One sheet path serves every quality, so mtimes can't tell."""
    sheet = args.media_dir / "sheets" / args.file.stem / f"{scene}.png"
    source = sheet.with_suffix(".src.json")
    made_from = load_state(source).get("clip")
    if sheet.exists() and made_from == [str(clip.resolve()), file_id(clip)]:
        return False
    sheet.parent.mkdir(parents=True, exist_ok=True)
    tmp = _partial(sheet)
    try:
        if not contact_sheet(clip, tmp):
            return False
        os.replace(tmp, sheet)
    finally:
        tmp.unlink(missing_ok=True)
    source.write_text(json.dumps({"clip": [str(clip.resolve()), file_id(clip)]}), encoding="utf-8")
    return True


def _check_report(report: Path) -> str:
    """check mode: tbb's record of every formula that failed to compile."""
    if not report.exists():
        return ""
    rows = [json.loads(r) for r in report.read_text(encoding="utf-8").splitlines() if r.strip()]
    return "\n".join(f"LaTeX error in {r['formula']!r}:\n    " + "\n    ".join(r["errors"] or ["(see the TeX log)"])
                     for r in rows)


def render_scene(cmd_base, args, scene: str, mode: str, extra: list[str]) -> SceneResult:
    """Render one scene, then (mode "clip") grade it and write its sheet, all in this worker so
    the post-processing overlaps the other scenes' renders. Modes: clip, collect (narration pass,
    animations skipped), check (animations skipped, every LaTeX error collected, still saved)."""
    module = args.file.stem
    cfg, tex_dir = scene_config(args.media_dir, module, scene)
    tag = {"clip": quality_dir(args.quality, args.fps) + ("-voice" if ENV.get("TBB_AUDIO") == "on" else ""),
           "collect": "collect"}.get(mode)
    state_file = state_path(args, scene, tag) if tag else None
    fp = scene_fingerprint(args, scene, mode, extra) if tag else ""
    if tag and not args.force:
        st = load_state(state_file)
        if st.get("fp") == fp and _still_valid(scene, mode, st):
            new_sheet = False
            if mode == "clip":  # the clip is still right; its grade may be for another --saturation
                graded = graded_path(args, scene)
                if not ensure_graded(Path(st["raw"]), graded, args.saturation):
                    return SceneResult(scene, 1, 0.0, "grading the clip with ffmpeg failed (see above)")
                new_sheet = args.sheet and ensure_sheet(args, scene, graded)
            return SceneResult(scene, 0, 0.0, st.get("warnings", ""), reused=True, sheet_new=bool(new_sheet))
    # collect stills go aside; voiced clips get their own folder (clips_dir)
    media = args.media_dir / "tbb_collect" if mode == "collect" else clips_dir(args) if mode == "clip" else args.media_dir
    flags = [f"-q{args.quality}", "--media_dir", str(media), "-c", str(cfg), "--disable_caching"]
    flags += ["--fps", f"{args.fps:g}"] if args.fps else []
    flags += INTERMEDIATE if mode == "clip" else ["-s"]  # -s skips animations (--dry_run draws them all)
    env = ENV
    if mode == "check":
        report = (args.media_dir / "tbb_check" / module / f"{scene}.jsonl").resolve()
        report.unlink(missing_ok=True)
        env = {**ENV, "TBB_CHECK_FILE": str(report)}
    if mode == "collect":
        (Path(ENV["TBB_LINES_DIR"]) / f"{scene}.jsonl").unlink(missing_ok=True)
    if mode == "clip" and ENV.get("TBB_SUBS_DIR"):
        (Path(ENV["TBB_SUBS_DIR"]) / f"{scene}.json").unlink(missing_ok=True)
    t0 = time.time()
    code, out = run_child([*cmd_base, "render", *flags, str(args.file), scene, *extra], SCENE_TIMEOUT, env=env)
    secs = time.time() - t0
    latex_found = _check_report(report) if mode == "check" else ""
    if code == 0 and not latex_found:
        warnings = "\n".join(tbb_warnings(out))
        result = SceneResult(scene, 0, secs, warnings)
        if mode == "clip":
            raw = find_video(clips_dir(args), module, args.quality, scene, args.fps)
            if raw is None:
                return result  # gather_clips explains (no animations, still image...)
            graded = graded_path(args, scene)
            if not finish_clip(raw, graded, args.saturation):
                return SceneResult(scene, 1, secs, "grading the clip with ffmpeg failed (see above)")
            result.sheet_new = bool(args.sheet and ensure_sheet(args, scene, graded))
            _save_state(scene, state_file, fp, warnings, secs, raw=raw)
        elif mode == "collect":
            _save_state(scene, state_file, fp, warnings, secs)
        return result
    if code in (124, 130):
        return SceneResult(scene, code, secs, out.strip().splitlines()[-1])
    frame = user_frame(out, args.file) if code != 0 else ""
    if latex_found:  # check mode: the formulas, then whatever stopped the scene after them
        return SceneResult(scene, 1, secs, "\n".join(x for x in (latex_found, frame) if x))
    latex = latex_error_summary(out, tex_dir, t0)
    tail = "\n".join(ln for ln in out.strip().splitlines()[-40:] if not re.match(r"^\s*[│╭╰]", ln))[-3000:]
    detail = latex or "\n".join(x for x in (tail, frame) if x)
    return SceneResult(scene, code, secs, detail)


def _lines_file(scene: str) -> Path:
    return Path(ENV.get("TBB_LINES_DIR", "")) / f"{scene}.jsonl"


def _save_state(scene, state_file: Path, fp: str, warnings: str, secs: float, raw: Path | None = None):
    st = {"fp": fp, "warnings": warnings, "seconds": round(secs, 2)}
    if raw is not None:
        st.update(raw=str(raw), raw_id=file_id(raw))
        subs = Path(ENV["TBB_SUBS_DIR"]) / f"{scene}.json" if ENV.get("TBB_SUBS_DIR") else None
        st["subs"] = file_id(subs) if subs else None
    else:  # collect: the narration lines this scene recorded (none is valid too)
        st["lines_id"] = file_id(_lines_file(scene))
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(st), encoding="utf-8")


def _still_valid(scene: str, mode: str, st: dict) -> bool:
    """The outputs a matching fingerprint promises are still there, untouched."""
    if mode == "collect":
        return st.get("lines_id") == file_id(_lines_file(scene))
    if st.get("raw_id") is None or file_id(Path(st.get("raw", ""))) != st["raw_id"]:
        return False  # deleted, or re-rendered since (another quality's run, a manual manim run)
    if ENV.get("TBB_SUBS_DIR"):  # --voice: this scene's subtitle cues, exactly as rendered
        return file_id(Path(ENV["TBB_SUBS_DIR"]) / f"{scene}.json") == st.get("subs")
    return True


def _render_order(args, scenes: list[str], mode: str) -> list[str]:
    """Longest-first (last render time, else class size), so the slowest scene never starts last."""
    tree = _parse(args.file)
    size = {n.name: (n.end_lineno or n.lineno) - n.lineno for n in tree.body if isinstance(n, ast.ClassDef)}
    tag = "collect" if mode == "collect" else quality_dir(args.quality, args.fps)
    def cost(s):
        st = load_state(state_path(args, s, tag)) or load_state(state_path(args, s, tag + "-voice"))
        return (st.get("seconds", 0.0), size.get(s, 0))
    return sorted(scenes, key=cost, reverse=True)


def run_all(cmd_base, args, scenes, extra, mode: str = "clip", quiet=False) -> tuple[list[str], dict[str, SceneResult]]:
    """Render scenes in parallel, longest first; returns (failed scenes in scene order, results)."""
    def report(r: SceneResult):
        if not quiet or r.code != 0:
            status = "reused" if r.reused else ("ok" if r.code == 0 else "FAILED")
            print(f"  {r.scene:<32} {status:>6}  " + ("" if r.reused else f"{r.seconds:6.1f}s"))
        if r.code == 0 and r.detail and not quiet:
            print("    layout: " + r.detail.replace("\n", "\n    layout: "))
        if r.code != 0:
            print(f"  {r.scene}:\n    " + r.detail.replace("\n", "\n    "), file=sys.stderr)

    results: dict[str, SceneResult] = {}
    pool = cf.ThreadPoolExecutor(max_workers=min(args.jobs, len(scenes)) or 1)
    try:
        futures = [pool.submit(render_scene, cmd_base, args, s, mode, extra) for s in _render_order(args, scenes, mode)]
        for fut in cf.as_completed(futures):
            r = fut.result()
            report(r)
            results[r.scene] = r
    except BaseException:  # Ctrl-C / SIGTERM: queued scenes must not start, running ones must stop
        stop_children()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown()
    failures = [s for s in scenes if results[s].code != 0]  # scene order, not completion order
    return failures, results


def quality_dir(quality: str, fps: float | None) -> str:
    qdir = QUALITY[quality]
    return qdir.split("p")[0] + f"p{fps:g}" if fps else qdir  # manim names it after the real fps


def find_video(media_dir: Path, module: str, quality: str, scene: str, fps: float | None) -> Path | None:
    root = media_dir / "videos" / module
    exact = root / quality_dir(quality, fps) / f"{scene}.mp4"
    if exact.exists() or fps is not None:  # an explicit --fps must never pick up another frame rate
        return exact if exact.exists() else None
    # A project manim.cfg can change the frame rate (and so the folder name): accept the newest
    # clip at the same resolution.
    height = QUALITY[quality].split("p")[0]
    found = list(root.glob(f"{height}p*/{scene}.mp4"))
    if not found:
        return None
    clip = max(found, key=lambda p: p.stat().st_mtime)
    print(f"  note: {scene}: no {exact.parent.name} clip, using {clip.parent.name} (manim.cfg sets the fps?)")
    return clip


def find_still(media_dir: Path, module: str, scene: str) -> Path | None:
    found = list((media_dir / "images" / module).glob(f"{scene}_ManimCE_v*.png"))
    found += [p for p in [media_dir / "images" / module / f"{scene}.png"] if p.exists()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


# ---------------------------------------------------------------------------
# ffmpeg plumbing
# ---------------------------------------------------------------------------
def _ffmpeg_output(*args: str) -> tuple[int, str]:
    """Run ffmpeg (never reading stdin, so it can't swallow a terminal or a pipe); (code, output)."""
    return run_child(["ffmpeg", "-nostdin", "-hide_banner", "-y", *args], FFMPEG_TIMEOUT)


def _ffmpeg(*args: str) -> bool:
    code, out = _ffmpeg_output("-loglevel", "error", *args)
    if code != 0:
        print(out[-2000:], file=sys.stderr)
    return code == 0


def _probe(video: Path, *entries: str) -> str:
    """ffprobe one value set; "" if ffprobe fails or times out."""
    code, out = run_child(["ffprobe", "-v", "error", *entries, "-of", "csv=p=0", str(video)], timeout=120)
    return out.strip() if code == 0 else ""


def video_duration(video: Path) -> float:
    """Duration of the video stream itself (the container can run longer when audio does), falling
    back to the container's; 0.0 if neither can be read."""
    for entries in (["-select_streams", "v:0", "-show_entries", "stream=duration"], ["-show_entries", "format=duration"]):
        try:
            return float(_probe(video, *entries).splitlines()[0])
        except (ValueError, IndexError):
            continue
    return 0.0


def has_audio(video: Path) -> bool:
    return bool(_probe(video, "-select_streams", "a", "-show_entries", "stream=index"))


def write_concat_list(paths, listing: Path) -> Path:
    """ffmpeg concat-demuxer list; single quotes in paths are escaped as '\\''."""
    listing.write_text("".join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in paths),
                       encoding="utf-8")
    return listing


def contact_sheet(video: Path, out: Path, cols: int = 4, rows: int = 3) -> bool:
    duration = video_duration(video)
    if duration <= 0:
        return False
    vf = f"fps={cols * rows / duration:.6f},scale=480:-1,tile={cols}x{rows}:padding=6:margin=6:color=white"
    return _ffmpeg("-i", str(video), "-vf", vf, "-frames:v", "1", str(out))


def concat(graded: list[Path], out: Path) -> bool:
    """Join graded clips without re-encoding (they share one encoder setup)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_name(f".{out.stem}_list.txt")
    try:
        write_concat_list(graded, listing)
        return _ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-an",
                       "-movflags", "+faststart", str(out))
    finally:
        listing.unlink(missing_ok=True)


def _srt_time(t: float) -> str:
    ms = round(max(t, 0) * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build_srt(scenes, durations, subs_dir: Path, out: Path) -> bool:
    entries, offset = [], 0.0
    for scene, dur in zip(scenes, durations):
        f = subs_dir / f"{scene}.json"
        if f.exists():
            entries += [(offset + a, offset + min(b, dur), txt) for a, b, txt in json.loads(f.read_text(encoding="utf-8"))]
        offset += dur
    if not entries:
        return False
    out.write_text("".join(f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(entries, 1)),
                   encoding="utf-8")
    return True


_LIMITER_LATENCY: list[bool] = []


def _limiter_has_latency() -> bool:
    if not _LIMITER_LATENCY:
        _, out = run_child(["ffmpeg", "-hide_banner", "-h", "filter=alimiter"], 60)
        _LIMITER_LATENCY.append("latency" in out)
    return _LIMITER_LATENCY[0]


def loudness_gain(wav: Path, lufs: float = -16.0, true_peak: float = -1.5) -> str:
    """ffmpeg filter that brings speech to `lufs` integrated loudness (EBU R128) without a true
    peak above `true_peak`. Measured with ebur128 at the native rate; loudnorm measures (and
    filters) at 192 kHz, which made it the slowest step of a narrated render. A gain that would
    push peaks too high gets a limiter after it; an all-silent track is left alone."""
    _, out = _ffmpeg_output("-i", str(wav), "-af", "ebur128=peak=true", "-f", "null", "-")
    summary = out.rsplit("Summary:", 1)[-1]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    if i is None or i.group(1) == "-inf" or float(i.group(1)) <= -69.9:
        return "anull"  # silence has no loudness (ebur128 reports its -70 LUFS floor)
    gain = lufs - float(i.group(1))
    af = f"volume={gain:.2f}dB"
    if peak is not None and peak.group(1) != "-inf" and float(peak.group(1)) + gain > true_peak:
        # Sample-peak limiter 1 dB under the true-peak ceiling (inter-sample peaks and AAC sit
        # above it); latency=1 compensates its look-ahead delay (ffmpeg 5+).
        af += (f",alimiter=limit={10 ** ((true_peak - 1.0) / 20):.4f}:attack=5:release=50:level=disabled"
               + (":latency=1" if _limiter_has_latency() else ""))
    return af


def concat_av(raws, graded, durations, out: Path, srt: Path | None, lufs: float = -16.0) -> bool:
    """Join graded clips (video, copied) with a continuous, loudness-normalised narration track
    taken from the raw clips. Each clip's audio (or silence) is padded/trimmed to that clip's
    exact video length, so the narration can't drift across scene boundaries. `srt`, if given,
    is embedded as a soft subtitle track."""
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / f".{out.stem}_av"
    work.mkdir(exist_ok=True)
    try:
        wavs = []
        for i, (v, d) in enumerate(zip(raws, durations)):
            w = work / f"{i:03d}.wav"
            src = ["-i", str(v), "-vn", "-af", "apad"] if has_audio(v) else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            if not _ffmpeg(*src, "-t", f"{d:.6f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(w)):
                return False
            wavs.append(w)
        raw = work / "narration_raw.wav"
        if not _ffmpeg("-f", "concat", "-safe", "0", "-i", str(write_concat_list(wavs, work / "audio.txt")),
                       "-c", "copy", str(raw)):
            return False
        inputs = ["-f", "concat", "-safe", "0", "-i", str(write_concat_list(graded, work / "video.txt")), "-i", str(raw)]
        maps = ["-map", "0:v:0", "-map", "1:a:0"]
        subs = []
        if srt is not None:
            inputs += ["-i", str(srt)]
            maps += ["-map", "2:s:0"]
            subs = ["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
        return _ffmpeg(*inputs, *maps, "-c:v", "copy", "-af", loudness_gain(raw, lufs), "-c:a", "aac", "-b:a", "192k",
                       "-ar", "48000", *subs, "-movflags", "+faststart", str(out))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def audio_coverage(video: Path, scenes, durations, max_gap: float = 4.0) -> None:
    """Report how much of the cut is voiced and every silence longer than max_gap, with its
    scene. 3b1b narration is ~85-90% voiced; long gaps mean a beat with no speech."""
    _, out = _ffmpeg_output("-i", str(video), "-vn", "-af", "silencedetect=noise=-45dB:d=0.7", "-f", "null", "-")
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", out)]
    total = sum(durations)
    gaps = [(min(a, total), min(b, total)) for a, b in zip(starts, ends + [total] * (len(starts) - len(ends)))]
    bounds, acc = [], 0.0
    for sc, d in zip(scenes, durations):
        bounds.append((acc, acc + d, sc))
        acc += d
    long = [(a, b) for a, b in gaps if b - a > max_gap]
    voiced = max(0.0, 1 - sum(b - a for a, b in gaps) / max(total, 1e-6))
    print(f"Audio check: {voiced:.0%} voiced (3b1b ~85-90%), {len(long)} silence(s) > {max_gap:g}s")
    for a, b in long[:12]:
        sc = next((n for s0, s1, n in bounds if s0 <= a < s1), "?")
        print(f"    WARN {a:7.1f}-{b:7.1f}s ({b - a:4.1f}s silent) in {sc}")


# ---------------------------------------------------------------------------
# Narration (--voice)
# ---------------------------------------------------------------------------
def narrate(*args: str, quiet: bool = False) -> int:
    """Run narrate.py (it re-executes itself inside the TTS venv)."""
    out = subprocess.DEVNULL if quiet else None
    return subprocess.run([sys.executable, str(helper("narrate.py")), *args], env=ENV, stdout=out).returncode


def collect_and_synthesise(cmd_base, args, scenes, extra, voice_dir: Path, final_dir: Path):
    """Pass 1 of --voice: run the scenes with animations skipped to record their narration (only
    scenes changed since the last pass), merge it into the project's script (other scenes' lines
    are kept, so batches accumulate), lint the style, then synthesise every missing line in one
    TTS process. Returns the Whisper QA running in the background (or None), or False on failure."""
    lines_dir = voice_dir / "lines" / args.file.stem  # per video file: two files may share scene names
    ENV["TBB_LINES_DIR"] = str(lines_dir)
    ENV["TBB_AUDIO"] = "collect"
    t0 = time.time()
    failures, results = run_all(cmd_base, args, scenes, extra, mode="collect", quiet=True)
    if failures:
        print(f"narration pass failed for {failures}", file=sys.stderr)
        return False
    lines, seen = [], set()
    for s in discover_scenes(args.file):  # whole project, in scene order: this batch + earlier batches
        f = lines_dir / f"{s}.jsonl"
        for row in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
            rec = json.loads(row)
            if rec["key"] not in seen:
                seen.add(rec["key"])
                lines.append(rec)
    reused = sum(r.reused for r in results.values())
    print(f"  collected narration for {len(scenes) - reused} scene(s) in {time.time() - t0:.1f}s"
          f"{f' ({reused} unchanged)' if reused else ''}; {len(lines)} line(s) in the project")
    if not lines:
        return None
    merged = voice_dir / f"{args.file.stem}_lines.jsonl"
    merged.write_text("".join(json.dumps(rec) + "\n" for rec in lines), encoding="utf-8")
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / f"{args.file.stem}_narration.txt").write_text(
        "\n".join(f"[{rec['scene']}] {rec['say']}" for rec in lines) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(helper("style_lint.py")), str(merged)])  # advisory
    if narrate("synth", str(merged), "--out", str(voice_dir / "audio")) != 0:
        return False
    if args.no_voice_qa:
        return None
    # Whisper round-trip (advisory: catches skipped or garbled words), alongside the render pass.
    qa = Background([sys.executable, str(helper("narrate.py")), "qa", str(merged), "--audio", str(voice_dir / "audio")])
    return qa


class Background:
    """A tracked child (stopped by Ctrl-C like the renders) whose output is printed on join()."""

    def __init__(self, cmd: list[str]):
        self._result: tuple[int, str] = (1, "")
        self._procs: list[subprocess.Popen] = []
        env = dict(ENV)  # a snapshot: the main thread keeps changing ENV for the render pass
        self._thread = threading.Thread(
            target=lambda: setattr(self, "_result", run_child(cmd, FFMPEG_TIMEOUT, env=env, started=self._procs)),
            daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        _terminate_all(self._procs)
        self._thread.join()

    def join(self) -> int:
        self._thread.join()
        code, out = self._result
        print(out.rstrip() if out.strip() else f"note: the Whisper QA didn't run (exit {code})")
        return code


# ---------------------------------------------------------------------------
def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    """Parse and validate; returns (args, extra manim args after `--`)."""
    extra: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("scenes", nargs="*", help="subset of scenes (default: all, in SCENES/source order)")
    ap.add_argument("-q", "--quality", choices=QUALITY, default="l")
    ap.add_argument("-j", "--jobs", type=int, help="parallel manim processes (default: CPU count, at most 8)")
    ap.add_argument("--check", "--stills", dest="check", action="store_true",
                    help="skip animations: report every LaTeX and Python error and the layout warnings, "
                         "and save each scene's last frame (PNG). Seconds, not minutes")
    ap.add_argument("--sheet", action="store_true", help="write a 4x3 frame contact sheet per scene")
    ap.add_argument("--fps", type=float, help="override frame rate (3b1b uses 30)")
    ap.add_argument("--saturation", type=float, default=1.5,
                    help="colour grade of every clip (3b1b: 1.5; 1 = no grade)")
    ap.add_argument("--force", action="store_true", help="re-render every scene, even unchanged ones")
    ap.add_argument("--no-captions", action="store_true", help="hide tbb captions but keep their timing")
    ap.add_argument("--voice", action="store_true",
                    help="narrate voiceover()/caption() lines with local TTS (narrate.py) and mix an audio track")
    ap.add_argument("--voice-name", default="am_michael", help="Kokoro voice (narrate.py voices)")
    ap.add_argument("--no-voice-qa", action="store_true", help="skip the Whisper transcription check")
    ap.add_argument("--embed-subs", action="store_true",
                    help="with --voice: also embed subtitles as a soft track (players may show it by default)")
    ap.add_argument("--captions", action="store_true",
                    help="with --voice: also burn captions into the picture (default: sidecar .srt only)")
    ap.add_argument("--no-concat", action="store_true", help="render clips only; don't join them")
    ap.add_argument("--concat-only", action="store_true",
                    help="skip rendering; join already-rendered clips (after rendering scenes in batches)")
    ap.add_argument("--media-dir", type=Path, default=Path("media"))
    ap.add_argument("--out", type=Path, help="joined output path (default final/<stem>_<quality>.mp4)")
    ap.add_argument("--python", default=sys.executable, help="interpreter whose manim to use")
    args = ap.parse_args(argv)

    if not args.file.exists():
        ap.error(f"{args.file} not found")
    if args.jobs is not None and args.jobs < 1:
        ap.error("-j must be at least 1")
    if args.fps is not None and args.fps <= 0:
        ap.error("--fps must be positive")
    conflicts = [("--embed-subs", args.embed_subs and not args.voice, "only applies with --voice"),
                 ("--captions", args.captions and not args.voice, "only applies with --voice"),
                 ("--captions", args.captions and args.no_captions, "contradicts --no-captions"),
                 ("--check", args.check and (args.voice or args.concat_only or args.sheet),
                  "renders no clips, so it can't be combined with --voice, --sheet or --concat-only"),
                 ("--concat-only", args.concat_only and args.no_concat, "contradicts --no-concat")]
    for flag, bad, why in conflicts:
        if bad:
            ap.error(f"{flag} {why}")
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        ap.error(f"{' and '.join(missing)} not found on PATH (macOS: brew install ffmpeg; Debian/Ubuntu: apt install ffmpeg)")
    if "'" in str(args.media_dir.resolve()):
        ap.error(f"ManimCE 0.22 can't render into a path containing a single quote ({args.media_dir.resolve()}): "
                 "its clip-joining manifest isn't escaped. Pass --media-dir somewhere without one.")
    all_scenes = discover_scenes(args.file)
    args.scenes = list(dict.fromkeys(args.scenes or all_scenes))  # a scene named twice renders once
    unknown = [s for s in args.scenes if s not in all_scenes]
    if unknown:
        ap.error(f"unknown scene(s) {unknown}; found {all_scenes}")
    if not args.scenes:
        ap.error("no scenes found (define classes with construct() or a SCENES list)")
    if args.jobs is None:
        cpus = os.process_cpu_count() if hasattr(os, "process_cpu_count") else os.cpu_count()
        args.jobs = max(1, min(cpus or 2, 8, len(args.scenes)))
    return args, extra


def narration_by_scene(voice_dir: Path, module: str) -> dict[str, set[str]]:
    """Scene -> voices of its recorded narration lines (empty for scenes that say nothing)."""
    out: dict[str, set[str]] = {}
    for f in (voice_dir / "lines" / module).glob("*.jsonl"):
        voices = {json.loads(row).get("voice", "?") for row in f.read_text(encoding="utf-8").splitlines() if row.strip()}
        if voices:
            out[f.stem] = voices
    return out


def voice_pass(args, cmd_base, extra: list[str], voice_dir: Path, subs_dir: Path, final_dir: Path):
    """Collect, lint and synthesise the narration, then set up the voiced render. Returns the
    background QA (or None), or False on failure."""
    # Fail fast, before the narration pass: a bad voice name or a missing TTS venv.
    if narrate("check-voice", args.voice_name) != 0 or narrate("python", quiet=True) != 0:
        return False
    ENV.update(TBB_VOICE=args.voice_name, TBB_VOICE_DIR=str(voice_dir))
    qa = collect_and_synthesise(cmd_base, args, args.scenes, extra, voice_dir, final_dir)
    if qa is False:
        return False
    ENV.update(TBB_AUDIO="on", TBB_SUBS_DIR=str(subs_dir))
    if not args.captions:
        ENV["TBB_CAPTIONS"] = "0"  # captions go to the .srt only
    return qa


def gather_clips(args, module: str, qdir: str, started: float) -> list[tuple[Path, Path]] | None:
    """(raw, graded) clip of every scene, grading any that lack an up-to-date graded copy (clips
    from an older render); None after reporting every scene that has no clip at all."""
    pairs, missing = [], []
    for s in args.scenes:
        v = find_video(clips_dir(args), module, args.quality, s, args.fps)
        if v is not None:
            g = graded_path(args, s)
            if not ensure_graded(v, g, args.saturation):
                return None
            pairs.append((v, g))
            continue
        still = None if args.concat_only else find_still(clips_dir(args), module, s)
        if still is not None and still.stat().st_mtime >= started - 1:  # written by this render
            missing.append(f"{s}: it has no animations (manim saved a still image instead); add a play() or wait()")
        else:
            missing.append(f"{s}: no {qdir} clip; render it first" if args.concat_only else f"{s}: manim produced no clip")
    if missing:
        print("no clip for:\n  " + "\n  ".join(missing), file=sys.stderr)
        return None
    return pairs


def finish_voiced(args, module: str, pairs, durations, out: Path, voice_dir: Path, subs_dir: Path) -> int:
    raws, graded = [r for r, _ in pairs], [g for _, g in pairs]
    narrated = {s: v for s, v in narration_by_scene(voice_dir, module).items() if s in args.scenes}
    silent = [s for s, v in zip(args.scenes, raws) if s in narrated and not has_audio(v)]
    if silent:
        print(f"  note: {', '.join(silent)} have narration but no audio (re-render them with --voice)",
              file=sys.stderr)
    srt = out.with_suffix(".srt")
    have_srt = build_srt(args.scenes, durations, subs_dir, srt)
    # MP4 subtitle tracks get flagged "default" by ffmpeg and players then show them, so the
    # sidecar .srt is the default and embedding is opt-in.
    if not concat_av(raws, graded, durations, out, srt if (have_srt and args.embed_subs) else None):
        return 1
    voices = sorted(set().union(*narrated.values())) if narrated else []
    who = f"narrated by {', '.join(voices)}, -16 LUFS" if voices else "no narration lines, silent track"
    print(f"\nFinal cut ({sum(durations):.1f}s, {who}, saturation {args.saturation:g}): {out}")
    audio_coverage(out, args.scenes, durations)
    if have_srt:
        print(f"Subtitles: {srt}" + (" (also embedded)" if args.embed_subs else " (sidecar; upload it with the video)"))
    return 0


def check(args, cmd_base, extra: list[str]) -> int:
    """--check: every scene with animations skipped, in parallel; all errors, then the stills."""
    print(f"Checking {len(args.scenes)} scene(s) from {args.file} with {args.jobs} job(s) (animations skipped)")
    started = time.time()
    failures, _ = run_all(cmd_base, args, args.scenes, extra, mode="check")
    print("\nStills:")
    for s in args.scenes:
        still = find_still(args.media_dir, args.file.stem, s)
        fresh = still is not None and still.stat().st_mtime >= started - 1  # not one from an earlier run
        print(f"  {s}: {still if fresh else '(none: the scene stopped before its last frame)'}")
    if failures:
        print(f"\n{len(failures)} scene(s) have errors: {failures}", file=sys.stderr)
        return 1
    print("\nNo errors.")
    return 0


def run(args: argparse.Namespace, extra: list[str]) -> int:
    started = time.time()
    module, qdir = args.file.stem, quality_dir(args.quality, args.fps)
    if args.no_captions:
        ENV["TBB_CAPTIONS"] = "0"
    cmd_base = manim_cmd(args.python)
    if args.check:
        return check(args, cmd_base, extra)
    out = args.out or Path("final") / f"{module}_{qdir}.mp4"
    voice_dir = (args.media_dir / "voice").resolve()
    subs_dir = voice_dir / "subs" / module / qdir  # per quality: --concat-only must not mix them
    # Render outputs inside the project must not count as scene inputs (fingerprints).
    args.outputs = (args.media_dir, out, out.with_suffix(".srt"), out.parent / f"{module}_narration.txt")

    results: dict[str, SceneResult] = {}
    if not args.concat_only:
        print(f"Rendering {len(args.scenes)} scene(s) from {args.file} at {qdir} with {args.jobs} job(s)")
        qa = None
        if args.voice:
            qa = voice_pass(args, cmd_base, extra, voice_dir, subs_dir, out.parent)
            if qa is False:
                return 1
        failures, results = run_all(cmd_base, args, args.scenes, extra)
        if failures:
            if qa is not None:
                qa.cancel()  # advisory: don't make a failed render wait for it
            print(f"\n{len(failures)} scene(s) failed: {failures}", file=sys.stderr)
            return 1
        if qa is not None:
            qa.join()

    pairs = gather_clips(args, module, qdir, started)
    if pairs is None:
        return 1
    durations = [video_duration(g) for _, g in pairs]
    print("\nClips:")
    for s, (_, g), d in zip(args.scenes, pairs, durations):
        line = f"  {s:<32} {d:6.1f}s  {g}"
        if args.sheet:
            sheet = args.media_dir / "sheets" / module / f"{s}.png"
            if s not in results and ensure_sheet(args, s, g):  # --concat-only: sheets of the clips joined
                results[s] = SceneResult(s, 0, 0.0, "", sheet_new=True)
            if sheet.exists():
                new = results.get(s) is not None and results[s].sheet_new
                line += f"\n  {'':<32} sheet: {sheet}" + (" (new)" if new else " (unchanged)")
        print(line)
    if args.sheet:
        fresh = [s for s in args.scenes if results.get(s) is not None and results[s].sheet_new]
        print(f"\nNew sheets: {', '.join(fresh) if fresh else 'none (every scene was unchanged)'}")
    if args.no_concat:
        return 0
    if args.voice:
        return finish_voiced(args, module, pairs, durations, out, voice_dir, subs_dir)
    if not concat([g for _, g in pairs], out):
        return 1
    print(f"\nFinal cut ({sum(durations):.1f}s, no audio, saturation {args.saturation:g}): {out}")
    return 0


_EXIT_ON_SIGNAL = {"code": 130}  # 130 after Ctrl-C (SIGINT), 143 after SIGTERM


def _raise_interrupt(_signum, _frame):
    """SIGTERM handler: stop the same clean way as Ctrl-C, but exit 143."""
    _EXIT_ON_SIGNAL["code"] = 143
    raise KeyboardInterrupt


def install_signal_handlers() -> None:
    # Ctrl-C and SIGTERM both stop every render. SIGINT is set explicitly because a process
    # launched in the background (`cmd &`, some agent harnesses) inherits it as ignored.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, _raise_interrupt)


def interrupted(what: str) -> int:
    """Stop every child after an interrupt; a second Ctrl-C during cleanup is ignored."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    stop_children()
    print(f"\ninterrupted: {what}", file=sys.stderr)
    return _EXIT_ON_SIGNAL["code"]


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # keep stdout and stderr in order when piped
    args, extra = parse_args(sys.argv[1:])
    install_signal_handlers()
    try:
        return run(args, extra)
    except KeyboardInterrupt:
        return interrupted("stopped all renders")


if __name__ == "__main__":
    sys.exit(main())
