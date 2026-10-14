# voiceppt — Voice-Driven Slide Presenter

Take-home prototype for SynthioLabs (Solutions Engineer, AI). A voice AI agent
presents a 6-slide deck, answers spoken questions grounded in the deck content,
automatically navigates to the relevant slide as the conversation moves, and
can be interrupted mid-sentence.

**Status: working end-to-end**, verified against the real OpenAI Realtime API
(not just mocked) — see [Verification](#verification) below.

**Live demo:** frontend at https://voiceppt.netlify.app, backend at
https://voiceppt-backend.onrender.com (see [Deployment](#deployment) for how
these two are wired together).

---

## How it works

- **Topic:** "How Large Language Models Work" — 6 slides (overview,
  tokenization, transformers & attention, training/RLHF, inference &
  sampling, limitations). Chosen so the agent has natural reasons to jump
  across non-adjacent slides, not just next/previous.
- **Voice pipeline:** OpenAI's Realtime API (`gpt-realtime-2.1`), speech-to-speech
  over WebRTC, direct browser↔OpenAI audio — the backend never touches raw
  audio, it only mints a short-lived ephemeral token and serves slide content.
- **Slide navigation:** the model calls a `show_slide(slide_number)` tool
  whenever the conversation's topic matches a different slide; the frontend
  renders whatever slide the tool call names.
- **Interruption:** handled automatically by OpenAI's server-side VAD over
  WebRTC (it truncates in-flight audio the instant it detects the user
  talking) — no custom cancel/truncate logic needed client-side.

