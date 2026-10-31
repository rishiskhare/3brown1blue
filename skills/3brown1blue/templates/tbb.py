"""tbb — a house kit for making videos *in the style of* 3Blue1Brown with Manim Community.

Requires Manim Community >= 0.22.1. Plain ManimCE, no ManimGL.
Copy this file next to your scene files and begin every scene file with:

    from manim import *
    from tbb import *

Importing applies the house style:
  * pure black background (Grant's production config), Computer Modern words via text()
    (CMU Serif or Latin Modern Roman through Pango, else LaTeX)
  * ManimGL's exact palette where CE differs (YELLOW=#FFFF00, BLUE_E=#1C758A)
  * ManimGL's "smooth" easing (CE's `smootherstep`) as the default rate function
  * the 3b1b LaTeX preamble (CE's TexTemplateLibrary.threeb1b + pifont + \\minus)
  * yellow SurroundingRectangles with a 0.1 buff, like ManimGL

Not affiliated with 3Blue1Brown. Do not recreate the Pi creatures or the 3b1b logo — they are
copyrighted characters/brand assets.
"""
from __future__ import annotations

import functools
import hashlib
import json
import numbers
import os
import re
import shutil
import subprocess
import unicodedata
import wave
from pathlib import Path
from collections.abc import Callable, Iterable, Sequence

import numpy as np
from manim import *  # noqa: F403
from manim.animation.animation import prepare_animation as _prepare_animation

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
# Hex values match 3b1b/manim (ManimGL)'s constants.
# ManimCE's built-in color constants already equal ManimGL's (BLUE_D..A, TEAL_*, GREEN_*,
# GOLD_*, RED_*, MAROON_*, PURPLE_*, GREY_*, PINK, ORANGE, GREY_BROWN, ...) EXCEPT these two:
BLUE_E = ManimColor("#1C758A")       # CE: #236B8E
YELLOW_C = ManimColor("#FFFF00")     # CE: #F7D96F. 3b1b's highlight yellow is pure yellow.
YELLOW = YELLOW_C
SOFT_YELLOW = ManimColor("#F7D96F")  # CE's YELLOW, handy for gentler accents
DEG = DEGREES                        # ManimGL spelling

COLORMAP_3B1B = [BLUE_E, GREEN, YELLOW, RED]  # ManimGL's default heat map

# vivek3141's (ex-3b1b intern, "vcubingx") pastel palette — ColorBrewer Set3. Softer; very
# good for ML/diagram-heavy videos. Roles he used: pink=input, green=hidden/output, blue=y-hat,
# yellow=time/constants/titles, aqua=function names, grey=weights, lavender=probabilities.
A_AQUA, A_YELLOW, A_LAVENDER, A_RED = (ManimColor(c) for c in ("#8DD3C7", "#FFFFB3", "#BEBADA", "#FB8072"))
A_BLUE, A_ORANGE, A_GREEN, A_PINK = (ManimColor(c) for c in ("#80B1D3", "#FDB462", "#B3DE69", "#FCCDE5"))
A_GREY, A_VIOLET, A_MINT, A_GOLD = (ManimColor(c) for c in ("#D9D9D9", "#BC80BD", "#CCEBC5", "#FFED6F"))

# Semantic roles: one color per *concept*, used in the formula AND the picture, all video long.
X_COLOR, Y_COLOR, Z_COLOR = GREEN_C, RED_C, BLUE_D   # i-hat green, j-hat red (3b1b lin-alg)
HIGHLIGHT = YELLOW
DIM_OPACITY = 0.25

BACKGROUND = "#000000"        # Grant's custom_config.yml
SOFT_BACKGROUND = "#1C1C1C"   # softer alternative; vivek's 2024 videos used #222222
TEXT_FONTS = ("CMU Serif", "Latin Modern Roman")  # Computer Modern faces: words match the LaTeX math
PANGO_SCALE = 0.76            # Pango Text renders ~1.3x larger than Tex at equal font_size


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _pango_fonts() -> frozenset:
    try:
        import manimpango

        return frozenset(manimpango.list_fonts())
    except Exception:
        return frozenset()


def _font_installed(name: str) -> bool:
    return name in _pango_fonts()


def _register_latin_modern() -> bool:
    """TeX Live ships Latin Modern (OpenType Computer Modern). Register it with Pango for this
    process so text() gets the right face without installing a system font."""
    if not shutil.which("kpsewhich"):
        return False
    try:
        import manimpango

        names = [f"lmroman10-{style}.otf" for style in ("regular", "italic", "bold", "bolditalic")]
        found = subprocess.run(["kpsewhich", *names], capture_output=True, text=True, timeout=10).stdout.split("\n")
        ok = False
        for path in filter(None, (p.strip() for p in found)):
            ok = manimpango.register_font(path) or ok
        _pango_fonts.cache_clear()  # the registered face is now listed
        return ok
    except Exception:
        return False


TEXT_FONT = TEXT_FONTS[0] if _font_installed(TEXT_FONTS[0]) else (
    TEXT_FONTS[1] if (_font_installed(TEXT_FONTS[1]) or _register_latin_modern()) else None)
HAS_TEXT_FONT = TEXT_FONT is not None


def tbb_tex_template() -> TexTemplate:
    tpl = TexTemplateLibrary.threeb1b.copy()
    tpl.add_to_preamble(r"\usepackage{pifont}")
    tpl.add_to_preamble(r'\DeclareMathSymbol{\minus}{\mathbin}{AMSa}{"39}')  # short minus: e^{\minus st}
    # The threeb1b preamble loads tipa, which hijacks \; \: \| as phonetic commands, so
    # "\max_\pi\; x" or "\pi \,\|\, \pi_{ref}" fail to compile. Restore the math meanings.
    tpl.add_to_preamble(
        r"\AtBeginDocument{%" "\n"
        r"\DeclareRobustCommand{\;}{\ifmmode\mskip\thickmuskip\else\hspace{0.2777em}\fi}%" "\n"
        r"\DeclareRobustCommand{\:}{\ifmmode\mskip\medmuskip\else\hspace{0.2222em}\fi}%" "\n"
        r"\DeclareRobustCommand{\|}{\ifmmode\Vert\else\textbardbl\fi}}"
    )
    return tpl


def apply_style(background: str = BACKGROUND, gl_easing: bool = True, tex_template: bool = True) -> None:
    """Apply the house look. Runs on import; call again (module level) to change options.
    gl_easing=False / tex_template=False restore ManimCE's defaults."""
    config.background_color = background
    config.tex_template = tbb_tex_template() if tex_template else TexTemplate()
    if HAS_TEXT_FONT:
        Text.set_default(font=TEXT_FONT)
        MarkupText.set_default(font=TEXT_FONT)
    if gl_easing:
        Animation.set_default(rate_func=smootherstep)
    else:
        Animation.set_default()  # no arguments: back to CE's own defaults
    SurroundingRectangle.set_default(color=YELLOW, buff=SMALL_BUFF)  # 3b1b's pure yellow, not CE's softer one


apply_style()


# ---------------------------------------------------------------------------
# Text & Tex
# ---------------------------------------------------------------------------
_CONTROL_WORD_TAIL = re.compile(r"\\[A-Za-z]*$")


def _split_on_keys(s: str, keys: Iterable[str]) -> list[str]:
    """Split a TeX string into pieces so every occurrence of each key is its own piece.

    Matches that would land inside a control word (the "n" in \\infty, "\\pi" in \\pitchfork)
    are skipped — wrap variables in braces ("{n}") to be unambiguous, 3b1b's own trick.
    """
    keys = sorted({k for k in keys if k}, key=len, reverse=True)
    if not keys:
        return [s]
    pattern = re.compile("|".join(re.escape(k) for k in keys))
    text_spans = _text_spans(s)
    pieces, last, pos = [], 0, 0
    while True:
        m = pattern.search(s, pos)
        if m is None:
            break
        a, b = m.span()
        key = m.group()
        inside_word = key[0].isalpha() and _CONTROL_WORD_TAIL.search(s[:a])
        runs_on = key[-1].isalpha() and b < len(s) and s[b].isalpha() and (key[0] == "\\" or inside_word)
        in_text = any(lo <= a < hi for lo, hi in text_spans)  # the "x" of \text{max} is a word
        if inside_word or runs_on or in_text:
            pos = a + 1
            continue
        if a > last:
            pieces.append(s[last:a])
        pieces.append(key)
        last = pos = b
    if last < len(s):
        pieces.append(s[last:])
    return pieces


_SCRIPT_TAIL = re.compile(r"[\^_]\s*$")                    # "e^", "x_": always takes an argument
_MACRO_ARG_TAIL = re.compile(r"(\\[A-Za-z]+|[}\]])\s*$")  # "\frac", "\frac{a}", "\sqrt[3]": may take one
_TEXT_COMMAND = re.compile(r"\\(?:text[a-z]*|mathrm|operatorname|mbox)\s*\{")


def _is_argument(prev: str, key: str) -> bool:
    if _SCRIPT_TAIL.search(prev):
        return True
    # After a macro, "}" or "]", a key that is a group, a letter or a macro ("{x}", "y" in
    # "\hat y", "\pi") may be its argument; bracing it is harmless if not. Operator keys like "="
    # are left alone so they keep their spacing ("{=}" would lose it).
    return (key[0] in "{\\" or key[0].isalnum()) and _MACRO_ARG_TAIL.search(prev) is not None


def _group_arguments(pieces: list[str], keys: set[str]) -> list[str]:
    """MathTex wraps each piece in its own \\special group, so a piece that is the argument of
    ^, _ or a macro ("e^{x}", "\\frac{x}{2}", "\\hat y") would hand that macro the \\special
    instead and LaTeX fails. Brace such pieces once more: "e^{" + "{x}" + "}" compiles.
    `pieces` must come from ONE input string, so the closing brace never joins another string."""
    out: list[str] = []
    for p in pieces:
        if p in keys and out and _is_argument(out[-1], p):
            out[-1] += "{"
            out.append(p)
            out.append("}")
        elif out and out[-1] == "}" and p not in keys:
            out[-1] += p  # fold the closing brace into the following plain piece of this string
        else:
            out.append(p)
    return out


def _text_spans(s: str) -> list[tuple[int, int]]:
    """(start, end) of the contents of every \\text{...}-style group: words, not math."""
    spans = []
    for m in _TEXT_COMMAND.finditer(s):
        depth, i = 1, m.end()
        while i < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[i], 0) if s[i - 1] != "\\" else 0
            i += 1
        spans.append((m.end(), i - 1))
    return spans


def _colorize(mob: MathTex, t2c: dict) -> None:
    for part in mob.submobjects:
        color = t2c.get(getattr(part, "tex_string", None))
        if color is not None:
            part.set_color(color)


