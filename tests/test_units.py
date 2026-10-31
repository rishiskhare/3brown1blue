"""Fast unit tests for the skill's pure logic (no rendering, no TTS).

    python -m unittest discover -s tests          # with the manim venv's python for the tbb tests

Script tests need only the standard library; tbb tests are skipped when manim isn't importable.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "3brown1blue"
sys.path[:0] = [str(SKILL / "scripts"), str(SKILL / "templates")]

import narrate  # noqa: E402
import render  # noqa: E402
import style_lint  # noqa: E402

HAS_MANIM = importlib.util.find_spec("manim") is not None


class TestRender(unittest.TestCase):
    def test_discover_scenes_order_and_SCENES(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.py"
            f.write_text("class B(Scene):\n    def construct(self): pass\nclass _Hidden(Scene):\n    def construct(self): pass\n"
                         "class A(TbbScene):\n    def construct(self): pass\nclass NotAScene: pass\n"
                         "class Builder:\n    def construct(self, scene): pass\n")  # a helper, not a scene
            self.assertEqual(render.discover_scenes(f), ["B", "A"])
            f.write_text('SCENES = ["A", "B"]\n' + f.read_text())
            self.assertEqual(render.discover_scenes(f), ["A", "B"])

    def test_build_srt_offsets_scenes(self):
        with tempfile.TemporaryDirectory() as d:
            subs = Path(d)
            (subs / "One.json").write_text(json.dumps([[0.5, 2.0, "first"]]))
            (subs / "Two.json").write_text(json.dumps([[1.0, 99.0, "second"]]))
            out = subs / "x.srt"
            self.assertTrue(render.build_srt(["One", "Two"], [10.0, 5.0], subs, out))
            text = out.read_text()
            self.assertIn("00:00:00,500 --> 00:00:02,000\nfirst", text)
            self.assertIn("00:00:11,000 --> 00:00:15,000\nsecond", text)  # clipped to scene end

    def test_discover_scenes_includes_card_subclasses_and_inherited_construct(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.py"
            f.write_text("class Opening(TitleCard):\n    title_text = 'x'\n"
                         "class _Base(TbbScene):\n    def construct(self): pass\n"
                         "class Child(_Base):\n    pass\n"
                         "class Helper(TbbScene):\n    pass\n", encoding="utf-8")
            self.assertEqual(render.discover_scenes(f), ["Opening", "Child"])

    def test_concat_list_escapes_quotes(self):
        with tempfile.TemporaryDirectory() as d:
            listing = render.write_concat_list([Path(d) / "it's.mp4"], Path(d) / "l.txt")
            self.assertIn("it'\\''s.mp4'", listing.read_text(encoding="utf-8"))

    def test_find_video_respects_explicit_fps(self):
        with tempfile.TemporaryDirectory() as d:
            clip = Path(d) / "videos" / "v" / "480p15" / "S.mp4"
            clip.parent.mkdir(parents=True)
            clip.write_bytes(b"")
            self.assertEqual(render.find_video(Path(d), "v", "l", "S", None), clip)
            self.assertIsNone(render.find_video(Path(d), "v", "l", "S", 30))  # never a 15 fps clip for --fps 30

    def test_latex_error_summary_reads_this_scenes_log(self):
        with tempfile.TemporaryDirectory() as d:
            tex_dir = Path(d)
            (tex_dir / "a.log").write_text("! Undefined control sequence.\nl.5 x = \\notacommand\n", encoding="utf-8")
            (tex_dir / "a.tex").write_text("\\begin{document}x = \\notacommand{2}\\end{document}", encoding="utf-8")
            out = "ValueError: latex error converting to dvi. See ... the log file: {log_file}"  # what rich shows
            summary = render.latex_error_summary(out, tex_dir, since=0)
            self.assertIn("! Undefined control sequence.", summary)
            self.assertIn("formula", summary)
            self.assertEqual(render.latex_error_summary("NameError: x", tex_dir, since=0), "")

    def test_user_frame_survives_wrapped_paths(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "my video.py"
            f.write_text("a = 1\nself.play(boom)\n", encoding="utf-8")
            out = (f"│ {d}/my vi │\n│ deo.py:2 in construct │\n│ ❱ 2 self.play(boom) │\n"
                   "NameError: name 'boom' is not defined")
            self.assertEqual(render.user_frame(out, f), "at my video.py:2 in construct: self.play(boom)")

    def test_conflicting_flags_are_rejected(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.py"
            f.write_text("class A(Scene):\n    def construct(self): pass\n", encoding="utf-8")
            for flags in (["--check", "--sheet"], ["--stills", "--voice"], ["--concat-only", "--no-concat"],
                          ["--voice", "--captions", "--no-captions"], ["--captions"], ["--fps", "0"], ["-j", "0"]):
                with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        render.parse_args([str(f), *flags])
            args, extra = render.parse_args([str(f), "-q", "h", "--", "-n", "3"])
            self.assertEqual((args.scenes, extra), (["A"], ["-n", "3"]))
            self.assertEqual(args.jobs, 1)  # default: CPU count, but never more than the scenes

    def test_fingerprint_tracks_only_what_a_scene_depends_on(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "v.py"
            base = ("from manim import *\nfrom tbb import *\nK = 1\n\ndef helper():\n    return K\n\n"
                    "class Builder:\n    def construct(self, scene):\n        return 1\n\n"
                    "class _Base(TbbScene):\n    def construct(self): self.x = helper()\n\n"
                    "class A(_Base):\n    @staticmethod\n    def make(scene):\n        return 1\n\n"
                    "class B(TbbScene):\n    def construct(self): self.y = A.make(self)\n\n"
                    "class C(TbbScene):\n    def construct(self): Builder().construct(self)\n\n"
                    "SCENES = ['A', 'B', 'C']\n")
            (root / "tbb.py").write_text("# kit\n", encoding="utf-8")

            def fps(src=None):
                if src is not None:
                    f.write_text(src, encoding="utf-8")
                render._PROJECT_HASH.clear()  # computed once per run; tests change files mid-run
                return tuple(render.source_fingerprint(f, s, (root / "media",)) for s in "ABC")

            a0, b0, c0 = fps(base)
            self.assertEqual(fps(base.replace("self.y = A.make(self)", "self.y = A.make(self) + 1"))[0], a0)
            self.assertEqual(fps(base.replace("self.x = helper()", "self.x = helper()  # a comment")), (a0, b0, c0))
            self.assertEqual(fps(base.replace("SCENES = ['A', 'B', 'C']", "SCENES = ['C', 'B', 'A']")), (a0, b0, c0))
            a, b, c = fps(base.replace("K = 1", "K = 2"))                 # module-level code reaches every scene
            self.assertTrue(a != a0 and b != b0 and c != c0)
            a, b, c = fps(base.replace("return 1\n\nclass B", "return 2\n\nclass B"))  # B calls A.make
            self.assertTrue(a != a0 and b != b0 and c == c0)
            a, b, c = fps(base.replace("return 1\n\nclass _Base", "return 3\n\nclass _Base"))  # helper class
            self.assertTrue(c != c0)
            fps(base)
            (root / "tbb.py").write_text("# kit, edited\n", encoding="utf-8")
            self.assertNotEqual(fps()[0], a0)                             # an imported module, by content
            before = fps()
            (root / "notes_for_another_video.py").write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(fps(), before)                               # a .py nobody imports doesn't count
            (root / "assets").mkdir()
            (root / "assets" / "data.json").write_text("{}", encoding="utf-8")
            self.assertNotEqual(fps(), before)                            # assets in subfolders do
            before = fps()
            for out in (root / "final" / "v_480p15.mp4", root / "media" / "x.png", root / "say.wav"):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"x")
            self.assertEqual(fps(), before)                               # render outputs don't
            cwd = os.getcwd()
            try:
                os.chdir(root / "assets")
                (root / "assets" / "manim.cfg").write_text("[CLI]\nframe_rate = 24\n", encoding="utf-8")
                self.assertNotEqual(fps(), before)                        # manim.cfg in the working directory
            finally:
                os.chdir(cwd)

    def test_finish_clip_leaves_nothing_on_failure(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "g" / "S_s1.5.mp4"
            self.assertFalse(render.finish_clip(Path(d) / "missing.mp4", out, 1.5))
            self.assertEqual(list(out.parent.iterdir()), [])              # no partial or short clip left

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_loudness_gain(self):
        with tempfile.TemporaryDirectory() as d:
            quiet, silent = Path(d) / "quiet.wav", Path(d) / "silent.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                            "-af", "volume=-20dB", str(quiet)], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                            "-t", "3", str(silent)], check=True)
            self.assertEqual(render.loudness_gain(silent), "anull")
            af = render.loudness_gain(quiet)
            self.assertTrue(af.startswith("volume="), af)
            out = subprocess.run(["ffmpeg", "-i", str(quiet), "-af", f"{af},ebur128=peak=true", "-f", "null", "-"],
                                 capture_output=True, text=True).stderr.rsplit("Summary:", 1)[-1]
            loud = float(re.search(r"I:\s+(-?[\d.]+) LUFS", out).group(1))
            peak = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", out).group(1))
            self.assertLessEqual(peak, -1.0)          # the limiter keeps peaks under the ceiling
            self.assertGreater(loud, -20.0)           # and the level came up towards -16 LUFS

    def test_scene_file_syntax_error_is_a_clean_message(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.py"
            f.write_text("class A(Scene)\n    pass\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, r"v\.py:1: "):
                render.discover_scenes(f)

    def test_user_frame_module_level_and_no_suffix_matches(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "ops.py"
            f.write_text("import nope\n", encoding="utf-8")
            rich = f"│ {f.absolute()}:1 in <module> │\n│ ❱ 1 import nope │\nModuleNotFoundError: No module named 'nope'"
            self.assertEqual(render.user_frame(rich, f), "at ops.py:1 in <module>: import nope")
            manim_frame = "│ /site-packages/manim/utils/module_ops.py:64 in get_module │\n│ 64 x │"
            self.assertEqual(render.user_frame(manim_frame, f), "")  # "ops.py" must not match module_ops.py
            plain = f'Traceback:\n  File "{f.absolute()}", line 1, in <module>\n    import nope'
            self.assertEqual(render.user_frame(plain, f), "at ops.py:1 in <module>: import nope")

    def test_user_frame_survives_a_split_line_number(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.py"
            f.write_text("\n" * 11 + "boom()\n", encoding="utf-8")
            out = f"│ {f.absolute()}:1 │\n│ 2 in construct │\n│ 9 boom() │"  # rich broke "12" across lines
            self.assertEqual(render.user_frame(out, f), "at v.py:12 in construct: boom()")

    def test_narration_by_scene_reads_voices(self):
        with tempfile.TemporaryDirectory() as d:
            lines = Path(d) / "lines" / "video"
            lines.mkdir(parents=True)
            (lines / "Intro.jsonl").write_text(json.dumps({"key": "k", "voice": "bm_george"}) + "\n", encoding="utf-8")
            (lines / "Mute.jsonl").write_text("", encoding="utf-8")
            self.assertEqual(render.narration_by_scene(Path(d), "video"), {"Intro": {"bm_george"}})


class TestNarrate(unittest.TestCase):
    letters = staticmethod(lambda ch: {"B": "bˈi", "C": "sˈi"}.get(ch, ""))

    def k(self, s):
        return narrate.kokoro_text(s, self.letters)

    def test_letter_A_names_get_letter_sound(self):
        self.assertEqual(self.k("Answer A is better than B."), "Answer [A](/ˈA/) is better than [B.](/bˈi./)")
        self.assertEqual(self.k("A wins almost surely."), "[A](/ˈA/) wins almost surely.")
        self.assertIn("[A](/ˈA/)'s", self.k("But pull A's score far ahead."))

    def test_article_A_untouched(self):
        self.assertEqual(self.k("A reward model takes a prompt."), "A reward model takes a prompt.")
        self.assertEqual(self.k("He said a thing."), "He said a thing.")

    def test_sentence_final_letters_keep_their_period(self):
        self.assertEqual(self.k("We pick B. Then A wins."), "We pick [B.](/bˈi./) Then [A](/ˈA/) wins.")
        self.assertEqual(self.k("Plan A."), "Plan [A.](/ˈA./)")

    def test_pronoun_I_untouched(self):
        self.assertEqual(self.k("I think the answer is C."), "I think the answer is [C.](/sˈi./)")

    def test_sentence_timings_with_hyphenated_tokens(self):
        words = [("You", 0.0, 0.2), ("fine-tune", 0.2, 0.7), ("it", 0.7, 0.8), (".", 0.8, 0.9),
                 ("Then", 1.2, 1.4), ("an", 1.4, 1.5), ("S-shaped", 1.5, 2.0), ("curve", 2.0, 2.4)]
        spans = narrate.sentence_timings(["You fine-tune it.", "Then an S-shaped curve."], words, 2.5)
        self.assertEqual(spans, [(0.0, 0.8), (1.2, 2.4)])  # real timings, not the proportional fallback

    def test_sentence_timings_fallback_is_proportional(self):
        spans = narrate.sentence_timings(["one two", "three four five six"], [], 6.0)
        self.assertEqual(spans, [(0.0, 2.0), (2.0, 6.0)])

    def test_wer_ignores_fillers_and_digit_spelling(self):
        self.assertEqual(narrate.wer("The answer is 2.", "answer is two"), 0.0)
        self.assertGreater(narrate.wer("one two three four", "one four"), 0.25)

    def test_check_voice(self):
        self.assertIsNone(narrate.check_voice("am_michael"))
        self.assertIn("did you mean am_michael", narrate.check_voice("am_micheal"))
        self.assertIsNone(narrate.check_voice("af_bella,af_heart"))
        self.assertIn("mixes US and UK", narrate.check_voice("af_bella,bm_george"))
        self.assertIn("did you mean am_michael", narrate.check_voice("AM_MICHAEL"))
        self.assertIn("not an English voice", narrate.check_voice("jf_alpha"))

class TestStyleLint(unittest.TestCase):
    def run_lint(self, lines):
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            return style_lint.lint(lines)

    def test_caption_speak_is_flagged(self):
        warns = self.run_lint(["In this video we will explore rewards.", "Equal scores: a coin flip.",
                               "A big gap: A wins.", "Let's delve in!"])
        text = " ".join(warns)
        self.assertIn("agenda opener", text)
        self.assertIn("caption-style fragment", text)
        self.assertIn("delve", text)

    def test_sentences_keep_closers_and_skip_abbreviations(self):
        split = style_lint.split_sentences
        self.assertEqual(split('He said "hi." Then go.'), ['He said "hi."', "Then go."])
        self.assertEqual(split("Ask Dr. Smith, e.g. Monday. Done."), ["Ask Dr. Smith, e.g. Monday.", "Done."])


    def test_inflections_and_curly_apostrophes(self):
        warns = " ".join(self.run_lint(["So let’s say we delved into it.", "Here’s the thing about that."]))
        self.assertIn("delve", warns)
        self.assertIn("here's the thing", warns)

    def test_bad_input_exits_2(self):
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "x.jsonl"
            bad.write_text('{"bad json\n', encoding="utf-8")
            for arg in (str(bad), d):
                with self.subTest(arg=arg):
                    p = subprocess.run([sys.executable, str(SKILL / "scripts" / "style_lint.py"), arg],
                                       capture_output=True, text=True)
                    self.assertEqual(p.returncode, 2, p.stderr)

    def test_grant_like_prose_passes(self):
        para = ("And if you think about it for a moment, the derivative is really asking you to imagine a tiny nudge "
                "to the input, and then to look at how much the output changes in response to that nudge. "
                "So what you want is the ratio between those two changes, and you want to think of it as the "
                "nudge gets smaller and smaller, which is a kind of strange thing to ask for at first. "
                "Now, this little ratio right here is what people call the derivative, and you can picture it "
                "as the slope of a line that just barely kisses the graph at the point you care about.")
        self.assertEqual(self.run_lint([para]), [])


class TestCheckEnv(unittest.TestCase):
    def test_parse_version_handles_prereleases(self):
        import check_env

        self.assertEqual(check_env.parse_version("0.22.0rc1"), (0, 22, 0))
        self.assertEqual(check_env.parse_version("0.23.dev4"), (0, 23, 0))
        self.assertGreaterEqual(check_env.parse_version("0.22.1"), check_env.MIN_MANIM)


@unittest.skipUnless(HAS_MANIM, "manim not installed")
class TestTbb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import logging

        import tbb

        logging.getLogger("manim").setLevel(logging.ERROR)
        cls.tbb = tbb

    def test_split_on_keys_skips_control_words(self):
        parts = self.tbb._split_on_keys(r"\sum_{n=1}^{\infty} n", ["n"])
        self.assertNotIn(r"\i", parts)
        self.assertEqual("".join(parts), r"\sum_{n=1}^{\infty} n")
        self.assertEqual(parts.count("n"), 2)

    def test_speakable(self):
        sp = self.tbb.speakable
        self.assertEqual(sp("x² + y² = r²"), "x squared plus y squared equals r squared")
        self.assertEqual(sp("Âᵢ"), "A hat i")
        self.assertEqual(sp("π* ∝ π_ref"), "pi star is proportional to pi ref")
        self.assertTrue(sp("e^(r/β)").isascii())

    def test_split_sentences(self):
        self.assertEqual(self.tbb.split_sentences("One thing. Two things? Three!  And 3.14 stays."),
                         ["One thing.", "Two things?", "Three!", "And 3.14 stays."])

    def test_group_arguments_braces_script_and_macro_arguments(self):
        g = self.tbb._group_arguments
        self.assertEqual(g(["e^", "{x}"], {"{x}"}), ["e^{", "{x}", "}"])
        self.assertEqual(g([r"\\frac", "{x}", "{y}"], {"{x}", "{y}"}), [r"\\frac{", "{x}", "}{", "{y}", "}"])
        self.assertEqual(g([r"\\alpha ", "="], {"="}), [r"\\alpha ", "="])  # operators keep their spacing

    def test_speakable_ascii_math(self):
        sp = self.tbb.speakable
        for s, want in [("x->y", "x goes to y"), ("a <= b", "a is at most b"), ("x != y", "x is not equal to y"),
                        ("a*b", "a times b"), ("x^2", "x squared"), ("and/or", "and or"), ("dy/dx", "dy over dx")]:
            self.assertEqual(sp(s), want)

    def test_public_api_exists_and_hides_internals(self):
        missing = [n for n in self.tbb.__all__ if not hasattr(self.tbb, n)]
        self.assertEqual(missing, [])
        self.assertNotIn("AUDIO_MODE", self.tbb.__all__)


    def test_tex_keeps_each_string_its_own_piece(self):
        from manim import RED

        pieces = [p.tex_string for p in self.tbb.tex(r"e^{x}", "=", r"\\sum {x}_i", t2c={"{x}": RED}).submobjects]
        self.assertIn("=", pieces)        # the closing brace never joins the next string
        self.assertNotIn("}", pieces)     # glyph-less closing braces are dropped

    def test_tex_braces_unbraced_macro_arguments_and_skips_text(self):
        self.assertTrue(self.tbb._is_argument(r"\\hat ", "y"))
        self.assertTrue(self.tbb._is_argument(r"\\sqrt[3]", "{x}"))
        self.assertFalse(self.tbb._is_argument(r"\\alpha ", "="))
        self.assertEqual(self.tbb._split_on_keys(r"\\text{max} x", ["x"]), [r"\\text{max} ", "x"])

    def test_speakable_reads_prose_as_prose(self):
        sp = self.tbb.speakable
        for s, want in [("don’t stop", "don't stop"), ("Möbius strip", "Mobius strip"), ("naïve", "naive"),
                        ("https://example.com/a/b", "example dot com"), ("<b>bold</b> text", "bold text"),
                        ("end with <eos>", "end with eos"), ("90°", "90 degrees"), ("distance/time", "distance over time"),
                        ("input/output", "input or output"), ("p(x|y)", "p(x given y)"), ("the |x|", "the length of x"),
                        ("2–4 minutes", "2 to 4 minutes"), ("x̂", "x hat")]:
            with self.subTest(s=s):
                self.assertEqual(sp(s), want)

    def test_light_copy_matches_deepcopy(self):
        from manim import DecimalNumber
        from manim.mobject.text.numbers import string_to_mob_map

        def deep(num, string, mob_class=None, **kwargs):  # ManimCE 0.22's own _string_to_mob
            mob_class = mob_class or num.mob_class
            if string not in string_to_mob_map:
                string_to_mob_map[string] = mob_class(string, **kwargs)
            mob = string_to_mob_map[string].copy()
            mob.font_size = num._font_size
            return mob

        def run(method):
            string_to_mob_map.clear()  # each path builds its own glyphs: a mutated cache can't hide
            saved = DecimalNumber._string_to_mob
            DecimalNumber._string_to_mob = method
            try:
                n = DecimalNumber(3.14159, color="#FF0000", font_size=40).shift(2 * UP_)
                for v in (-27.5, 0.5, 123.25):
                    n.set_value(v)
                return [(m.points.copy(), m.get_fill_color()) for m in n.family_members_with_points()]
            finally:
                DecimalNumber._string_to_mob = saved

        import numpy as np
        UP_ = np.array([0.0, 1.0, 0.0])
        light, ref = run(self.tbb._decimal_string_to_mob), run(deep)
        self.assertEqual(len(light), len(ref))
        for (p, c), (q, d) in zip(light, ref):
            self.assertTrue(np.allclose(p, q))
            self.assertEqual(c, d)

    def test_light_copy_never_touches_the_cached_glyphs(self):
        import numpy as np
        from manim import RED, UP, DecimalNumber
        from manim.mobject.text.numbers import string_to_mob_map

        string_to_mob_map.clear()
        n = DecimalNumber(3.5)
        snapshot = {k: [m.points.copy() for m in v.family_members_with_points()] for k, v in string_to_mob_map.items()}
        n[0].get_part_by_tex("3").shift(UP)  # the copy's own parts...
        n[0].set_color_by_tex("3", RED)
        n.set_value(7.25)
        for k, pts in snapshot.items():      # ...never the cached glyphs every later number copies
            now = [m.points for m in string_to_mob_map[k].family_members_with_points()]
            self.assertTrue(all(np.allclose(a, b) for a, b in zip(pts, now)), k)

    def test_waits_under_captions_are_split_with_exact_timing(self):
        import tempfile as tf

        import numpy as np
        from manim import Dot, FadeIn, tempconfig

        tbb, seen = self.tbb, {}

        class Probe(tbb.TbbScene):
            def construct(self):
                with self.voiceover("One two three four. Five six seven eight.") as v:
                    self.play(FadeIn(Dot()))
                    for d in (2.37, 0.5, 1.0 / 15):  # a long wait across a caption swap, a short one, one frame
                        t0 = self.time
                        segments = self._caption_wait_segments(d)
                        self.wait(d)
                        seen[d] = (self.time - t0, segments)
                    v.wait_until(1)

        with tf.TemporaryDirectory() as d, tempconfig({"media_dir": d, "frame_rate": 15, "pixel_height": 120,
                                                       "pixel_width": 214, "disable_caching": True,
                                                       "verbosity": "ERROR", "progress_bar": "none"}):
            Probe().render()
        for d, (elapsed, segments) in seen.items():
            frames = len(np.arange(0, d, 1 / 15))
            self.assertAlmostEqual(elapsed, frames / 15, places=9)       # exactly one ordinary wait's frames
            if segments is not None:
                self.assertEqual(sum(n for n, _ in segments), frames)
        self.assertIsNotNone(seen[2.37][1])                              # and the long one was split

    def test_style_lint_splitter_is_the_same_code(self):
        self.assertEqual(self.tbb._SENTENCE_END.pattern, style_lint._SENTENCE_END.pattern)
        self.assertEqual(self.tbb._ABBREVIATIONS, style_lint._ABBREVIATIONS)

    def test_narration_key_matches_narrate_for_any_voice(self):
        tbb = self.tbb
        self.assertEqual(tbb.TTS_REVISION, narrate.TTS_REVISION)
        saved = tbb.VOICE, tbb.VOICE_SPEED
        try:
            tbb.VOICE, tbb.VOICE_SPEED = "bm_george", 1.1
            self.assertEqual(tbb.narration_key("Hello."), narrate.narration_key("Hello.", "bm_george", 1.1))
        finally:
            tbb.VOICE, tbb.VOICE_SPEED = saved


if __name__ == "__main__":
    unittest.main()
