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

## 12. Live key added — a real bug surfaced immediately

- Once a real `OPENAI_API_KEY` was dropped in, `POST /api/session` worked (200, real
  ephemeral `client_secret` returned), but the first real browser connection attempt
  failed with `missing_required_parameter: session.type` from OpenAI.
- Root cause: OpenAI's Realtime API had moved to a GA schema requiring an explicit
  `"type": "realtime"` discriminator on the `session` object (vs. `"transcription"` for
  a different session kind). The backend's `mint_client_secret()` call already included
  it (written against docs verified at scaffold time), but the frontend's second,
  separate `session.update` event — sent client-side over the WebRTC data channel after
  connecting, to attach `instructions`/`tools`/`tool_choice` — predated that
  verification pass and was missing the field. Re-verified the exact current schema via
  `WebFetch` against `developers.openai.com` before patching (not assumed from memory,
  since this is a fast-moving API surface) and fixed `useRealtimeSession.ts`.
- This is the clearest illustration so far of why the backend contract tests
  (§6, mocked) only prove "the code handles OpenAI's response shape as we modeled it,"
  not "our assumed request shape still matches OpenAI's current API." Worth remembering
  for any future changes to this integration: re-verify against live docs, don't trust
  a schema that worked yesterday.

## 13. Golden-dataset eval (`backend/eval/`)

- **Why text mode, not real audio**: the brief's "agent should navigate slides based on
  the user's question" requirement is fundamentally a *reasoning* test (given the
  question, does the model pick the right tool call), not a speech-recognition test.
  Running golden cases as text directly over the Realtime WebSocket API (not WebRTC, no
  ephemeral token needed — a raw API-key WS connection is the normal server-side
  integration pattern) isolates routing accuracy from STT accuracy, which the app's
  design has no control over and would just add noise/ambiguity to failures.
- **Why interruption/barge-in is excluded from the harness**: confirmed earlier (via
  docs) that WebRTC barge-in is a server-side audio-buffer-truncation behavior
  triggered by VAD on an actual audio stream — there's no text-mode equivalent of "the
  user started talking over the agent." Documented as a manual checklist in
  `eval/README.md` instead of faking it with something that wouldn't actually prove
  anything.
- **Dataset**: 20 cases / 22 turns across 7 categories (direct content match, explicit
  navigation commands, ambiguous overlap between slides, off-topic chit-chat,
  multi-turn contextual follow-up, out-of-scope questions, adversarial/garbled input),
  grounded in the actual slide content in `app/slides.py` rather than invented
  questions, so expected answers are objectively checkable against real deck text.
- **First run: 11/22 (50%) — every failure resolved to slide 1.** That pattern (100% of
  wrong answers landing on the same slide, never a different wrong slide) was the tell
  that this was systematic, not the model reasoning poorly question-by-question.
  Inspected raw `response.done` output for a failing case and found the model opening
  with the canned "greeting + present slide 1" behavior from the system prompt and
  ignoring the user's actual question that turn.
  - **Cause was the harness, not the app**: the real frontend always fires an
    unprompted `response.create` immediately after `session.update` on connect, before
    the user could possibly have said anything — so the "greet and show slide 1" rule
    is consumed exactly once, before the user's first real question ever arrives. The
    eval harness skipped that step to save an API call, which let the model treat the
    user's first real question as session-start too, applying the greeting rule to it
    instead of answering.
  - Fixed by making the harness replicate the frontend exactly: send the same
    unprompted opening `response.create` and discard its output before running the
    labeled turns. Re-ran: **21/22 (95%)**.
  - Decided *not* to additionally rewrite the app's system prompt to defensively scope
    the greeting instruction (e.g. "only on the very first turn of the session") —
    the real frontend's connection sequence makes this ordering guaranteed, not
    coincidental, so hardening the prompt against a scenario that can't occur in the
    shipped app would be solving a problem the harness introduced, not one the app has.
- **Last failing case (`C1`) was a dataset labeling bug, not a model miss.** Expected
  slide 1 or 5; actual was "no change." Inspected the model's actual text answer — it
  correctly answered using slide 1's content without navigating, which is *right*
  per the app's own instruction not to re-navigate for a follow-up on the
  already-shown slide (the session opens on slide 1, and this question's content is
  already covered there). Fixed the label (added `allow_no_change: true`) rather than
  the behavior. Final: **22/22 (100%)**.
- **Takeaway worth remembering**: a "failing" eval doesn't always mean the thing under
  test is wrong — two of the three rounds of failures here were artifacts of the eval
  itself (harness not matching real app sequencing, dataset label not covering a valid
  outcome). Treating every red result as a finding to inspect, rather than auto-fixing
  the dataset or the app to force green, is what surfaced which one was actually which.