def tex(*strings: str, t2c: dict | None = None, isolate: Iterable[str] = (), font_size: float = 48,
        **kwargs) -> MathTex:
    """Math, the 3b1b way: `tex(r"f({x}) = {x}^2", t2c={"{x}": X_COLOR})`.

    Every t2c key and every `isolate` string becomes its own submobject (so TransformTex can
    match it and `parts(eq, key)` can select it). Splitting is done here rather than via
    MathTex(substrings_to_isolate=...), which drops glyphs with some dvisvgm builds.
    Wrap single-letter variables in braces ("{t}") so "t" inside \\int or \\theta is untouched.
    """
    t2c = dict(t2c or {})
    keys = list(t2c) + list(isolate)
    pieces: list[str] = []
    for s in strings:  # group per string, so each input string stays its own piece(s)
        pieces.extend(_group_arguments(_split_on_keys(s, keys), set(keys)))
    mob = MathTex(*pieces, font_size=font_size, **kwargs)
    # A brace added to close a group at the end of a string is its own glyph-less piece: drop it
    # so eq[i] and parts() only ever see real content.
    mob.remove(*[p for p in mob.submobjects
                 if getattr(p, "tex_string", None) == "}" and not p.family_members_with_points()])
    _colorize(mob, t2c)
    return mob


def parts(mob: MathTex, key: str) -> VGroup:
    """All submobjects whose tex string == key — CE's stand-in for ManimGL's `tex["key"]`.
    Index the result for one occurrence: parts(eq, "{x}")[1]."""
    return VGroup(*[p for p in mob.submobjects if getattr(p, "tex_string", None) == key])


def text(s: str, font_size: float = 48, color=WHITE, t2c: dict | None = None, **kwargs) -> Mobject:
    """Words in Computer Modern: Pango `Text` in CMU Serif or Latin Modern Roman when installed,
    else LaTeX text mode (same face, slower). font_size is calibrated to match tex() in both
    modes. `t2c` colors substrings in both modes."""
    if HAS_TEXT_FONT:
        return Text(s, font_size=font_size * PANGO_SCALE, color=color, t2c=t2c or {}, **kwargs)
    colors = {_tex_escape(k): c for k, c in (t2c or {}).items()}
    body = r"\\".join(_tex_escape(line) for line in s.split("\n"))
    mob = Tex(*_split_on_keys(body, list(colors)), font_size=font_size, color=color, **kwargs)
    for part in mob.submobjects:
        if getattr(part, "tex_string", None) in colors:
            part.set_color(colors[part.tex_string])
    return mob


_TEX_SPECIALS = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "_": r"\_", "^": r"\textasciicircum{}",
                 "~": r"\textasciitilde{}", "&": r"\&", "%": r"\%", "#": r"\#", "$": r"\$"}


def _tex_escape(s: str) -> str:
    """Plain text -> LaTeX text-mode source (used by text()'s fallback when no font is installed)."""
    return "".join(_TEX_SPECIALS.get(ch, ch) for ch in s)


def _fit_width(mob: Mobject, max_width: float) -> Mobject:
    if mob.width > max_width:
        mob.scale_to_fit_width(max_width)
    return mob


def _label_mob(s: str, math: bool, font_size: float, color) -> Mobject:
    return MathTex(s, font_size=font_size, color=color) if math else text(s, font_size=font_size, color=color)


def title(s: str, font_size: float = 60, color=WHITE, underlined: bool = True,
          buff: float = MED_SMALL_BUFF) -> VGroup:
    """Top-of-frame title with 3b1b's tight underline. Returns VGroup(words, underline).
    Reveal: self.play(FadeIn(t[0], lag_ratio=0.1), Create(t[1]))."""
    words = _fit_width(text(s, font_size=font_size, color=color), config.frame_width - 1).to_edge(UP, buff=buff)
    group = VGroup(words)
    if underlined:
        group.add(underline(words))
    return group


def _check_target(fn: str, target, s) -> None:
    """The kit's convention is target first, then text: catch the old label(s, mob) order."""
    if isinstance(target, str) and not isinstance(s, str):
        raise TypeError(f"{fn}(mob, s, ...): the mobject (or point) comes first, then the label text")


def label(mob, s: str, direction=UP, color=WHITE, font_size: float = 36, math: bool = True,
          buff: float = 0.15, backstroke_width: float = 4) -> Mobject:
    """Small math (default) or text label next to `mob` (a mobject or a point), with a black
    backstroke so it reads over grids and curves. backstroke_width=0 for none."""
    _check_target("label", mob, s)
    lab = _label_mob(s, math, font_size, color).next_to(mob, direction, buff=buff)
    return backstroke(lab, stroke_width=backstroke_width) if backstroke_width else lab


# ---------------------------------------------------------------------------
# Emphasis
# ---------------------------------------------------------------------------
def backstroke(mob: VMobject, color=BLACK, stroke_width: float = 3) -> VMobject:
    """ManimGL `set_backstroke`: a stroke drawn *behind* the fill. 3-5 is typical."""
    mob.set_stroke(color, width=stroke_width, opacity=1, background=True)
    return mob


def underline(mob: Mobject, color=GREY_B, buff: float = 0.08, stroke_width: float = 2,
              stretch: float = 1.05) -> Line:
    line = Line(LEFT, RIGHT, color=color, stroke_width=stroke_width)
    line.set_width(mob.width * stretch)
    line.next_to(mob, DOWN, buff=buff)
    return line


def highlight_rect(mob: Mobject, color=None, buff: float = SMALL_BUFF, stroke_width: float = 2,
                   fill_opacity: float = 0.0, corner_radius: float = 0.0) -> SurroundingRectangle:
    color = HIGHLIGHT if color is None else color
    rect = SurroundingRectangle(mob, color=color, buff=buff, corner_radius=corner_radius)
    rect.set_stroke(color, stroke_width).set_fill(color, fill_opacity)
    return rect


def FlashAround(mob: Mobject, color=None, buff: float = SMALL_BUFF, stroke_width: float = 4,
                time_width: float = 1.0, run_time: float = 1.5, **kwargs) -> Animation:
    """ManimGL FlashAround: a tapered streak of light runs once around `mob`."""
    color = HIGHLIGHT if color is None else color
    rect = SurroundingRectangle(mob, buff=buff)
    rect.set_stroke(color, stroke_width).set_fill(opacity=0)
    rect.insert_n_curves(60)
    return ShowPassingFlashWithThinningStrokeWidth(rect, time_width=time_width, n_segments=12,
                                                   run_time=run_time, **kwargs)


def FlashUnder(mob: Mobject, color=None, stroke_width: float = 4, run_time: float = 1.2,
               **kwargs) -> Animation:
    """A flash of light runs once along an underline (no line is left behind)."""
    color = HIGHLIGHT if color is None else color
    line = underline(mob, color=color, stroke_width=stroke_width)
    line.insert_n_curves(20)
    return ShowPassingFlash(line, time_width=0.6, run_time=run_time, **kwargs)


def pulse_along(path: VMobject, color=YELLOW, stroke_width: float = 6, time_width: float = 0.4,
                run_time: float = 2, **kwargs) -> Animation:
    """VShowPassingFlash: a glowing pulse travels along a curve (signal flow, a path, a graph)."""
    copy = path.copy().set_stroke(color, stroke_width).set_fill(opacity=0)
    kwargs.setdefault("rate_func", linear)
    return ShowPassingFlash(copy, time_width=time_width, run_time=run_time, **kwargs)


def glow_dot(point=ORIGIN, color=YELLOW, radius: float = 0.05, glow_radius: float = 0.3,
             layers: int = 14) -> VGroup:
    """ManimGL `Group(TrueDot(), GlowDot())`: a crisp core with a soft radial halo.
    Move it with `.move_to` / `.animate` / updaters. glow_dot(...)[1] is the core."""
    color = ManimColor(color)  # accept "#FF0000" strings as well as color constants
    radii = np.linspace(glow_radius, radius, layers)
    halo = VGroup(*[Dot(point, radius=r, color=color, stroke_width=0, fill_opacity=0.07) for r in radii])
    core = Dot(point, radius=radius, color=interpolate_color(color, WHITE, 0.3), stroke_width=0)
    return VGroup(halo, core)


def tracing_tail(mob: Mobject, time_traced: float = 1.0, color=None, stroke_width: float = 3) -> TracedPath:
    """ManimGL TracingTail: a comet tail that fades over `time_traced` seconds. Add it to the
    scene; it follows mob's center."""
    color = color or mob.get_color()
    return TracedPath(mob.get_center, dissipating_time=time_traced, stroke_color=color,
                      stroke_width=stroke_width, stroke_opacity=[0, 1])


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
def brace_label(mob: Mobject, s: str, direction=DOWN, color=WHITE, font_size: float = 36,
                math: bool = True, buff: float = SMALL_BUFF) -> VGroup:
    """VGroup(brace, label). Reveal: GrowFromCenter(g[0]), FadeIn(g[1], shift=0.2*direction)."""
    _check_target("brace_label", mob, s)
    brace = Brace(mob, direction=direction, buff=buff, color=GREY_A)
    lab = _label_mob(s, math, font_size, color)
    brace.put_at_tip(lab)
    return VGroup(brace, lab)


def labeled_arrow(start, end, s: str, direction=UP, color=WHITE, label_color=None, font_size: float = 32,
                  math: bool = True, stroke_width: float = 4, **arrow_kwargs) -> VGroup:
    """Arrow from start to end with a label beside its midpoint (`direction=RIGHT` for vertical
    arrows). Returns VGroup(arrow, label)."""
    arrow = Arrow(start, end, buff=0.1, color=color, stroke_width=stroke_width, **arrow_kwargs)
    lab = _label_mob(s, math, font_size, label_color or color)
    lab.next_to(arrow.get_center(), direction, buff=0.15)
    return VGroup(arrow, lab)


def _opacity(m: Mobject) -> tuple[float, ...] | None:
    """A part's own opacities: (fill, stroke, backstroke) for a VMobject, (alpha,) for an image."""
    if isinstance(m, VMobject):
        return m.get_fill_opacity(), m.get_stroke_opacity(), m.get_stroke_opacity(background=True)
    if isinstance(m, ImageMobject):
        return (float(getattr(m, "stroke_opacity", 1.0)),)
    return None


def _set_opacity(m: Mobject, values: tuple[float, ...]) -> None:
    if isinstance(m, VMobject):
        m.set_fill(opacity=values[0], family=False)
        m.set_stroke(opacity=values[1], family=False)
        m.set_stroke(opacity=values[2], background=True, family=False)
    elif isinstance(m, ImageMobject):
        m.set_opacity(values[0])


def _full_opacity(m: Mobject) -> tuple[float, ...] | None:
    """Opacity to dim from and restore to: remembered by the first dim(), else the current one."""
    return getattr(m, "_tbb_full_opacity", None) or _opacity(m)


def _scaled_opacity(m: Mobject, factor: float, fill_factor: float = 1.0) -> Mobject:
    """A copy of `m` whose every part has `factor` x its full opacity, so outlines stay unfilled.
    The copy forgets dim() memory: it is a new object at its own full opacity."""
    out = m.copy()
    for src, dst in zip(m.get_family(), out.get_family()):
        full = _full_opacity(src)
        if full is not None:
            scaled = [x * factor for x in full]
            if len(scaled) == 3:
                scaled[0] *= fill_factor
            _set_opacity(dst, tuple(scaled))
        dst.__dict__.pop("_tbb_full_opacity", None)
    return out


