# Writing narration like Grant Sanderson

This guide is derived from 14 3Blue1Brown narrations, about 52k words and 278 minutes. It spans 2016–2026: Essence of Linear Algebra 1 and 3, Essence of Calculus 1 and 2, neural networks, the Putnam problem, Fourier, Bayes, Hamming codes, convolutions, attention, colliding blocks (2025), the Laplace transform (2025) and entropy (2026).

- **Sources:** the manual English subtitle tracks, which have real punctuation, plus word-timed auto-captions for the pause measurements.
- **Counting:** counts are corpus totals unless marked per 1k words.
- **Sentence lengths:** they follow the subtitler's punctuation, so treat them as upper bounds.
- **Quotes:** short excerpts quoted for style analysis.

Quotations are short excerpts © Grant Sanderson / 3Blue1Brown, used for commentary and analysis; this skill is not affiliated with 3Blue1Brown.

**Read this before writing any narrated script. The words matter more than the voice.**

## Contents

- The numbers to hit
- Rules
- Anti-patterns (these make AI narration sound unlike him)
- Script template
- Self-check before rendering

## The numbers to hit

| Measure | Grant | Notes |
|---|---|---|
| Pace | ~185 wpm (167–204) | Kokoro `am_michael` at speed 1.0 measured ~170–175 wpm on paragraphs, so the same script runs about 7% longer. |
| Sentence length | mean 25, median 23 words | 32% are 30+ words. Long, comma-chained sentences are the default. |
| Very short sentences (≤5 words) | ~3% | Deliberate beats: "This is a 3.", "Wonderful.", "Here's my thinking." |
| Questions | ~5% of sentences | Puzzle videos run higher (Putnam 18%). Teaching videos stay under 2–5%. |
| Exclamation marks | ~0.15 per 1k words | Effectively never. Enthusiasm lives in word choice. |
| "you" / "we, let's" / "I" | 21.5 / 12.2 / 8.2 per 1k | Address the viewer first. Recent videos often use "you and I". |
| Sentence-initial "And" | ~1 in 9 sentences | His strongest syntactic signature. Then "So", "But", "Now", "If", "For example". |
| Casual hedges | ~7 per 1k | "kind of", "sort of", "a little", "pretty", "basically", "maybe". |
| Breath groups | 15–30 words between pauses | Recent videos have few pauses over 2 s; the animation carries the silences. |

The signature vocabulary, per 1k words:

| Word | Rate per 1k |
|---|---|
| "this" (mostly *this + noun*: "this diagram", "this expression", "this ratio") | 17.2 |
| "just" | 5.2 |
| "really" | 2.1 |
| "think about" | 1.6 |
| "let's" | 1.6 |
| "actually" | 1.4 |
| "you might" | 1.3 |
| "for example" | 1.0 |

Other recurring phrases, as corpus totals:
- "imagine" 45, "notice" 28, "I mean," 28, "the key …" 32
- "Well," 24, "remember" 21, "I want you to" 19
- "fancy word / name" and "in the business" 21 together

## Rules

### Openings
1. **Open on the object or the puzzle, never on an agenda.** He doesn't open with "In this video we will…".
   - "This is a 3." (NN)
   - "Have you ever wondered how it's possible to scratch a CD … and still have it play back" (Hamming)
   - "the derivative measures an instantaneous rate of change, but … that phrase is actually an oxymoron" (Calc 2)
2. **State the goal as what the viewer will come away with.** "my goal is for you to come away feeling like you could have invented calculus yourself" (Calc 1)
3. **Give an honest scope note early,** where it applies. "a lot of what I want to show is not necessary if your only goal is to solve equations" (Laplace)
4. **Introduce one central example within the first minute, with real numbers, and keep returning to it.** "As our central example, I want you to imagine a car that starts at some point A" (Calc 2)

### Sentences and voice
5. **Write long, flowing sentences chained with commas and "and", around 20–25 words.** Then drop a rare 2–5 word beat after a build.
6. **Start sentences with "And", "So", "But", "Now".** Avoid formal connectives: "Furthermore" and "Additionally" never appear, and "Moreover" appears about once in 52k words.
7. **Talk to "you" most, "we/let's" next, and "I" for intent and opinion.** Use "I want you to…", "I think", "I mean".
8. **Hedge casually,** about 7 times per 1k words. "the idea is going to be to take this graph and sort of wrap it up around a circle" (Fourier)
9. **Express wonder in plain words.**
   - "Isn't that clever?" (Hamming)
   - "Now take a step back, because that's beautiful." (Calc 2)
   - "That's very surprising." (Laplace)
10. **Use specific numbers in examples,** and drop into them with "For example" or "Let's say". "It moves 0.001 m. That's very small" (Calc 2)

### Pointing at the visuals
11. **Point with *this + noun*,** and save "right here" for rare emphasis. Never use "as you can see on the screen". The animation highlights the referent; the words name what kind of thing it is.
12. **Narrate motion as it unfolds, in sequence words.** "move straight up until you intersect the circle, and then down and to the right with that same slope" (Blocks)
13. **Direct attention after the visual is up,** using "Notice…" or "Look at…". "Notice the order matters here." (LA1)

### Notation and formulas
14. **Describe first, then name.** He uses "called", "known as" and "what we call" about 50 times.
    - "This number inside the neuron is called its activation" (NN)
    - "This number is known as the prior." (Bayes)
15. **Downplay jargon.**
    - "Transformation is essentially a fancy word for function." (LA3)
    - "known in the business as a parity check" (Hamming)
16. **Read every symbol in words and gloss it straight away.** Never read a formula off as a string of symbols.
    - "dx, the little nudge to the input that caused a to change" (Calc 1)
    - "this vertical bar means given that" (Bayes)
