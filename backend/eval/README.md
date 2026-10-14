# Eval: golden dataset for slide-routing accuracy

## What this tests, and what it deliberately doesn't

The brief has two core behavioral requirements:

1. "The AI agent should be able to automatically change slides based on the
   user's question." — **this is what `golden_dataset.json` / `run_eval.py`
   test.**
2. "User should be able to interrupt the AI agent." — **not covered by this
   harness.** Barge-in on WebRTC is a server-side audio-buffer-truncation
   behavior triggered by VAD detecting new speech while audio is playing
   (see `working.md` / README.md for the citation). There is no text
   equivalent of "the user started talking over the agent" — it only exists
   as an audio-timing event. Automating it would require synthesizing TTS
   audio for every test case and injecting it as a fake microphone track
   into a real browser session, which was explicitly scoped out in favor of
   the cheaper, faster text-mode approach below. See the manual checklist
   at the bottom of this file instead.

## Why text mode, not real audio

Golden-dataset grading should isolate the thing the app's design actually
controls: given the system prompt + `show_slide` tool schema built in
`app/slides.py`, does the model make the right navigation call? Whether
speech was transcribed correctly is a property of OpenAI's ASR, not of this
app, and mixing the two into one pass/fail would make failures ambiguous
(wrong slide because of bad routing logic, or because the transcript was
wrong?). Running cases as text over the Realtime WebSocket API removes that
confound for the price of not testing voice specifically.

## How grading works

Each case in `golden_dataset.json` is one or more conversation turns sent to
a fresh Realtime session (isolated per case, same `instructions`/`tools` the
real app serves). After each turn, the harness inspects `response.done` for
a `show_slide` function call and grades it against one of three expectation
types:

- `"specific"` — exactly one correct `slide_id`.
- `"any_of"` — multiple slides are defensible (the question's content
  genuinely spans two slides); any one of the listed ids passes.
- `"no_change"` — no `show_slide` call should fire at all (off-topic,
  out-of-scope, a same-slide follow-up, or adversarial/garbled input).

20 cases / 22 turns across 7 categories: direct content match, explicit
navigation commands, ambiguous overlap, off-topic chit-chat, multi-turn
contextual follow-up (tests the "don't re-navigate for a follow-up on the
current slide" instruction), out-of-scope questions (checks against
hallucinated navigation), and adversarial/garbled input.

## Running it

Requires a real `OPENAI_API_KEY` in `backend/.env` (makes live API calls -
~22 short text-only responses, on the order of a few cents total).

```bash
cd backend
source .venv/local/bin/activate
pip install -r eval/requirements.txt
python eval/run_eval.py
```

Prints a pass/fail summary per category and writes full details to
`eval/results.json`.

## Manual checklist: interruption / barge-in

**Status: verified ✅** — manually tested in the browser; the agent's speech stops
and the session responds to the new input instead of finishing its sentence.

Run this by hand in the browser (`npm run dev` + backend running with a
real key):

1. Click "Start voice session," wait for the agent's opening greeting to
   start playing (badge shows "Speaking").
2. While it's still talking, speak over it with any unrelated sentence.
3. Expect: the badge flips to "Listening…" almost immediately, the agent's
   audio stops mid-sentence (not after it finishes), and it responds to
   what you just said rather than finishing the interrupted sentence.
4. Confirm the session doesn't error or disconnect from the interruption
   (status stays "connected" throughout).

This isn't automated because it requires real audio timing against a live
mic - there's no meaningful way to script "talk over it" without recording
actual audio, which was explicitly deferred per the text-mode-only decision
for this round of eval work.