def _hold_opacity(mob: Mobject, factor: float | None) -> None:
    """Objects redrawn by their own updaters (always_redraw, live_number) would reset to full
    opacity every frame; a trailing updater re-applies the dim. factor=None removes it."""
    old = mob.__dict__.pop("_tbb_hold", None)
    if old is not None:
        mob.remove_updater(old)
        mob.__dict__.pop("_tbb_hold_full", None)
    if factor is None or not any(p.updaters for p in mob.get_family()):
        return
    fulls = [f for f in (_full_opacity(p) for p in mob.get_family()) if f is not None and len(f) == 3]
    fill, stroke, back = (max(col) for col in zip(*fulls)) if fulls else (1.0, 1.0, 1.0)
    mob._tbb_hold_full = (fill, stroke, back)  # parts rebuilt while dimmed restore to these

    def hold(m):
        for p in m.get_family():
            if isinstance(p, VMobject):
                current = _opacity(p)
                _set_opacity(p, tuple(c and t * factor for c, t in zip(current, (fill, stroke, back))))

    mob.add_updater(hold)
    mob._tbb_hold = hold


class _FadeParts(Animation):
    """Animate every part of `mob` to `factor` x its full opacity. Full opacities are remembered
    when the first dim *plays* (not when it is built) and forgotten when restore=True finishes."""

    def __init__(self, mob: Mobject, factor: float, restore: bool = False, **kwargs):
        self.factor, self.restore = factor, restore
        super().__init__(mob, **kwargs)

    def begin(self) -> None:
        self._parts = []
        held = getattr(self.mobject, "_tbb_hold_full", None)  # set while a redrawn object is dimmed
        for p in self.mobject.get_family():
            full = _full_opacity(p)
            if full is None:
                continue
            if held is not None and len(full) == 3 and "_tbb_full_opacity" not in p.__dict__:
                full = tuple(h if c else 0.0 for c, h in zip(full, held))  # rebuilt while dimmed
            p.__dict__.setdefault("_tbb_full_opacity", full)
            self._parts.append((p, _opacity(p), tuple(x * self.factor for x in full)))
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        a = self.rate_func(alpha)
        for p, start, end in self._parts:
            _set_opacity(p, tuple(x + (y - x) * a for x, y in zip(start, end)))

    def finish(self) -> None:
        # Animation.finish() resumes the mobject's updaters and runs them once, so a hold must be
        # removed before it when restoring (else it re-dims), and added after it when dimming.
        if self.restore:
            _hold_opacity(self.mobject, None)
        super().finish()
        if self.restore:
            for p, _, _ in self._parts:
                p.__dict__.pop("_tbb_full_opacity", None)
        else:
            _hold_opacity(self.mobject, self.factor)


def _split_kept(m: Mobject, keep_ids: set[int]) -> list[tuple[Mobject, bool]]:
    """`m` as its largest pieces, in drawing order, each marked kept or not: a group holding
    one kept glyph becomes [(rest..., False), (glyph, True), ...]."""
    if id(m) in keep_ids:
        return [(m, True)]
    if not any(id(sm) in keep_ids for sm in m.get_family()):
        return [(m, False)]
    return [piece for sub in m.submobjects for piece in _split_kept(sub, keep_ids)]


def _ids_of(keep) -> set[int]:
    """Family ids of mobjects given directly or as lists/groups (parts(eq, key), [a, b])."""
    kept = [m for k in keep for m in ([k] if isinstance(k, Mobject) else k)]
    return {id(m) for k in kept for m in k.get_family()}


def dim(*mobs: Mobject, opacity: float | None = None) -> list[Animation]:
    """Push mobjects into the background: self.play(*dim(a, b)). Each part keeps its own
    proportions (an outline stays an outline), images and self-redrawing objects dim too, and
    undim() restores the originals. opacity defaults to DIM_OPACITY."""
    factor = DIM_OPACITY if opacity is None else opacity
    return [_FadeParts(m, factor) for m in mobs]


def undim(*mobs: Mobject) -> list[Animation]:
    """Bring dim()-ed mobjects back to their original opacities."""
    return [_FadeParts(m, 1.0, restore=True) for m in mobs]


def focus_on(eq: VMobject, *keep: Mobject | Iterable[Mobject], opacity: float | None = None) -> list[Animation]:
    """Dim everything in `eq` except the kept parts, at any depth: focus_on(eq, parts(eq, "{x}")),
    focus_on(eq, eq[0], eq[2]) or a single glyph eq[0][1]. Kept parts that were dimmed come back."""
    factor = DIM_OPACITY if opacity is None else opacity
    return [_FadeParts(p, 1.0, restore=True) if kept else _FadeParts(p, factor)
            for p, kept in _split_kept(eq, _ids_of(keep))]


def speech_bubble(content: Mobject, direction=DL, color=GREY_A, buff: float = 0.3,
                  corner_radius: float = 0.3) -> VGroup:
    """A plain speech bubble around `content`, tail pointing toward `direction`.
    Returns VGroup(bubble, content); the tail tip is bubble.tip_point."""
    body = RoundedRectangle(width=content.width + 2 * buff, height=content.height + 2 * buff,
                            corner_radius=corner_radius, stroke_color=color, stroke_width=2)
    body.move_to(content)
    dx, dy = np.sign(direction[0]) or -1, np.sign(direction[1]) or -1
    base = body.get_corner(np.array([dx, dy, 0])) + np.array([-dx * 0.7, 0, 0]) - np.array([0, dy * 0.05, 0])
    tip = base + np.array([dx * 0.4, dy * 0.6, 0])
    tail = Polygon(base + LEFT * 0.18, tip, base + RIGHT * 0.18, stroke_color=color, stroke_width=2)
    tail.set_fill(BLACK, 1)
    body.set_fill(BLACK, 1)
    bubble = VGroup(body, tail)
    bubble.tip_point = tip
    return VGroup(bubble, content)


# ---------------------------------------------------------------------------
# Math objects
# ---------------------------------------------------------------------------
AXIS_CONFIG = dict(color=GREY_B, stroke_width=2, include_tip=False, tick_size=0.05,
                   longer_tick_multiple=1.5, font_size=24)


def tbb_axes(x_range=(-1, 6, 1), y_range=(-1, 4, 1), x_length: float = 10, y_length: float = 5.5,
             numbers: bool = True, **kwargs) -> Axes:
    """3b1b axes: no tips, thin GREY_B lines, small numbers. Plot with stroke 3:
    `ax.plot(f, color=BLUE, stroke_width=3)`."""
    axis_config = {**AXIS_CONFIG, "include_numbers": numbers, **kwargs.pop("axis_config", {})}
    kwargs.setdefault("tips", False)
    return Axes(x_range=list(x_range), y_range=list(y_range), x_length=x_length, y_length=y_length,
                axis_config=axis_config, **kwargs)


def tbb_plane(x_range=(-8, 8, 1), y_range=(-5, 5, 1), faded_line_ratio: int = 2, **kwargs) -> NumberPlane:
    """3b1b NumberPlane: BLUE_D grid, faint BLUE_E sub-grid, white axes. Style dicts you pass
    (background_line_style=, faded_line_style=, axis_config=) are merged into these, like tbb_axes."""
    styles = dict(
        background_line_style=dict(stroke_color=BLUE_D, stroke_width=2, stroke_opacity=1),
        faded_line_style=dict(stroke_color=BLUE_E, stroke_width=1, stroke_opacity=0.5),
        axis_config=dict(stroke_color=WHITE, stroke_width=2),
    )
    for key, base in styles.items():
        kwargs[key] = {**base, **kwargs.pop(key, {})}
    return NumberPlane(x_range=list(x_range), y_range=list(y_range), faded_line_ratio=faded_line_ratio, **kwargs)


def tbb_number_line(x_range=(-5, 5, 1), length: float = 12, numbers: bool = True, **kwargs) -> NumberLine:
    cfg = {**AXIS_CONFIG, "font_size": 30, "tick_size": 0.1, "include_numbers": numbers, **kwargs}
    return NumberLine(x_range=list(x_range), length=length, **cfg)


def _light_copy(m: Mobject, copies: dict[int, Mobject] | None = None) -> Mobject:
    """A copy of a glyph tree that copies only what DecimalNumber changes (arrays, children,
    updaters). Mobject.copy() deep-copies the whole Tex machinery and is the cost of every frame
    of a live number (most of the render time of a number-heavy scene). A Tex's lookup of its
    parts (get_part_by_tex, set_color_by_tex) is rebuilt onto the copies, never shared."""
    top = copies is None
    copies = {} if top else copies
    c = m.__class__.__new__(m.__class__)
    d = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in m.__dict__.items()}
    d["submobjects"] = [_light_copy(s, copies) for s in m.submobjects]
    d["updaters"] = []
    c.__dict__ = d
    copies[id(m)] = c
    if top:  # every part is copied now: point each copied lookup at the copies
        for orig_id, cp in list(copies.items()):
            lookup = cp.__dict__.get("id_to_vgroup_dict")
            if lookup:
                cp.id_to_vgroup_dict = {k: VGroup(*[copies.get(id(sm), sm) for sm in g.submobjects])
                                        for k, g in lookup.items()}
    return c


def _decimal_string_to_mob(self, string, mob_class=None, **kwargs):
    # Same as ManimCE 0.22's DecimalNumber._string_to_mob, with a light copy of the cached glyphs.
    from manim.mobject.text.numbers import string_to_mob_map
    if mob_class is None:
        mob_class = self.mob_class
    if string not in string_to_mob_map:
        string_to_mob_map[string] = mob_class(string, **kwargs)
    mob = _light_copy(string_to_mob_map[string])
    mob.font_size = self._font_size
    return mob


DecimalNumber._string_to_mob = _decimal_string_to_mob


def live_number(tracker: ValueTracker | Callable[[], float], decimals: int = 2, color=WHITE,
                font_size: float = 40, **kwargs) -> DecimalNumber:
    """DecimalNumber that follows a ValueTracker (or any zero-arg callable). Position it with
    `.next_to(...)` once, or add `num.always.next_to(dot, UP)` to make it follow something."""
    get = tracker.get_value if isinstance(tracker, ValueTracker) else tracker
    num = DecimalNumber(get(), num_decimal_places=decimals, color=color, font_size=font_size, **kwargs)
    num.add_updater(lambda m: m.set_value(get()))
    return num


def tracked_dot(axes: Axes, graph: ParametricFunction, tracker: ValueTracker, color=YELLOW,
                radius: float = DEFAULT_DOT_RADIUS) -> Dot:
    """A dot riding `graph` at x = tracker.get_value()."""
    dot = Dot(color=color, radius=radius)
    dot.add_updater(lambda d: d.move_to(axes.i2gp(tracker.get_value(), graph)))
    dot.update()  # start on the curve, so .next_to(dot) works before the first frame
    return dot