17. **Delay formal definitions until they're wanted, and say why.** "doing so too early would spoil a good story" (Entropy)
18. **Flag non-standard names.** "I'm going to call this one the value up matrix, which again is not conventional." (Attention)

### Difficulty
19. **Let the viewer make the naive move, then correct it.** The "You might think … but" frame appears 11 times.
    - "You might think you have infinite choices, but you don't." (Laplace)
20. **Voice the viewer's objection as a question.** "But I hear some of you asking, how does the robot know how to decode this?" (Entropy)
21. **Ask for a prediction before a reveal, only 1–3 times per video,** and leave a 2–4 s visual beat. "pause, actively predict what the scheme is going to be before I tell you" (Hamming). Use the behaviour, not "pause and ponder" as a catchphrase.
22. **Name the load and give a specific reason not to worry.**
    - "a lot of people find the attention mechanism … very confusing, so don't worry if it takes some time" (Attention)
23. **Be candid about choices and limits.**
    - "admittedly that's kind of an arbitrary choice" (NN)
    - "if I'm honest with you, the symbolic reasoning is probably the easier way" (Laplace)
24. **Comment on strategy: how to think, not just what's true.** "a good policy is to not try too hard to get at the answer directly" (Calc 1)
25. **Step back after a dense stretch.** "That is a lot of different moving parts, so let's step back and summarize what we have so far." (Fourier)

### Personality and endings
26. **Use dry, deadpan humour about once every 3–5 minutes,** embedded in a technical sentence, never as a set-piece. "There is an international law saying that when you're doing physics for more than a half hour, you must use at least one small angle approximation." (Blocks)
27. **Stretch one concrete analogy over the whole video,** and return to it at the end. Laplace: the car versus engine analogy, set up in the opening and closed in the final section.
28. **End with three things:** the one-sentence takeaway, a specific moral about method, and a forward hook framed as unfinished elegance.
    - "To sum up, linear transformations are a way to move around space such that gridlines remain parallel and evenly spaced" (LA3)
    - "evidence should not determine beliefs, but update them" (Bayes)
    - "what I haven't told you yet is just how elegant this algorithm really is" (Hamming)

## Anti-patterns (these make AI narration sound unlike him)

- **Agenda openers.** "In this video we will explore…", "Today we're going to…", "Let's dive in." The corpus has 0 such openings.
- **Hype vocabulary.**
  - delve (0 in the corpus), journey, unlock, harness, game-changer, mind-blowing, incredible
  - "fascinating" (2 in 52k words), "crucial" (2), "dive in" (3)
- **Exclamation marks**, and interjections like "Amazing!".
- **Over-signposting.**
  - "In other words" (4 total), "Here's the thing" (0), "Let's break it down", "It's important to note", "Simply put", "Essentially," at the start of a sentence.
  - First/Second/Third scaffolding.
- **Rhetorical triplets** ("simple, elegant, and powerful") and parallel flourishes. His lists are plain inventories of real items: "span, bases, and linear dependence".
- **Caption-speak.** Telegraphic fragments such as "Equal scores: a coin flip." Write the full spoken sentence instead.
- **Uniform medium-length sentences**, or a constant stream of questions.
- **Naming before showing**, or reading symbols without saying what they mean.
- **Empty encouragement or inspiration.** "Great job!", "Math is all around us". His reassurance is specific; his morals are claims about method.
- **Channel furniture.**
  - Patreon or sponsor reads, "Grant here", subscribe jokes
  - "Essence of …" branding
  - "last chapter" references when no series exists
  - "pause and ponder" as a catchphrase

## Script template

Grant speaks about 100 words per ~32 s; with Kokoro at speed 1.0, 100 words is about 35 s.

**Whole video:**
1. Hook, goal and scope: 150–300 words.
2. Sections, built from the beats below.
3. Takeaway, moral and forward hook: 150–250 words.

Recent 3b1b videos have 6–10 sections. A focused single-idea narrated explainer needs 1–2 (about 2–5 minutes in all).

**One section** totals about 330–700 words, or 2–4 minutes:

| Beat | Words | Content | Typical language |
|---|---|---|---|
| 1. Hook or bridge | 30–60 | A question, a callback, or a surprising fact | "Now…", "So the question is…" |
| 2. Concrete setup | 60–120 | One specific example with real numbers; the visual appears | "Let's say…", "I want you to imagine…" |
| 3. Naive attempt | 40–100 | The obvious approach, and why it falls short | "You might think… but…" |
| 4. Prediction prompt (optional) | 15–40 | Ask the viewer to anticipate, then a 2–4 s beat | "Take a moment to see if you can…" |
| 5. Key move or reveal | 100–200 | The insight, narrated with *this + noun* while it animates | "Notice…", "And this…" |
| 6. Name and notation | 40–80 | Term or symbol after the concept, read in words, each part glossed | "This is called…", "a fancy name for…" |
| 7. Reaction and candour | 15–40 | Wonder, a dry aside, or an honest caveat | "Isn't that neat?", "admittedly…" |
| 8. Step-back summary and handoff | 30–60 | What we now know, plus the open thread | "So far…", "But what I haven't told you yet…" |

**Mapping beats to code:** in tbb, a section is one or more scenes of 15–60 s (so renders stay short and parallel), and each beat cluster is one `self.voiceover(...)` block. Beats 4 and 5 are where you use `v.wait_until("phrase")` to land the reveal on the word that names it.

## Self-check before rendering

`render.py --voice` runs a style lint on the collected script. It flags:
- agenda openers and hype words
- exclamation marks
- caption-style fragments
- the mean sentence length and the "you" rate, against the targets above

Fix every warning, or justify ignoring it.