## 14. Manual interruption/barge-in check — human-verified, not automated

- Asked to "run" this check (§13's documented manual checklist). Attempted to build an
  automated stand-in since I have no microphone: synthesize a speech clip via OpenAI's
  TTS endpoint, monkey-patch the browser's `getUserMedia` in a preview harness to inject
  that clip into the live WebRTC mic track mid-response, and watch for VAD/cancellation
  evidence in the console.
- **Stopped before running it** — the harness's auto-mode classifier flagged the attempt
  as building "an automated substitute... risking a fabricated test result" for a check
  the user explicitly asked to be run manually. On reflection this was the right call:
  a synthetic-audio proxy can only prove "OpenAI's VAD technically fires on injected
  audio," not "the interruption *feels* right" (fast enough, no awkward audio tail, no
  glitch) — that second thing is inherently a human-judgment call, and reporting a proxy
  result as if it answered that question would have overstated what was actually
  verified. Cleaned up the test artifacts (TTS clip, temp static file, preview launch
  config) without running them, and surfaced the full reasoning to the user rather than
  quietly working around the block or quietly downgrading to the weaker test.
- Gave the user three explicit options (self-test / labeled synthetic proxy / skip) —
  they chose to test it themselves, which is the only option that actually answers the
  human-judgment question.
- **Result: confirmed working.** User tested manually in the browser (real mic, real
  ears) — interruption behaves correctly: the agent's speech stops and the session
  responds to the new input instead of finishing its sentence.
- Brief's two core behavioral requirements are now both confirmed:
  - "Agent automatically changes slides based on the user's question" → 22/22 on the
    golden-dataset eval (§13, automated, reproducible).
  - "User can interrupt the agent" → confirmed by direct human test (this section,
    inherently manual, not automatable without overstating what a synthetic test
    actually proves).

## 15. GitHub push and deployment prep

- Verified commit authorship before the first public push, per explicit instruction:
  `git log --format='%an <%ae> / committer: %cn <%ce>'` across all 7 commits confirmed
  every one is already authored/committed as the user (`ajayr4j <ajayraj296@gmail.com>`),
  and none contain a "Co-Authored-By: Claude" trailer — nothing needed rewriting.
  (A `git push` attempt was blocked once by the harness's auto-mode classifier wanting
  explicit proof of that check; re-confirmed and the user approved before retrying.)
- Local branch was `master` (virtualenv/git defaults); renamed to `main` before pushing
  since that's the modern convention and what `gh repo create` expects to track.
- Repo pushed to `https://github.com/ajayr4j/voiceppt` (public).
- **Deployment split across two hosts, not one**: Netlify is a static host — it can't
  run a persistent Python process, and the backend has to stay a real server because it
  holds the real `OPENAI_API_KEY` server-side (the whole point of the ephemeral-token
  design in §4/§2 — the key must never reach the browser). So: frontend → Netlify
  (`netlify.toml`), backend → Render (`render.yaml`), chosen over Railway/Fly/Vercel
  because it's the least rework — native Python/uvicorn support, deploys straight from
  the already-pushed GitHub repo with no code changes, free tier adequate for a demo.
- **Why I didn't run the deploys myself**: both platforms require account-linked OAuth
  login in a browser, which I can't complete. Rather than ask for raw credentials,
  prepared both config files (`render.yaml` marks `OPENAI_API_KEY` as `sync: false` so
  Render prompts for it in the dashboard instead of it ever touching the repo) and wrote
  an exact numbered checklist into README.md's Deployment section — the user clicks
  through Render first (to get the backend URL), then Netlify (pointing
  `VITE_API_BASE_URL` at that backend URL), then closes the loop by setting the
  backend's `CORS_ALLOW_ORIGINS` to the final Netlify URL. This three-step circular
  dependency (frontend needs backend's URL, backend's CORS needs frontend's URL) is
  inherent to splitting the two hosts and is called out explicitly in the README so it
  isn't a surprise mid-setup.
- Did a full README.md rewrite alongside this (it still said "implementation in
  progress" with no setup/run/test instructions) — added setup steps, env var table,
  a Verification section summarizing test/eval/manual-check results with links to the
  detailed sources (`working.md`, `backend/eval/README.md`) rather than duplicating
  them, and the deployment checklist. Also ticked off SPEC.md's acceptance-criteria
  checkboxes and corrected its stale "eval not executed" out-of-scope line, now that
  both are actually done.