def tangent_line(axes: Axes, graph: ParametricFunction, tracker: ValueTracker, length: float = 4,
                 color=YELLOW, stroke_width: float = 3, dx: float = 1e-4) -> Line:
    """Tangent to `graph` at x = tracker.get_value(), redrawn every frame."""
    f = graph.underlying_function

    def make():
        x = tracker.get_value()
        line = Line(axes.c2p(x - dx, f(x - dx)), axes.c2p(x + dx, f(x + dx)),
                    color=color, stroke_width=stroke_width)
        line.set_length(length)
        return line.move_to(axes.c2p(x, f(x)))

    return always_redraw(make)


def ghost(mob: VMobject, opacity: float = 0.3) -> VMobject:
    """A faded copy left behind as a reference ("before" state, full curve under a tracer).
    Strokes keep `opacity` x their own; fills half that, and unfilled curves stay unfilled."""
    return _scaled_opacity(mob, opacity, fill_factor=0.5)


# ---------------------------------------------------------------------------
# Diagrams (patterns from vivek3141's deep-learning series, written fresh for CE)
# ---------------------------------------------------------------------------
class NeuralNetwork(VGroup):
    """Layered network diagram: NeuralNetwork([3, 5, 5, 2]).

    .layers[i] is a VGroup of neuron Circles, .edges[i] the Lines between layer i and i+1.
    Layers larger than `max_shown` show their first/last neurons around a \\vdots.
    Colors follow vivek's roles: input pink, hidden green, output blue.
    Animate: self.play(lagged(Create, nn.layers, lag_ratio=0.3), lagged(Create, nn.edges))
    Signal flow: self.play(lagged(pulse_along, [e for g in nn.edges for e in g], lag_ratio=0.01))
    """

    def __init__(self, sizes: Sequence[int], layer_buff: float = 2.0, neuron_radius: float = 0.18,
                 neuron_buff: float = 0.25, max_shown: int = 6, colors: Sequence | None = None,
                 edge_color=GREY_B, edge_stroke_width: float = 1.0, edge_opacity: float = 0.6, **kwargs):
        super().__init__(**kwargs)
        n = len(sizes)
        if n < 2:
            raise ValueError("NeuralNetwork needs at least two layers, e.g. NeuralNetwork([3, 2])")
        if max_shown < 2:
            raise ValueError("max_shown must be at least 2 (one neuron each side of the \\vdots)")
        colors = list(colors) if colors else [A_PINK] + [A_GREEN] * (n - 2) + [A_BLUE]
        if len(colors) != n:
            raise ValueError(f"colors= needs one color per layer ({n}), got {len(colors)}")
        self.layers, self.dots = VGroup(), VGroup()
        gaps = []  # (layer index, index of first neuron below the \vdots)
        for i, size in enumerate(sizes):
            shown = min(size, max_shown)
            neurons = VGroup(*[
                Circle(radius=neuron_radius, stroke_color=colors[i], stroke_width=3).set_fill(BLACK, 1)
                for _ in range(shown)
            ]).arrange(DOWN, buff=neuron_buff)
            if size > max_shown:
                half = shown // 2
                neurons[:half].shift(0.3 * UP)
                neurons[half:].shift(0.3 * DOWN)
                gaps.append((i, half))
            self.layers.add(neurons)
        self.layers.arrange(RIGHT, buff=layer_buff)
        for i, half in gaps:
            a, b = self.layers[i][half - 1], self.layers[i][half]
            self.dots.add(MathTex(r"\vdots", color=GREY_B).move_to((a.get_center() + b.get_center()) / 2))
        self.edges = VGroup()
        for a, b in zip(self.layers[:-1], self.layers[1:]):
            self.edges.add(VGroup(*[
                Line(n1.get_right(), n2.get_left(), stroke_color=edge_color, stroke_width=edge_stroke_width,
                     stroke_opacity=edge_opacity)
                for n1 in a for n2 in b
            ]))
        self.add(self.edges, self.layers, self.dots)

    def activate(self, layer: int, values: Sequence[float], color=None) -> Animation:
        """Fill neurons of `layer` with opacity = activation in [0, 1]."""
        neurons = self.layers[layer]
        color = color or neurons[0].get_stroke_color()
        return AnimationGroup(*[n.animate.set_fill(color, float(np.clip(v, 0, 1)))
                                for n, v in zip(neurons, values)])


class ProbabilityBars(VGroup):
    """Horizontal bar chart of a distribution (next-token probabilities, class scores, ...).

    bars = ProbabilityBars(["cat", "dog", "fish"], [0.6, 0.3, 0.1])
    self.play(bars.reveal())                 # labels write, bars grow left-to-right one by one
    self.play(bars.animate_to([0.2, 0.7, 0.1]))
    """

    def __init__(self, labels: Sequence[str], probs: Sequence[float], max_width: float = 4.0,
                 bar_height: float = 0.38, buff: float = 0.18, color=A_LAVENDER, font_size: float = 32,
                 decimals: int = 2, **kwargs):
        super().__init__(**kwargs)
        if len(labels) != len(probs):
            raise ValueError(f"{len(labels)} labels but {len(probs)} probabilities")
        if not labels:
            raise ValueError("ProbabilityBars needs at least one bar")
        self.max_width, self.bar_height = max_width, bar_height
        self.labels = VGroup(*[text(s, font_size=font_size) for s in labels])
        self.bars = VGroup(*[
            Rectangle(width=max(p * max_width, 1e-3), height=bar_height, stroke_width=0)
            .set_fill(color, 0.9) for p in probs
        ])
        self.numbers = VGroup(*[DecimalNumber(p, num_decimal_places=decimals, font_size=font_size * 0.8)
                                for p in probs])
        rows = VGroup()
        for lab, bar, num in zip(self.labels, self.bars, self.numbers):
            rows.add(VGroup(lab, bar, num))
        rows.arrange(DOWN, buff=buff)
        label_right = max(lab.get_right()[0] for lab in self.labels)
        for lab, bar, num in zip(self.labels, self.bars, self.numbers):
            lab.shift((label_right - lab.get_right()[0]) * RIGHT)
            bar.next_to([label_right, lab.get_y(), 0], RIGHT, buff=0.25)
            self._place_number(num, bar)
            num.add_updater(lambda m, b=bar: self._place_number(m, b))
        self.add(self.labels, self.bars, self.numbers)

    @staticmethod
    def _place_number(num: Mobject, bar: Mobject) -> None:
        num.next_to(bar, RIGHT, buff=0.15)

    def reveal(self, lag_ratio: float = 0.15) -> Animation:
        """Labels write, then each bar grows from the left with its number."""
        grows = [GrowFromEdge(b, LEFT) for b in self.bars]
        nums = [FadeIn(n, shift=0.2 * RIGHT) for n in self.numbers]
        return Succession(
            Write(self.labels),
            LaggedStart(*[AnimationGroup(g, f) for g, f in zip(grows, nums)], lag_ratio=lag_ratio),
        )

    def animate_to(self, probs: Sequence[float], run_time: float = 1.5) -> Animation:
        """Bars stretch to the new values; each number counts and rides along with its bar."""
        if len(probs) != len(self.bars):
            raise ValueError(f"{len(self.bars)} bars but {len(probs)} probabilities")
        anims = []
        for bar, num, p in zip(self.bars, self.numbers, probs):
            left = bar.get_left()
            target = bar.copy().stretch_to_fit_width(max(p * self.max_width, 1e-3)).move_to(left, LEFT)
            anims.append(Transform(bar, target))

            # An animation suspends num's own updater, so the number moves here (after the
            # bar in the same group, so it reads the bar's current frame).
            def follow(m, alpha, b=bar, v0=num.get_value(), v1=p):
                m.set_value(interpolate(v0, v1, alpha))
                self._place_number(m, b)

            anims.append(UpdateFromAlphaFunc(num, follow))
        return AnimationGroup(*anims, run_time=run_time)


# ---------------------------------------------------------------------------
# Timing & transforms
# ---------------------------------------------------------------------------
def time_span(anim: Animation, start: float, end: float, run_time: float) -> Animation:
    """ManimGL `anim(time_span=(start, end))` inside a play of length `run_time`:
        self.play(Create(axes), time_span(FadeIn(dots), 1, 2, 3), run_time=3)
    Give every animation in that play the same run_time (time_span sets this one's)."""
    if not 0 <= start < end <= run_time:
        raise ValueError(f"time_span needs 0 <= start < end <= run_time, got ({start}, {end}) in {run_time}")
    base = anim.rate_func
    anim.set_rate_func(squish_rate_func(base, start / run_time, end / run_time))
    anim.set_run_time(run_time)
    return anim


def lagged(anim_cls, mobs: Iterable[Mobject], lag_ratio: float = 0.1, **kwargs) -> LaggedStart:
    """ManimGL LaggedStartMap with 3b1b's favourite lag (0.1). kwargs go to each animation
    (e.g. shift=0.25*UP) except run_time, which goes to the group."""
    run_time = kwargs.pop("run_time", None)
    group_kwargs = {"run_time": run_time} if run_time else {}
    return LaggedStart(*[anim_cls(m, **kwargs) for m in mobs], lag_ratio=lag_ratio, **group_kwargs)


def _parts_by_tex(mob: VMobject) -> dict[str, VGroup]:
    groups: dict[str, VGroup] = {}
    for p in mob.submobjects:
        groups.setdefault(getattr(p, "tex_string", None) or str(id(p)), VGroup()).add(p)
    return groups


class TransformTex(AnimationGroup):
    """Rearrange an equation (ManimGL TransformMatchingTex/Strings, rebuilt for CE).

    Pieces with equal tex strings glide to their new spots; `key_map={"=": r"\\approx"}` morphs
    pieces whose strings differ; everything else fades out/in. Build both sides with tex(...)
    or multi-arg MathTex so the pieces you care about are separate submobjects.

    Use this instead of CE's TransformMatchingTex(key_map=...), which in 0.22 raises
    "zip() argument 2 is longer than argument 1" whenever mapped pieces differ in glyph count.
    """

    def __init__(self, source: VMobject, target: VMobject, key_map: dict | None = None,
                 run_time: float = 2, path_arc: float = 0, fade_shift=ORIGIN, **kwargs):
        src, tgt = _parts_by_tex(source), _parts_by_tex(target)
        pairs = [(k, k) for k in src if k in tgt]
        for a, b in (key_map or {}).items():
            if a in src and b in tgt and a not in {p[0] for p in pairs} and b not in {p[1] for p in pairs}:
                pairs.append((a, b))
        used_s, used_t = {a for a, _ in pairs}, {b for _, b in pairs}
        anims = [Transform(src[a], tgt[b], path_arc=path_arc) for a, b in pairs]
        anims += [FadeOut(g, shift=fade_shift) for k, g in src.items() if k not in used_s]
        anims += [FadeIn(g, shift=fade_shift) for k, g in tgt.items() if k not in used_t]
        self._source, self._target = source, target
        # Scene.play adds these temporary groups to the scene; remember them to remove later.
        self._temp_groups = [*src.values(), *tgt.values()]
        super().__init__(*anims, run_time=run_time, **kwargs)

    def clean_up_from_scene(self, scene: Scene) -> None:
        super().clean_up_from_scene(scene)
        scene.remove(self._source, *self._temp_groups)
        scene.add(self._target)


