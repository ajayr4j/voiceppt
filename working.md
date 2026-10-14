# working.md — Build Log & Rationale

Personal reference log for every non-obvious decision made while building `voiceppt`.
`README.md` is the external-facing doc, `SPEC.md` is the condensed spec; this file is
the "why" behind both, plus the scaffolding/tooling decisions that don't belong in
either.

---

## 1. Repo naming and scope

- Repo lives at `/home/jaeger/Projects/voicesynthio` (working directory given by the
  user) but is conceptually named **`voiceppt`** per explicit instruction — this is
  what the folder would be renamed to / what the GitHub repo should be called on
  submission. The directory itself was not renamed mid-build to avoid breaking the
  running dev session paths; rename at submission time if desired (`mv voicesynthio
  voiceppt` or just create the GitHub repo as `voiceppt` and push this directory's
  contents into it — git history doesn't care about the local folder name).

## 2. Architecture decision (recap of the "why" — full detail in README.md)

- **Speech-to-speech (OpenAI Realtime API) over cascaded STT→LLM→TTS.** For a 2-day
  prototype, the realtime API collapses turn-taking, barge-in/interruption, and audio
  streaming into primitives OpenAI already solved (server-side VAD cancels/truncates
  the in-flight response the instant the user starts talking). Building the same
  behavior cascaded means hand-rolling an audio player that can be stopped mid-sentence
  and a VAD/endpointing layer — solvable, but it's infrastructure work that doesn't
  demonstrate the actual evaluation criteria (voice UX + tool-driven slide nav).
- **Production counterpoint (recorded for the JD's pharma/compliance context):** a
  cascaded pipeline gives an auditable text transcript at every hop (ASR output, LLM
  output, TTS input) before anything is spoken — valuable when a compliance team wants
  to review/approve exactly what the agent is allowed to say about a drug. Speech-to-
  speech models are more opaque in that respect. This is a real trade-off, not just a
  "prototype vs production" toggle — flagged explicitly in README.md so it isn't lost.
- **Tool calling (`show_slide`) over keyword/regex slide matching.** The model already
  has full conversational context (what was just asked, what's already been shown) —
  offloading "which slide is relevant" to a regex or embedding-similarity lookup
  duplicates reasoning the model is already doing, and adds a dataset-maintenance
  burden (keyword lists) for a 6-slide deck. Tool calling is the canonical pattern the
  Realtime API is designed around, and it's trivially gradeable (enum-constrained
  `slide_number` argument, that either matches ground truth or it doesn't).

## 3. Backend: FastAPI over Django

- Django's batteries (ORM, admin, auth, migrations) are all unused weight for a
  stateless token-minting + static-content API with two endpoints. FastAPI's async
  support matters because `mint_client_secret()` makes an outbound httpx call per
  session — async avoids blocking the event loop. Pydantic models give the
  request/response schema validation "for free," which doubles as the implicit API
  contract documented in SPEC.md.

## 4. Backend file layout and why each file is separate

- `app/config.py` — isolates `.env`/`pydantic-settings` loading so nothing else in the
  codebase reaches into `os.environ` directly; makes swapping config sources (e.g.
  secrets manager in production) a one-file change.
- `app/slides.py` — **single source of truth** for slide content. It drives three
  things that must never drift apart: (1) what `GET /api/slides` returns to render the
  UI, (2) the `show_slide` tool's enum of valid slide numbers, (3) the system prompt
  text embedded in `build_instructions()` that tells the model what's actually on each
  slide. Keeping these in one file/one list comprehension means adding a 7th slide is a
  single edit, not a three-file hunt.
- `app/realtime.py` — isolates the only piece of code that talks to OpenAI's HTTP API.
  This is the one module that needs mocking in tests (`httpx.AsyncClient.post`) and the
  one module that would need to change if swapping providers (e.g. to Gemini Live) —
  confirms the earlier architecture-comparison work wasn't just academic, the code is
  structured so that swap is a realistic possibility, not a rewrite.
- `app/routes/slides.py`, `app/routes/session.py` — thin FastAPI routers; kept separate
  from `main.py` so `main.py` stays a pure composition root (CORS config + router
  registration + health check), easy to scan in one read.

## 5. Why the `.env` placeholder values look the way they do

- `OPENAI_API_KEY=sk-replace-with-your-real-key` — deliberately an obviously-fake,
  obviously-labeled placeholder (not e.g. a blank string) so that: (a) it's
  self-documenting for whoever opens the repo, (b) a real call to OpenAI with it
  produces a clean 401 rather than some other ambiguous failure, which is exactly what
  was smoke-tested (see §8).
- `.env` and `.env.example` were made identical on purpose for this placeholder-only
  state — normally `.env` would be gitignored and `.env.example` would be the tracked
  template; both exist here so the app actually runs locally out of the box with zero
  setup beyond `cp` not even being needed. `.gitignore` still excludes real `.env`
  files going forward (see §9) so a real key, once added, is never accidentally
  committed.

## 6. Testing approach

- 6 backend tests cover: slide list shape/count/id integrity, successful session
  creation (mocked 200 from OpenAI), a mocked 401 from OpenAI surfacing as a clean 502
  (not a 500/crash), and a network-error path (httpx raising) also surfacing as 502.
- Deliberately **not** testing the realtime WebRTC/voice flow itself — that requires a
  live browser mic, a real API key, and a real OpenAI session; it's explicitly called
  out as untestable in this environment (no key) rather than faked with a brittle
  mock that would give false confidence.
- No frontend unit tests were added. Given the 2-day scope, the highest-value
  verification was: backend contract tests (cheap, fast, real signal) + a frontend
  production build / type-check (catches the entire class of "this would never have
  compiled" bugs) + manual smoke test instructions in README.md for the one thing that
  actually needs a human + a real key + a microphone. Writing React Testing Library
  tests for static slide rendering would be effort spent proving something a type
  checker + eyeballing already proves.

## 7. Frontend: Vite + React + TS over Streamlit / plain JS

- Streamlit was the user's own original instinct and was explicitly reconsidered: it's
  good for data-app dashboards, not for owning a `<video>`/`<audio>` WebRTC
  `RTCPeerConnection` and a data channel with manual JS event listeners — that requires
  real client-side JS control flow that Streamlit's rerun-on-every-interaction model
  fights against. Plain JS/HTML was rejected because the hook (`useRealtimeSession`)
  has enough state transitions (idle/connecting/connected/listening/speaking, cleanup
  on unmount) that React's state model removes a whole class of manual DOM-sync bugs
  for not much extra setup cost (Vite scaffolds in seconds).

## 8. Frontend structure rationale

- `types.ts` — shared `Slide`/`SessionResponse`/`ConnectionStatus`/`AgentState` types
  used by both `api.ts` and the components, so the UI and the API client can't silently
  drift (e.g. renaming a slide field).
- `api.ts` — the only module that knows the backend's base URL
  (`VITE_API_BASE_URL`, defaulting to `http://localhost:8000` for zero-config local
  dev) and endpoint shapes. Everything else only imports `fetchSlides`/`createSession`.
- `hooks/useRealtimeSession.ts` — all WebRTC/data-channel/event-handling complexity is
  isolated here so `App.tsx` stays a plain state-wiring component. This hook is the
  direct translation of the OpenAI WebRTC guide verified via `WebFetch` against
  `developers.openai.com` (not from potentially-stale training knowledge) — specifically
  the ephemeral client-secret flow, the SDP offer/answer POST to
  `/v1/realtime/calls`, the `"oai-events"` data channel, and the
  `function_call` → `conversation.item.create` (function_call_output) → `response.create`
  round-trip for `show_slide`.
- `components/SlideView.tsx` / `VoiceControls.tsx` — split purely because they're two
  unrelated concerns (slide rendering vs. connection/agent-state UI) with no shared
  state beyond props already passed down from `App.tsx`.
- `vite-env.d.ts` was initially missing (caught post-scaffold) — without it,
  TypeScript doesn't know the ambient `ImportMetaEnv`/`ImportMeta.env` shape, so
  `import.meta.env.VITE_API_BASE_URL` in `api.ts` wouldn't type-check. Fixed by adding
  the standard `/// <reference types="vite/client" />` triple-slash directive (Vite's
  own scaffold always includes this; it was lost because `App.tsx`/CSS were rewritten
  by hand rather than regenerated).
- Deleted Vite's default `frontend/README.md` boilerplate and `frontend/src/assets/`
  (hero/react/vite placeholder images) since `App.tsx` was fully rewritten and no
  longer references them — kept the repo free of dead assets rather than leaving
  unused files "just in case."

## 9. Verification performed

- Backend: `pytest` → 6/6 passing, run inside the project virtualenv.
- Backend (live smoke test, not mocked): started `uvicorn`, called `POST
  /api/session` with the placeholder key against the *real* OpenAI endpoint, confirmed
  it returns a clean `502` with a descriptive error (not a crash/500) — proving the
  graceful-degradation path works end-to-end, not just in a mocked unit test.
- Frontend: `npm run build` (`tsc -b && vite build`) → compiles cleanly, 0 errors,
  produces `dist/`.
- **Not verified** (cannot be, without a real `OPENAI_API_KEY` and a browser
  microphone): the actual voice session — connect → speak → agent response → tool-
  call-driven slide navigation → barge-in interruption. This needs to be smoke-tested
  by hand the moment a real key is dropped into `backend/.env`; README.md has the exact
  steps.

## 10. Tooling issues hit during scaffolding (and fixes)

- `python3 -m venv .venv` failed (`ensurepip is not available... need
  python3.10-venv`) — would have required a `sudo apt install`, which wasn't worth
  doing for a venv. Used the already-installed `virtualenv` binary instead
  (`virtualenv .venv`) — functionally equivalent, no system package needed.
- That `virtualenv` run on this Debian/Ubuntu box places executables under
  `.venv/local/bin/` instead of the usual `.venv/bin/` — a known Debian virtualenv
  packaging quirk (Debian patches venv layout for its own Python packaging reasons).
  Activate via `source backend/.venv/local/bin/activate`, not the usual path.
- `addyosmani/agent-skills` was installed as a Claude Code plugin at **user scope**
  (`claude plugin marketplace add` + `claude plugin install ... -y`, no `--project`
  flag), specifically so the 25-skill pack's files don't end up inside this take-home
  submission repo — it's a working-process aid, not part of the deliverable.

## 11. Git strategy (next step)

- `git init` locally, with a root `.gitignore` covering `backend/.venv/`,
  `__pycache__/`, `.env`/`*.env` (but **not** `*.env.example`), `frontend/node_modules/`,
  `frontend/dist/`, editor/OS cruft.
- Commits are being made in logical chunks (backend, frontend, docs/config) rather
  than one giant initial commit, so the history itself demonstrates the build order —
  useful for a reviewer skimming `git log`.
- No remote/push without explicit confirmation — this file and the repo stay local
  until the user says to create/push to GitHub.
