# SPEC — voiceppt

Voice-driven slide presentation agent. Take-home assessment for SynthioLabs (Solutions Engineer, AI).

## Objective

A working prototype where:
1. The app presents 5-6 slides on a chosen topic.
2. A voice AI agent can be asked questions and automatically navigates to the slide relevant to the question.
3. The user can interrupt the agent while it's speaking (barge-in).
4. There's a real frontend and a real backend — not a single-file demo.

## Topic

**"How Large Language Models Work"** — 6 slides: Overview, Tokenization, Transformers & Attention, Training (pretraining + RLHF), Inference & Sampling, Limitations & What's Next. Chosen because it's technical, relevant to a voice-AI company's audience, and gives the agent natural follow-up questions to demo slide-jumping across non-adjacent slides (not just next/previous).

## Architecture

```
Browser (React)                      FastAPI backend                 OpenAI Realtime API
┌──────────────────┐                ┌──────────────────┐            ┌──────────────────┐
│ SlideDeck UI      │  GET /api/slides │ slides.py        │            │                  │
│ useRealtimeSession │ ───────────────▶│ (single source   │            │                  │
│  hook              │                 │  of truth for    │            │                  │
│                    │ POST /api/session│ content + tool   │            │                  │
│                    │ ───────────────▶│  schema)          │            │                  │
│                    │ ◀─ client_secret, tools, instructions           │                  │
│                    │                 │  mints ephemeral  │ ─────────▶ │ /v1/realtime/    │
│                    │                 │  token server-side│            │ client_secrets   │
│  RTCPeerConnection │ ── SDP offer, Authorization: Bearer <ephemeral> ──────────────────▶ │ /v1/realtime/calls│
│  + data channel     │ ◀───────────────────── SDP answer, audio track, JSON events ───────│                  │
└──────────────────┘                └──────────────────┘            └──────────────────┘
```

Audio flows **directly between the browser and OpenAI** over WebRTC — the backend never touches raw audio, only mints a short-lived ephemeral token and serves the slide content once. Full rationale for every choice here is in the conversation history / `working.md`; this file is the condensed, actionable version.

## Backend contract

- `GET /api/slides` → `[{id, title, bullets[]}, ...]` — the 6 slides, for rendering.
- `POST /api/session` → `{client_secret, tools, instructions}`:
  - `client_secret`: ephemeral token minted from `POST https://api.openai.com/v1/realtime/client_secrets`, used once by the browser to open the WebRTC session.
  - `tools`: the `show_slide(slide_number)` function schema, enum-constrained to valid slide IDs.
  - `instructions`: system prompt built from the same slide data (title + bullets of every slide), so the model can answer grounded in exactly what's on screen and knows when to call `show_slide`.

## Tool contract (what the model can do)

```json
{
  "type": "function",
  "name": "show_slide",
  "description": "Call this whenever the conversation's current topic matches a different slide than the one currently shown, or when the user explicitly asks to go to a slide.",
  "parameters": {
    "type": "object",
    "properties": { "slide_number": { "type": "integer", "enum": [1,2,3,4,5,6] } },
    "required": ["slide_number"]
  }
}
```

## Interruption

Handled by OpenAI's server-side VAD over the WebRTC session (confirmed in docs: with WebRTC the server manages the output audio buffer automatically on barge-in). Frontend listens for `input_audio_buffer.speech_started` / `response.cancelled` purely to update UI state (stop showing the "speaking" indicator) — no custom cancel/truncate logic needed client-side for the WebRTC transport.

## Acceptance criteria

- [ ] Backend serves slide data and mints a session without the key present (fails gracefully with a clear error, doesn't crash).
- [ ] Frontend renders all 6 slides and can navigate manually (fallback for when voice isn't configured/available).
- [ ] With a real `OPENAI_API_KEY` set, a voice session connects, the agent greets the user and talks through slide 1, answers a question by jumping to the matching slide, and can be interrupted mid-sentence.
- [ ] Backend has passing tests that don't require a real API key (mocked).
- [ ] `working.md` documents the rationale behind every non-obvious decision.

## Explicitly out of scope (per earlier architecture discussion)

- Real `.pptx`/`.pdf` rendering — slides are styled React components built from data.
- Multi-user/auth/persistence — single-session demo.
- Automated eval harness run end-to-end (golden dataset design is documented; not executed, since a real API key isn't available in this environment).
- Self-hosted/open-source voice stack — documented as a production alternative in `README.md`, not built.