def FromCopy(source: Mobject, target: Mobject, path_arc: float = -PI / 4, run_time: float = 1.5,
             **kwargs) -> Animation:
    """3b1b's most-used move: a copy flies from where a term *comes from* to where it lands,
    on a gentle arc, leaving the original in place."""
    return TransformFromCopy(source, target, path_arc=path_arc, run_time=run_time, **kwargs)


# ---------------------------------------------------------------------------
# 3D
# ---------------------------------------------------------------------------
def gl_orientation(theta_deg: float = 0, phi_deg: float = 0, gamma_deg: float = 0,
                   center=ORIGIN, height: float = 8.0) -> dict:
    """Translate ManimGL `frame.reorient(theta, phi, gamma, center, height)` into kwargs for
    ThreeDScene.set_camera_orientation / move_camera. Verify visually: conventions are close
    but CE's theta is offset by -90 degrees."""
    return dict(theta=(theta_deg - 90) * DEGREES, phi=phi_deg * DEGREES, gamma=gamma_deg * DEGREES,
                frame_center=np.array(center, dtype=float), zoom=8.0 / height)


# ---------------------------------------------------------------------------
# Captions & narration (render.py --voice speaks voiceover() paragraphs and caption() lines)
# ---------------------------------------------------------------------------
def reading_time(s: str, wpm: float = 180, minimum: float = 1.2) -> float:
    """Seconds a viewer needs to read `s` once, plus a breath. Silent videos live or die on this."""
    return max(minimum, len(s.split()) / wpm * 60 + 0.6)


# Set by render.py: TBB_CAPTIONS=0 hides drawn captions (--no-captions, or --voice without
# --captions); TBB_AUDIO picks the narration pass; TBB_VOICE* name the TTS voice.
CAPTIONS = os.environ.get("TBB_CAPTIONS", "1").strip().lower() not in {"0", "false", "no", "off"}
AUDIO_MODE = os.environ.get("TBB_AUDIO", "off").strip().lower()   # off | collect | on
if AUDIO_MODE not in {"off", "collect", "on"}:
    raise ValueError(f"TBB_AUDIO must be off, collect or on (got {AUDIO_MODE!r})")
VOICE = os.environ.get("TBB_VOICE", "am_michael")
try:
    VOICE_SPEED = float(os.environ.get("TBB_VOICE_SPEED", "1.0"))
except ValueError:
    raise ValueError(f"TBB_VOICE_SPEED must be a number like 1.0 (got {os.environ['TBB_VOICE_SPEED']!r})") from None
VOICE_DIR = Path(os.environ.get("TBB_VOICE_DIR", "media/voice"))
LINES_DIR = Path(os.environ.get("TBB_LINES_DIR", VOICE_DIR / "lines"))  # render.py: per video file
LINE_GAP = 0.35          # breath after each spoken line before the next may start
SPEECH_LEAD = 0.25       # speech starts this long after the caption swap begins

_GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "Δ": "delta", "ε": "epsilon",
          "θ": "theta", "λ": "lambda", "μ": "mu", "π": "pi", "ρ": "rho", "σ": "sigma",
          "φ": "phi", "ω": "omega", "∇": "del", "τ": "tau", "η": "eta", "ϕ": "phi", "ψ": "psi",
          "χ": "chi", "ξ": "xi", "κ": "kappa", "ν": "nu", "ζ": "zeta", "Ω": "omega", "Φ": "phi"}
_SPOKEN = [("->", " goes to "), ("=>", " implies "), ("<=", " is at most "), (">=", " is at least "),
           ("!=", " is not equal to "), ("==", " equals "),   # ASCII digraphs before their single chars
           ("≈", " is approximately "), ("≠", " is not equal to "), ("≤", " is at most "),
           ("≥", " is at least "), ("→", " goes to "), ("⇒", " implies "), ("×", " times "),
           ("·", " times "), ("−", " minus "), ("±", " plus or minus "), ("∞", " infinity "),
           ("Σ", " the sum "), ("∑", " the sum "), ("∏", " the product "), ("∫", " the integral of "),
           ("∂", " partial "), ("∈", " in "), ("≻", " is preferred to "), ("∝", " is proportional to "),
           ("√", " the square root of "), ("…", "..."), ("e.g.", "for example"), ("i.e.", "that is"),
           ("%", " percent"), ("&", " and "), ("=", " equals "), ("<", " is less than "),
           (">", " is greater than "), ("+", " plus ")]
_SUPERSCRIPT_WORDS = {"²": " squared", "³": " cubed"}
_SYMBOL_WORDS = {"°": " degrees", "½": " one half", "⅓": " one third", "⅔": " two thirds", "¼": " one quarter",
                 "¾": " three quarters", "↔": " if and only if ", "⇔": " if and only if ", "←": " left arrow "}
_TYPOGRAPHY = {"’": "'", "‘": "'", "“": '"', "”": '"', "—": ", ", "–": ", "}
_COMBINING = {"\u0302": " hat", "\u0303": " tilde", "\u0304": " bar", "\u0305": " bar",
              "\u0307": " dot", "\u0308": " double dot", "\u20d7": " vector"}
_OR_PAIRS = {("and", "or"), ("either", "or"), ("input", "output"), ("yes", "no"), ("true", "false"),
             ("on", "off"), ("read", "write"), ("he", "she"), ("him", "her"), ("his", "her"), ("black", "white")}


_MARKUP = re.compile(r"\[([^\]]+)\]\((/[^)]*/)\)")  # misaki phoneme override: [word](/phonemes/)


def strip_markup(s: str) -> str:
    """Display form of narration text: `[Kokoro](/kˈOkəɹO/)` -> `Kokoro`."""
    return _MARKUP.sub(r"\1", s)


def _is_letter(c: str) -> bool:
    return c.isalpha() and not unicodedata.decomposition(c).startswith(("<sub>", "<super>"))


def _spell_accents(s: str) -> str:
    """Sub/superscripts become separate letters ("yᵢ" -> "y i"). An accent on a lone math letter is
    read ("x̂" -> "x hat", "Â" -> "A hat"); inside a word it is dropped ("Möbius" -> "Mobius")."""
    out = []
    for i, raw in enumerate(s):
        if unicodedata.decomposition(raw).startswith(("<sub>", "<super>")):
            out.append(" " + unicodedata.normalize("NFKD", raw) + " ")
            continue
        base_at = i - 1 if unicodedata.combining(raw) else i  # "x" + U+0302 vs precomposed "x̂"
        lone = not (base_at > 0 and _is_letter(s[base_at - 1])) and not (i + 1 < len(s) and _is_letter(s[i + 1]))
        for ch in unicodedata.normalize("NFKD", raw):
            if not unicodedata.combining(ch):
                out.append(ch)
            elif ch in _COMBINING and lone:
                out.append(_COMBINING[ch] + " ")
    return "".join(out)


def speakable(s: str) -> str:
    """Caption text -> what the TTS should say. Handles common math symbols, Greek, sub/super-
    scripts and accents ("Âᵢ" -> "A hat i", "|y|" -> "the length of y", "π*" -> "pi star"),
    and ordinary prose (curly quotes, dashes, URLs, HTML tags, accented words).
    For real formulas pass `say=` to caption() ("e to the r over beta"): no rule set reads math
    the way a person would. Anything still unspeakable is dropped rather than spelled out."""
    keep = []  # phoneme overrides pass through untouched (the IPA must survive the ASCII filter)

    def hold(m):
        keep.append(m.group(0))
        return f" TBBMARKUP{len(keep) - 1}Q "

    s = _MARKUP.sub(hold, s)
    # Prose first: typography, links and markup are not math.
    s = re.sub(r"(?<=\d)\s*[–—]\s*(?=\d)", " to ", s)              # "2–4 minutes"
    for a, b in _TYPOGRAPHY.items():
        s = s.replace(a, b)
    s = re.sub(r"\bhttps?://(?:www\.)?([^/\s]+)\S*", lambda m: " " + m[1].replace(".", " dot ") + " ", s)
    for tag in set(re.findall(r"</([A-Za-z][\w-]*)>", s)):              # paired tags: <b>bold</b>
        s = re.sub(rf"</?{tag}\b[^>]*>", " ", s)
    s = re.sub(r"<([A-Za-z][\w-]*)\s*/>", " ", s)                       # <br/>
    s = re.sub(r"<([A-Za-z][\w-]*)>", r" \1 ", s)                       # tokens: "<eos>" -> "eos"
    s = s.replace("<=>", " if and only if ").replace("<-", " left arrow ")
    for table in (_SUPERSCRIPT_WORDS, _SYMBOL_WORDS):
        for a, b in table.items():
            s = s.replace(a, b)
    s = re.sub(r"(?:\bthe\s+)?\|([^|]{1,12})\|", r" the length of \1 ", s)
    s = re.sub(r"(?<=[\w)])\s*\|\s*(?=[\w(])", " given ", s)          # p(x|y)
    s = re.sub(r"(\w)\*(?=\w)", r"\1 times ", s)                     # a*b
    s = re.sub(r"(\w)\*", r"\1 star", s)                              # π*, x*
    s = re.sub(r"\b([A-Za-z]+)/([A-Za-z]+)\b",                       # input/output; distance/time
               lambda m: (f"{m[1]} or" if m[2].lower() == "or" else f"{m[1]} or {m[2]}")
               if (m[1].lower(), m[2].lower()) in _OR_PAIRS else m[0], s)
    s = re.sub(r"\b(\d+)/\1\b", r"\1 \1", s)                          # 50/50
    s = re.sub(r"(?<=[\w)])\s*/\s*(?=[\w(])", " over ", s)           # dy/dx, x/2, (a+b)/2
    s = re.sub(r"(?<=\w)\^2(?!\d)", " squared", s)
    s = re.sub(r"(?<=\w)\^3(?!\d)", " cubed", s)
    s = re.sub(r"(?<=\w)\^", " to the ", s)
    for a, b in _SPOKEN:
        s = s.replace(a, b)
    for a, b in _GREEK.items():
        s = s.replace(a, f" {b} ")
    s = _spell_accents(s)
    s = "".join(ch if ch.isascii() else " " for ch in s)   # never let the engine spell code points
    s = s.replace("_", " ").replace("|", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\(\s+", "(", re.sub(r"\s+([.,:;?!)])", r"\1", s))
    return re.sub(r"TBBMARKUP(\d+)Q", lambda m: keep[int(m.group(1))], s).strip()


TTS_REVISION = 2  # bump when narrate.py changes how text becomes audio (forces re-synthesis)


def narration_key(say: str) -> str:
    tag = f"kokoro|r{TTS_REVISION}|{VOICE}|{VOICE_SPEED}|{say}"
    return hashlib.sha1(tag.encode()).hexdigest()[:16]


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def _record_line(scene: Scene, key: str, sentences: list[str]) -> None:
    """Collect pass: append one narration line for narrate.py to synthesise."""
    path = LINES_DIR / f"{type(scene).__name__}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "say": " ".join(sentences), "sentences": sentences, "voice": VOICE,
                            "speed": VOICE_SPEED, "scene": type(scene).__name__}) + "\n")