```
Browser (React)                      FastAPI backend                 OpenAI Realtime API
┌──────────────────┐                ┌──────────────────┐            ┌──────────────────┐
│ SlideView UI      │  GET /api/slides │ slides.py        │            │                  │
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

Full rationale behind every architectural decision (why FastAPI/React, why
the Realtime API over a cascaded STT→LLM→TTS pipeline, why tool calling over
keyword matching, trade-offs for a production/pharma deployment, etc.) is in
[`working.md`](working.md). [`SPEC.md`](SPEC.md) has the condensed
requirements/contracts.

---

## Project layout

```
backend/   FastAPI app — slide data, ephemeral token minting, tests, eval
frontend/  React + Vite + TS — slide UI, WebRTC voice session hook
```

## Setup & running locally

### Backend

```bash
cd backend
virtualenv .venv && source .venv/bin/activate   # or .venv/local/bin/activate on Debian/Ubuntu
pip install -r requirements.txt
cp .env.example .env   # then paste a real OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # defaults to http://localhost:8000, fine for local dev
npm run dev
```

Open http://localhost:5173, click "Start voice session," allow microphone
access.

### Environment variables

| Var | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `backend/.env` | Real key, never sent to the browser — only used server-side to mint ephemeral session tokens. |
| `REALTIME_MODEL` | `backend/.env` | Defaults to `gpt-realtime-2.1`. |
| `REALTIME_VOICE` | `backend/.env` | Defaults to `marin`. |
| `CORS_ALLOW_ORIGINS` | `backend/.env` | Comma-separated allowed frontend origin(s). |
| `VITE_API_BASE_URL` | `frontend/.env` | Backend base URL the frontend calls for `/api/*`. |

Without a real `OPENAI_API_KEY`, everything still runs — slide browsing and
manual navigation work, and `POST /api/session` fails with a clean `502`
instead of crashing (see tests). Voice obviously needs the real key.

---

## Verification

- **Backend unit tests** (mocked, no API key needed): `cd backend && source
  .venv/local/bin/activate && pytest` → 6/6 passing. Covers slide data shape,
  successful session creation, and graceful 502s on both an OpenAI error
  response and a network failure.
- **Golden-dataset eval** (real API calls, text-mode, isolates routing
  accuracy from speech-recognition accuracy): `cd backend && python
  eval/run_eval.py` → **22/22 (100%)** across 7 categories — direct content
  match, explicit navigation commands, ambiguous slide overlap, off-topic
  chit-chat, multi-turn contextual follow-up, out-of-scope questions, and
  adversarial/garbled input. Full methodology and findings in
  [`backend/eval/README.md`](backend/eval/README.md).
- **Interruption/barge-in**: manually verified live in the browser with a
  real microphone — confirmed the agent's speech stops immediately and the
  session responds to the new input rather than finishing its sentence. This
  one is inherently a human-judgment check (does it *feel* right, not just
  "did VAD technically fire"), so it isn't part of the automated eval — see
  [`backend/eval/README.md`](backend/eval/README.md) for why.
- **Live smoke test against the real OpenAI endpoint**: confirmed the
  placeholder-key → real-key transition end-to-end, including catching and
  fixing a live API schema-drift bug (`session.type` became a required field
  in the GA Realtime API) the moment a real key was added. Documented in
  `working.md` §12.

---

## Deployment

Netlify hosts the frontend (static build) well, but doesn't run a persistent
Python process — the backend holds the real OpenAI key server-side, so it
needs an actual host. This repo deploys as two pieces:

- **Frontend → Netlify** (config: [`netlify.toml`](netlify.toml))
- **Backend → Render** (config: [`render.yaml`](render.yaml))

### 1. Deploy the backend (Render)

1. Go to [render.com](https://render.com) → New → **Blueprint** → connect
   the `voiceppt` GitHub repo. Render will read `render.yaml` automatically.
2. When prompted for `OPENAI_API_KEY` (marked `sync: false`, so Render asks
   rather than storing it in the repo), paste your real key.
3. Deploy. Note the resulting URL, e.g. `https://voiceppt-backend.onrender.com`.

### 2. Deploy the frontend (Netlify)

1. Go to [app.netlify.com](https://app.netlify.com) → **Add new site** →
   Import from Git → select the `voiceppt` repo. It will read
   `netlify.toml` automatically (base `frontend/`, build `npm run build`,
   publish `dist/`).
2. Site settings → Environment variables → add `VITE_API_BASE_URL` = the
   Render URL from step 1 (e.g. `https://voiceppt-backend.onrender.com`).
3. Deploy. Note the resulting URL, e.g. `https://voiceppt.netlify.app`.

### 3. Close the loop: update backend CORS

1. Back in Render → the backend service → Environment → set
   `CORS_ALLOW_ORIGINS` to the Netlify URL from step 2. Use the bare
   origin only — scheme + host, **no trailing slash and no path**
   (`https://voiceppt.netlify.app`, not `https://voiceppt.netlify.app/`).
   CORS matches the browser's `Origin` header exactly, which never has a
   trailing slash; a mismatch here surfaces in the browser as a generic
   `Failed to fetch`, not an auth error.
2. This repo also commits a best-guess value directly in `render.yaml` so a
   fresh deploy of this Blueprint starts with the right origin out of the
   box. In practice, though, **the dashboard value is the one that's actually
   live** — once you edit `CORS_ALLOW_ORIGINS` in the Environment tab, Render
   treats it as a per-service override that a later `git push`/redeploy does
   *not* revert back to the `render.yaml` value, even though both are
   nominally the "same" blueprint-managed variable. So if this value is ever
   wrong, fix it in the Environment tab directly — don't assume pushing a
   `render.yaml` change alone will update it.
3. Click "Save, rebuild, and deploy" (editing an env var in the dashboard
   triggers this automatically).

Render's free tier spins down on inactivity — the first request after idle
can take ~30-60s to cold-start.

---

## Appendix: Self-Hosted Alternative (Production Consideration)

This prototype uses OpenAI's Realtime API (cloud, hosted) because it was the
fastest path to a working demo within the assessment's timeline. That's the
right call for a 2-day prototype, but **not necessarily the right call for
every production deployment** — in particular, a pharma customer whose
security/compliance team won't allow voice audio to leave their VPC would
rule out any third-party cloud voice API outright. For that scenario, the
open-source self-hosted path below is the real proposal.

**Option 1 — Moshi (Kyutai), Apache-2.0, open weights:**
A genuinely full-duplex speech-to-speech foundation model, runnable on your
own GPU (≈160ms theoretical / ≈200ms practical latency on an L4).
Architecturally the closest open equivalent to OpenAI/Gemini's realtime
models.
Limitation: it's built for natural spoken dialogue, not agentic tool-calling
— there's no first-class "emit a structured function call mid-response" the
way the cloud realtime APIs support. Using it here would mean inferring
slide-routing intent from its text stream rather than a native tool call,
which reintroduces the exact transcript-classification approach this
project's architecture decisions deliberately avoided.

**Option 2 — Pipecat or LiveKit Agents (self-hosted orchestration
frameworks, Apache-2.0):**
Assemble a cascaded pipeline yourself from self-hosted components —
Whisper/faster-whisper (STT) → any function-calling-capable LLM (self-hosted
via Ollama/vLLM, or still a hosted API if only the audio needs to stay
local) → Piper/Kokoro/XTTS (TTS). Both frameworks handle interruption
generically at the pipeline level (VAD-triggered cancellation of in-flight
LLM/TTS tasks), so barge-in doesn't need to be hand-rolled. Since the LLM
stage is a normal function-calling model, slide-routing via tool calls works
exactly as designed in this project — this is the more complete open-source
match to the actual requirements.
Trade-off: still a cascaded architecture (latency stacks across
STT→LLM→TTS), and now you own GPU provisioning and model-serving ops for
every component instead of a vendor doing it.

**When to actually reach for this:** data-residency/VPC-only requirements,
strict regulatory constraints on where audio/PHI can be processed, or cost
at a scale where the cloud API's per-minute pricing compounds meaningfully.
Not for a quick prototype or pilot where proving the interaction model
matters more than deployment topology.