CAPTION_FONT_SIZE = 34
CAPTION_MAX_WIDTH = 12.0
CAPTION_EDGE_BUFF = 0.45     # gap between a caption and the bottom of the frame
CAPTION_BACKSTROKE = 5       # black stroke behind caption glyphs
CAPTION_FADE = 0.18          # seconds a voiceover caption line takes to fade in or out
CAPTION_SWAP_SPLIT = 0.45    # caption(): old line clears in this fraction of run_time, then the new one arrives
SUBTITLE_TRIM, SUBTITLE_MIN = 0.05, 0.3  # each subtitle ends this early, and lasts at least this long


def _caption_mob(s: str, color=GREY_A, t2c: dict | None = None) -> Mobject:
    m = _fit_width(text(strip_markup(s), font_size=CAPTION_FONT_SIZE, color=color, t2c=t2c), CAPTION_MAX_WIDTH)
    m.to_edge(DOWN, buff=CAPTION_EDGE_BUFF)
    backstroke(m, stroke_width=CAPTION_BACKSTROKE)
    m.set_z_index(100)
    return m


WORDS_PER_SECOND = 2.9     # Kokoro am_michael at speed 1.0 (~175 wpm measured), for estimates without audio
SENTENCE_PAUSE = 0.3
# A sentence ends at . ! ? or … plus any closing quotes/brackets, before a space and a capital,
# digit or opening quote/bracket. Kept in sync with style_lint.py (which can't import manim).
_SENTENCE_END = re.compile(r"[.!?…]+[\"”’)\]]*(?=\s+[\"“(\[A-Z0-9])")
_ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "prof", "st", "vs", "e.g", "i.e", "cf", "fig", "eq", "approx"}
_CUE_WORD = re.compile(r"[a-z0-9']+")


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


class Voiceover:
    """A narrated paragraph, timed by its own speech. Use via `with self.voiceover(paragraph) as v:`.

    v.wait_until(2)              wait until sentence 2 starts (0-based)
    v.wait_until("reward model") wait until that phrase is spoken (matched on spoken words)
    v.until(cue)                 seconds from now until a cue, for run_time= (>= 0.1)
    v.span(i)                    length of sentence i in seconds
    v.remaining                  seconds until the speech ends
    Leaving the block waits for the speech to finish. Without --voice, timings are estimated at
    speaking pace and the sentences show as captions, so the same scene also renders silent.
    """

    def __init__(self, scene: "Scene", paragraph: str, captions: Sequence[str] | None = None,
                 show: bool = True, t2c: dict | None = None):
        self.scene = scene
        self.sentences = split_sentences(paragraph)
        if not self.sentences:
            raise ValueError("voiceover() needs at least one sentence")
        self.display = list(captions) if captions else self.sentences
        if len(self.display) != len(self.sentences):
            raise ValueError("captions= must have one entry per sentence")
        self.spoken = [speakable(x) for x in self.sentences]
        self.key = narration_key(" ".join(self.spoken))
        self.show = CAPTIONS and show  # render.py turns CAPTIONS off for --no-captions / --voice
        self.t2c = t2c
        self.audio = None
        self._load_timing()

    # -- timing ---------------------------------------------------------------------------
    def _load_timing(self):
        wav = VOICE_DIR / "audio" / f"{self.key}.wav"
        meta = wav.with_suffix(".json")
        if AUDIO_MODE == "on" and wav.exists() and meta.exists():
            t = json.loads(meta.read_text(encoding="utf-8"))
            self.audio = wav.resolve()
            self.duration = t["duration"]
            self.spans = [(x["start"], x["end"]) for x in t["sentences"]]
            # A Kokoro token can hold several cue words ("fine-tune", "S-shaped"): split it the same
            # way cues and estimates are split, sharing the token's time span between its parts.
            self.words = []
            for w in t["words"]:
                parts = _CUE_WORD.findall(w["text"].lower())
                for k, part in enumerate(parts):
                    a = w["start"] + (w["end"] - w["start"]) * k / len(parts)
                    b = w["start"] + (w["end"] - w["start"]) * (k + 1) / len(parts)
                    self.words.append((part, a, b))
            return
        if AUDIO_MODE == "on":
            logger.warning(f"tbb voice: no audio for {self.sentences[0][:50]!r} (run render.py --voice); estimating")
        self.spans, self.words, t = [], [], 0.0
        for sp in self.spoken:
            ws = _CUE_WORD.findall(strip_markup(sp).lower())
            d = max(len(ws), 1) / WORDS_PER_SECOND
            for k, w in enumerate(ws):
                self.words.append((w, t + d * k / len(ws), t + d * (k + 1) / len(ws)))
            self.spans.append((t, t + d))
            t += d + SENTENCE_PAUSE
        self.duration = t - SENTENCE_PAUSE

    def _offset(self, cue) -> float:
        """Seconds into the speech for a sentence index or a phrase. A phrase spoken more than
        once resolves to its next occurrence that hasn't passed yet."""
        if isinstance(cue, bool):
            raise TypeError("a cue is a sentence index (int) or a phrase (str), not a bool")
        if isinstance(cue, numbers.Integral):
            cue = int(cue)
            if not -len(self.spans) <= cue < len(self.spans):
                raise IndexError(f"voiceover has {len(self.spans)} sentence(s); no sentence {cue}")
            return self.spans[cue][0]
        target = _CUE_WORD.findall(speakable(str(cue)).lower())
        if not target:
            raise ValueError(f"cue {cue!r} has no words to match")
        heard = [w for w, _, _ in self.words]
        hits = [self.words[i][1] for i in range(len(heard) - len(target) + 1) if heard[i:i + len(target)] == target]
        if not hits:
            raise ValueError(f"cue {cue!r} not found in narration: {' '.join(self.spoken)[:120]!r}")
        now = self.scene.time - getattr(self, "t0", self.scene.time)
        return next((t for t in hits if t >= now - 1e-3), hits[-1])

    def at(self, cue) -> float:
        return self.t0 + self._offset(cue)

    def until(self, cue, minimum: float = 0.1) -> float:
        return max(self.at(cue) - self.scene.time, minimum)

    def span(self, i: int) -> float:
        if not -len(self.spans) <= i < len(self.spans):
            raise IndexError(f"voiceover has {len(self.spans)} sentence(s); no sentence {i}")
        a, b = self.spans[i]
        return max(b - a, 0.1)

    @property
    def remaining(self) -> float:
        return max(self.t0 + self.duration - self.scene.time, 0.0)

    def wait_until(self, cue, offset: float = 0.0):
        dt = self.at(cue) + offset - self.scene.time
        if dt > 1e-3:
            self.scene.wait(dt)

    # -- context ----------------------------------------------------------------------------
    def __enter__(self):
        sc = self.scene
        sc._wait_for_voice()
        if sc._caption is not None:  # a lingering caption() line gives way to the narration
            sc.play(FadeOut(sc._caption), run_time=0.3)
            sc._caption = None
        self.t0 = sc.time
        if AUDIO_MODE == "collect":
            _record_line(sc, self.key, self.spoken)
        if self.audio is not None:
            sc.add_sound(str(self.audio))
        starts = [a for a, _ in self.spans]
        for i, (a, b) in enumerate(self.spans):
            end = starts[i + 1] if i + 1 < len(starts) else b
            sc._subtitles.append((self.t0 + a, self.t0 + max(end - SUBTITLE_TRIM, a + SUBTITLE_MIN),
                                  strip_markup(self.display[i])))
        self._group = None
        if self.show:
            self._group = self._caption_group()
            sc._pin_caption(self._group)
            sc.add(self._group)
            sc._caption = self._group
        return self

    def __exit__(self, exc_type, exc, tb):
        sc = self.scene
        if exc_type is None:
            sc._voice_until = self.t0 + self.duration + LINE_GAP
            sc._wait_for_voice()
        if self._group is not None:  # also on an exception: no orphan caption or updater is left
            self._group.clear_updaters()
            sc._drop_caption(self._group)
        return False

    def _caption_group(self) -> VGroup:
        """The paragraph's caption lines, each fading in and out over its sentence. Only lines
        that are visible are in the group: Cairo would otherwise draw every sentence's glyphs, at
        opacity 0, on every frame. Timing follows scene time, the clock the audio is placed on."""
        lines = [_caption_mob(d, t2c=self.t2c) for d in self.display]
        starts = [a for a, _ in self.spans]
        # The last line fades out before __exit__ removes the group (at duration + LINE_GAP).
        windows = [(a, (starts[i + 1] if i + 1 < len(starts) else self.duration + LINE_GAP - 0.02))
                   for i, a in enumerate(starts)]
        alphas: list[float | None] = [None] * len(lines)
        # The container must sort with its lines (z 100): ManimCE redraws every frame everything
        # drawn after the first object with an updater, so at z 0 it would drag the content along.
        group = VGroup()
        group.z_index = lines[0].z_index

        def alphas_at(scene_time: float) -> tuple[float, ...]:
            t = scene_time - self.t0
            return tuple(float(np.clip(min((t - a) / CAPTION_FADE, (b - t) / CAPTION_FADE), 0, 1))
                         for a, b in windows)

        def update(g, dt):  # time-based on purpose: a wait must keep rendering through the fades
            shown = []
            for i, (m, alpha) in enumerate(zip(lines, alphas_at(self.scene.time))):
                if alpha != alphas[i]:  # restyling glyphs is costly: only when the alpha changes
                    alphas[i] = alpha
                    m.set_fill(opacity=alpha)
                    m.set_stroke(opacity=0)
                    m.set_stroke(BLACK, width=CAPTION_BACKSTROKE * getattr(g, "_tbb_zoom", 1.0),
                                 opacity=alpha, background=True)
                if alpha > 0:
                    shown.append(m)
            if shown != g.submobjects:
                g.submobjects = shown

        update(group, 0)
        group.add_updater(update)
        group._tbb_lines = lines  # every line, for the 3D camera's fixed-in-frame set
        group._tbb_alphas_at = alphas_at  # lets wait() freeze the frames between caption changes
        return group


CAPTION_SAFE_Y = -2.75   # keep regular content above this line in scenes that use captions
EDGE_MARGIN = 0.1        # the audit flags content closer than this to the frame edge


def _bbox(m: Mobject):
    """(x0, x1, y0, y1) of every point in m's family, or None if it has none."""
    arrays = [sm.points for sm in m.get_family() if len(getattr(sm, "points", ()))]
    if not arrays:
        return None
    pts = np.concatenate(arrays)
    return pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()


def _describe(m: Mobject, inside: Callable[[tuple], bool] | None = None) -> str:
    """Human name for a mobject (or, for groups, the first descendant that fails `inside`)."""
    target = m
    if inside is not None and type(m).__name__ in {"Group", "VGroup"}:
        for sm in m.get_family():
            if sm is m or type(sm).__name__ in {"Group", "VGroup"}:
                continue
            b = _bbox(sm)
            if b is not None and not inside(b):
                target = sm
                break
    name = type(target).__name__
    for owner in [target] + [a for a in m.get_family() if target in a.get_family()][::-1]:
        txt = getattr(owner, "tex_string", None) or getattr(owner, "text", None) or getattr(owner, "original_text", None)
        if isinstance(owner, DecimalNumber):
            txt = f"{owner.get_value():g}"
        if txt:
            txt = str(txt).strip().replace("\n", " ")
            return f"{type(owner).__name__} {txt[:40]!r}"
    return name


class _TbbMixin:
    audit_layout = True        # warn about off-frame mobjects and caption collisions after each play
    _caption: Mobject | None = None     # the caption or voiceover lines on screen now
    _audit_seen: set | None = None      # warnings already given (each is reported once)
    _voice_until: float = 0.0           # scene time the current speech (plus a breath) ends
    _subtitles: list | None = None      # (start, end, text) cues for the .srt

    def play(self, *args, **kwargs):
        super().play(*args, **kwargs)
        if self.audit_layout and not isinstance(self, ThreeDScene):
            self._audit()

    def wait(self, duration: float = DEFAULT_WAIT_TIME, stop_condition=None, frozen_frame=None):
        """Scene.wait, but a wait under voiceover captions renders each stretch where the captions
        don't change as one frozen frame. Their fade updater would otherwise make ManimCE redraw
        every frame of every wait. Frame counts and times are exactly those of a single wait."""
        segments = self._caption_wait_segments(duration) if stop_condition is None and frozen_frame is None else None
        if segments is None:
            return super().wait(duration, stop_condition, frozen_frame)
        dt = 1 / config.frame_rate
        for frames, frozen in segments:
            if frozen:
                # The frozen frame shows everything as of now: the caption, and anything an
                # updater would have moved on the first frame (a wait under captions used to run them).
                self.update_mobjects(0)
                super().wait((frames + 1e-6) * dt, frozen_frame=True)  # int() of it is `frames`
            else:  # arange() gives `frames`; exactly dt for one frame (less would warn "too short")
                super().wait(dt if frames == 1 else (frames - 1e-6) * dt, frozen_frame=False)

    def _caption_wait_segments(self, duration: float) -> list[tuple[int, bool]] | None:
        """[(frames, frozen), ...] for a wait under voiceover captions, or None to wait normally:
        no voiceover caption, nothing to freeze, animations being skipped (-s, -n, sections, whose
        play counts must not change), or something else on screen that changes over time."""
        timeline = getattr(self._caption, "_tbb_alphas_at", None)
        if timeline is None or self.renderer.skip_animations or config.from_animation_number > 0 \
                or config.upto_animation_number != float("inf") or self.updaters or self.always_update_mobjects:
            return None
        if any(m.has_time_based_updater() for m in self.get_mobject_family_members()
               if m is not self._caption):
            return None
        dt = 1 / config.frame_rate
        n = len(np.arange(0, duration, dt))  # the frames one ordinary wait would render
        t0 = self.time
        states = [timeline(t0 + j * dt) for j in range(n)]
        runs: list[list] = []  # [frames, state]
        for s in states:
            if runs and runs[-1][1] == s:
                runs[-1][0] += 1
            else:
                runs.append([1, s])
        segments: list[tuple[int, bool]] = []
        for frames, _ in runs:
            frozen = frames >= 3  # shorter runs (fades) render normally
            if segments and not frozen and not segments[-1][1]:
                segments[-1] = (segments[-1][0] + frames, False)
            else:
                segments.append((frames, frozen))
        return segments if any(f for _, f in segments) else None

    def _audit(self):
        """Warn (once each) about content touching the frame edge or colliding with the caption."""
        if self._audit_seen is None:
            self._audit_seen = set()
        frame = getattr(self.camera, "frame", None)
        if frame is not None:  # MovingCameraScene: audit against the current camera frame
            view = (*frame.get_center()[:2], frame.width / 2, frame.height / 2)
        else:
            view = (0.0, 0.0, config.frame_width / 2, config.frame_height / 2)
        cap = self._caption
        # A voiceover's lines come and go; audit against all of them (with animations skipped,
        # as in render.py --check, often none is on screen when the audit runs).
        lines = getattr(cap, "_tbb_lines", None)
        cap_box = _bbox(VGroup(*lines) if lines else cap) if cap is not None and cap in self.mobjects else None
        for m in self.mobjects:
            if m is cap or m is frame or isinstance(m, (TracedPath, ValueTracker)):
                continue
            box = _bbox(m)
            if box is not None:
                self._audit_edges(m, box, view)
                if cap_box is not None:
                    self._audit_caption(m, box, cap, cap_box)

    def _audit_edges(self, m: Mobject, box, view) -> None:
        x0, x1, y0, y1 = box
        cx, cy, hw, hh = view
        margin = EDGE_MARGIN
        spans_frame = (x1 - x0) >= 2 * hw - 0.2 or (y1 - y0) >= 2 * hh - 0.2  # planes, backdrops
        on_screen = x1 > cx - hw and x0 < cx + hw and y1 > cy - hh and y0 < cy + hh
        crosses = (x0 < cx - hw + margin or x1 > cx + hw - margin or
                   y0 < cy - hh + margin or y1 > cy + hh - margin)
        key = ("off", id(m))
        if crosses and on_screen and not spans_frame and key not in self._audit_seen:
            self._audit_seen.add(key)
            name = _describe(m, lambda b: b[0] >= cx - hw + margin and b[1] <= cx + hw - margin
                             and b[2] >= cy - hh + margin and b[3] <= cy + hh - margin)
            logger.warning(f"tbb layout: {name} touches or crosses the frame edge in "
                           f"{type(self).__name__} (x {x0:.2f}..{x1:.2f}, y {y0:.2f}..{y1:.2f}; "
                           f"frame is +-{hw:.2f} x +-{hh:.2f})")

    def _audit_caption(self, m: Mobject, box, cap: Mobject, cap_box) -> None:
        x0, x1, y0, y1 = box
        overlap = x0 < cap_box[1] and x1 > cap_box[0] and y0 < cap_box[3] + 0.1 and y1 > cap_box[2]
        key = ("cap", id(m), id(cap))
        if not overlap or key in self._audit_seen:
            return
        visible = any(sm.get_fill_opacity() > 0.05 or sm.get_stroke_opacity() > 0.05
                      for sm in m.get_family() if len(getattr(sm, "points", ())))
        if visible:
            self._audit_seen.add(key)
            name = _describe(m, lambda b: b[2] > cap_box[3] + 0.1 or b[1] < cap_box[0] or b[0] > cap_box[1])
            logger.warning(f"tbb layout: {name} collides with the caption in {type(self).__name__} "
                           f"(its bottom y={y0:.2f}; keep content above y={CAPTION_SAFE_Y})")

    def caption(self, s: str | None, hold: float | None = None, color=GREY_A, run_time: float = 0.8,
                t2c: dict | None = None, added_anims: Sequence[Animation] = (), say: str | None = None,
                show: bool = True):
        """One narration beat: swap the lower-third caption to `s` (None clears it) and hold.

        Silent render: holds for reading time. With `render.py --voice`, the line is also spoken
        (`say=` overrides the spoken text, e.g. say="e to the r over beta" for "e^(r/β)") and the
        hold becomes the speech length; captions then move to a subtitle track unless --captions.
        hold=0 keeps animating while the line plays; the next caption() waits for speech to end,
        so lines never overlap. `added_anims` play during the swap. show=False speaks or holds
        without drawing a caption.
        """
        spoken = speakable(say if say is not None else s) if (s or say) else None
        self._wait_for_voice()
        added = [_prepare_animation(a) for a in added_anims]  # accepts .animate builders too
        anims = list(added)
        display = CAPTIONS and show
        old = self._caption
        new = None
        if old is not None:
            # Old line clears in the first half, new line arrives in the second: never two
            # captions stacked on top of each other mid-swap.
            anims.append(time_span(FadeOut(old, shift=0.15 * UP), 0, CAPTION_SWAP_SPLIT * run_time, run_time))
        if s and display:
            new = _caption_mob(s, color=color, t2c=t2c)
            self._pin_caption(new)
            fade_in = FadeIn(new, shift=0.15 * UP)
            anims.append(time_span(fade_in, CAPTION_SWAP_SPLIT * run_time, run_time, run_time) if old is not None
                         else fade_in.set_run_time(run_time))

        clip = self._voice_clip(spoken) if spoken else None
        start = self.time + (SPEECH_LEAD if anims else 0)
        if clip:
            self.add_sound(str(clip[0]), time_offset=start - self.time)
        if anims:
            self.play(*anims, run_time=max([run_time] + [a.get_run_time() for a in added]))
        if old is not None:
            self._drop_caption(old)
        self._caption = new

        shown = strip_markup(s) if s else None  # subtitles show the word, not phoneme markup
        if clip:
            self._voice_until = start + clip[1] + LINE_GAP
            if shown:
                self._subtitles.append((start, start + clip[1], shown))
            wait = (self._voice_until - self.time) if hold is None else hold
        else:
            # Silent: hold for reading time, also for a spoken-only line (caption(None, say=...)),
            # so the silent and narrated timelines match.
            if shown:
                self._subtitles.append((start, start + reading_time(shown), shown))
            words = shown or (say if spoken else None)
            wait = reading_time(words) if (words and hold is None) else (hold or 0)
        if wait > 1e-3:
            self.wait(wait)
        return new

    def voiceover(self, paragraph: str, captions: Sequence[str] | None = None, show: bool = True,
                  t2c: dict | None = None) -> Voiceover:
        """Narrate a paragraph and time the animations inside the block to it:

            with self.voiceover(\"\"\"Let's say a person looks at two answers and tells you which
                                   one they prefer. What you want is a single number for each.\"\"\") as v:
                self.play(Write(question))
                v.wait_until("single number")
                self.play(Create(bar), run_time=v.span(1))

        Write it as spoken prose following references/narration-style.md, not caption fragments.
        `captions=` gives one on-screen line per sentence when the spoken form differs (math);
        `show=False` draws no captions; `t2c=` colors words in them, as in caption()."""
        return Voiceover(self, paragraph, captions=captions, show=show, t2c=t2c)

    # -- narration plumbing ---------------------------------------------------------------
    def _drop_caption(self, m: Mobject) -> None:
        """Take a caption off screen (and out of the 3D camera's fixed-in-frame set)."""
        self.remove(m)
        if isinstance(self, ThreeDScene):
            for part in getattr(m, "_tbb_lines", [m]):
                self.camera.fixed_in_frame_mobjects.difference_update(part.get_family())
        if self._caption is m:
            self._caption = None

    def _pin_caption(self, m: Mobject) -> None:
        """Keep a caption in the lower third of what the camera shows. Not added to the scene.
        A voiceover group pins all its lines, including those not shown yet."""
        parts = getattr(m, "_tbb_lines", None)
        if isinstance(self, ThreeDScene):
            self.add_fixed_in_frame_mobjects(*(parts or [m]))
            self.remove(*(parts or [m]))
            return
        frame = getattr(self.camera, "frame", None)
        if frame is None:
            return
        whole = VGroup(*parts) if parts else m
        home, height = whole.get_center().copy(), whole.height  # placement in the default full frame

        def follow(mob):
            k = frame.width / config.frame_width
            if k != getattr(mob, "_tbb_zoom", 1.0):
                whole.scale_to_fit_height(height * k)
                # Stroke widths are in scene units, so a zoomed-in camera thickens them: keep the
                # backstroke's on-screen width, or it eats into the letters.
                for glyph in whole.family_members_with_points():
                    glyph.set_stroke(width=CAPTION_BACKSTROKE * k, background=True)
                mob._tbb_zoom = k
            whole.move_to(frame.get_center() + home * k)

        follow(m)
        m.add_updater(follow)

    def setup(self):
        super().setup()
        self._subtitles = []
        self._voice_until = 0.0

    def _voice_clip(self, spoken: str):
        key = narration_key(spoken)
        if AUDIO_MODE == "collect":
            _record_line(self, key, [spoken])
            return None
        if AUDIO_MODE != "on":
            return None
        wav = VOICE_DIR / "audio" / f"{key}.wav"
        if not wav.exists():
            logger.warning(f"tbb voice: no audio for {spoken[:50]!r} (run render.py --voice); estimating")
            return None
        return wav.resolve(), _wav_duration(wav)

    def _wait_for_voice(self):
        remaining = self._voice_until - self.time
        if remaining > 1e-3:
            self.wait(remaining)

    def tear_down(self):
        self._wait_for_voice()  # never cut the last line off at the end of a scene
        subs_dir = os.environ.get("TBB_SUBS_DIR")
        if subs_dir and self._subtitles:
            out = Path(subs_dir) / f"{type(self).__name__}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(self._subtitles), encoding="utf-8")
        super().tear_down()

    def clear_except(self, *keep: Mobject, run_time: float = 1, shift=None):
        """Fade out everything except `keep` — the "keeper" transition between beats. A kept
        piece may sit inside a group on screen (clear_except(eq[2])): the rest of the group fades
        and the kept piece stays where it was drawn. The current caption and the camera frame stay;
        clear a caption with caption(None)."""
        keep_ids = _ids_of(keep)
        for always in (self._caption, getattr(self.camera, "frame", None)):
            if always is not None:
                keep_ids |= {id(m) for m in always.get_family()}
        leaving = []
        for m in list(self.mobjects):
            pieces = _split_kept(m, keep_ids)
            if len(pieces) > 1:
                # Split the group in place (same z-order) so its kept pieces stay on screen.
                if m.updaters:
                    logger.warning(f"tbb: clear_except split {_describe(m)}, so its updaters stop; "
                                   "keep the whole group, or put the updaters on its parts")
                i = self.mobjects.index(m)
                self.mobjects[i:i + 1] = [p for p, _ in pieces]
            leaving += [p for p, kept in pieces if not kept]
        if leaving:
            kw = {"shift": shift} if shift is not None else {}
            self.play(*[FadeOut(m, **kw) for m in leaving], run_time=run_time)

    def fade_all(self, run_time: float = 1, shift=None):
        self.clear_except(run_time=run_time, shift=shift)


class TbbScene(_TbbMixin, Scene):
    """Default 2D scene."""


class TbbMovingScene(_TbbMixin, MovingCameraScene):
    """2D scene with a movable camera: self.camera.frame.animate.set(height=4).move_to(x)."""


class Tbb3DScene(_TbbMixin, ThreeDScene):
    """3D scene. HUD text: self.add_fixed_in_frame_mobjects(title)."""


class TitleCard(Scene):
    """Video/section title. Subclass and set class attributes:

        class Opening(TitleCard):
            title_text = "Why e^x is its own derivative"
            subtitle_text = "A visual walkthrough"
    """

    title_text = "Title"
    subtitle_text = ""
    title_color = WHITE
    subtitle_color = GREY_A
    hold = 2.0

    def construct(self):
        t = _fit_width(text(self.title_text, font_size=72, color=self.title_color), config.frame_width - 1)
        group = VGroup(t)
        if self.subtitle_text:
            group.add(text(self.subtitle_text, font_size=36, color=self.subtitle_color))
            group.arrange(DOWN, buff=0.4)
        self.play(Write(t), run_time=1.5)
        if len(group) > 1:
            self.play(FadeIn(group[1], shift=0.2 * UP))
        self.wait(self.hold)
        self.play(FadeOut(group))


class ChapterCard(Scene):
    """"Part N / chapter title" divider (vivek3141's PartScene). Set number, chapter_title, color."""

    number = 1
    chapter_title = "Chapter"
    color = YELLOW
    hold = 1.5

    def construct(self):
        part = text(f"Part {self.number}", font_size=40, color=GREY_A)
        name = _fit_width(text(self.chapter_title, font_size=66, color=self.color), config.frame_width - 1)
        VGroup(part, name).arrange(DOWN, buff=0.35)
        line = underline(name, color=self.color)
        self.play(FadeIn(part, shift=0.2 * DOWN))
        self.play(Write(name), Create(line), run_time=1.5)
        self.wait(self.hold)
        self.play(FadeOut(VGroup(part, name, line), shift=0.3 * UP))


class QuestionCard(Scene):
    """A big question that frames what follows (3b1b's "What is topology?" cards)."""

    question = "Why?"
    color = WHITE
    hold = 2.0

    def construct(self):
        q = title(self.question, font_size=72, color=self.color)
        self.play(FadeIn(q[0], lag_ratio=0.1), Create(q[1]))
        self.wait(self.hold)
        self.play(FadeOut(q))


class QuoteCard(Scene):
    """Opening quote: slow letter fade, then the author in yellow."""

    quote = "The art of doing mathematics consists in finding\nthat special case which contains all the germs of generality."
    author = "David Hilbert"
    hold = 2.0

    def construct(self):
        q = _fit_width(text(self.quote, font_size=40), config.frame_width - 1.5)
        a = text(f"— {self.author}", font_size=36, color=YELLOW)
        VGroup(q, a).arrange(DOWN, buff=0.6)
        a.align_to(q, RIGHT)
        self.play(FadeIn(q, lag_ratio=0.02, run_time=3, rate_func=linear))
        self.play(Write(a, run_time=1.5))
        self.wait(self.hold)
        self.play(FadeOut(VGroup(q, a)))


class EndScreen(Scene):
    """Generic closing card with a 16:9 slot for the next video. Not the 3b1b end screen."""

    message = "Thanks for watching"
    hold = 3.0

    def construct(self):
        msg = text(self.message, font_size=54).to_edge(UP, buff=0.8)
        screen = ScreenRectangle(height=4.2, stroke_color=GREY_B, stroke_width=2).next_to(msg, DOWN, buff=0.6)
        self.play(Write(msg))
        self.play(Create(screen))
        self.wait(self.hold)


# ---------------------------------------------------------------------------
# render.py --check: report every LaTeX error of a scene in one pass
# ---------------------------------------------------------------------------
_TEX_GROUP = re.compile(r"(\\special\{dvisvgm:raw [^}]*\})")


def _install_tex_check(report: Path) -> None:
    """A formula that fails to compile is recorded in `report` (one JSON line: the formula and
    its TeX errors) and typeset as "?" in each of its pieces, so the scene runs on and the next
    error is found too. The pieces keep their dvisvgm groups, so parts()/indexing still work."""
    from manim.mobject.text import tex_mobject
    from manim.utils.tex_file_writing import generate_tex_file
    compile_svg = tex_mobject.tex_to_svg_file

    def checked(expression, environment=None, tex_template=None):
        try:
            return compile_svg(expression, environment, tex_template)
        except ValueError:
            log = generate_tex_file(expression, environment, tex_template or config.tex_template).with_suffix(".log")
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.exists() else []
            errors = [ln.strip() + (" " + lines[i + 1].strip() if i + 1 < len(lines) else "")
                      for i, ln in enumerate(lines) if ln.startswith("!")][:4]
            pieces = [p for p in _TEX_GROUP.split(expression) if not _TEX_GROUP.fullmatch(p)]
            formula = " | ".join(p.strip() for p in pieces if p.strip())
            report.parent.mkdir(parents=True, exist_ok=True)
            with report.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"formula": formula[:400], "errors": errors}) + "\n")
            placeholder = "".join(p if _TEX_GROUP.fullmatch(p) else ("?" if p.strip() else p)
                                  for p in _TEX_GROUP.split(expression))
            try:
                return compile_svg(placeholder, environment, tex_template)
            except ValueError:
                return compile_svg("?", environment, tex_template)

    tex_mobject.tex_to_svg_file = checked


if os.environ.get("TBB_CHECK_FILE"):
    _install_tex_check(Path(os.environ["TBB_CHECK_FILE"]))


# The public API. Other knobs stay reachable as tbb.NAME; change a default on the module
# (`import tbb; tbb.DIM_OPACITY = 0.4`), since rebinding the star-imported copy does nothing.
__all__ = [
    # palette
    "YELLOW", "YELLOW_C", "BLUE_E", "SOFT_YELLOW", "COLORMAP_3B1B", "DEG",
    "A_AQUA", "A_YELLOW", "A_LAVENDER", "A_RED", "A_BLUE", "A_ORANGE", "A_GREEN", "A_PINK",
    "A_GREY", "A_VIOLET", "A_MINT", "A_GOLD",
    "X_COLOR", "Y_COLOR", "Z_COLOR", "HIGHLIGHT", "DIM_OPACITY", "BACKGROUND", "SOFT_BACKGROUND",
    # style
    "apply_style", "tbb_tex_template", "TEXT_FONT", "HAS_TEXT_FONT",
    # text & tex
    "text", "tex", "parts", "title", "label",
    # emphasis
    "backstroke", "underline", "highlight_rect", "FlashAround", "FlashUnder", "pulse_along",
    "glow_dot", "tracing_tail",
    # structure
    "brace_label", "labeled_arrow", "dim", "undim", "focus_on", "speech_bubble",
    # diagrams
    "NeuralNetwork", "ProbabilityBars",
    # math objects
    "tbb_axes", "tbb_plane", "tbb_number_line", "live_number", "tracked_dot", "tangent_line", "ghost",
    # timing & transforms
    "time_span", "lagged", "TransformTex", "FromCopy",
    # 3D
    "gl_orientation",
    # narration
    "speakable", "strip_markup", "split_sentences", "reading_time", "CAPTION_SAFE_Y",
    # scenes
    "TbbScene", "TbbMovingScene", "Tbb3DScene", "TitleCard", "ChapterCard", "QuestionCard",
    "QuoteCard", "EndScreen",
]
