# stack.md - Development Environment & Tooling

This file is about how this project was built (the dev environment and AI
tooling), not what it's built from. For the application's own runtime tech
stack (FastAPI, React, OpenAI Realtime API, etc.), see `README.md`'s "How it
works" and "Setup & running locally" sections. This is kept separate on
purpose: README is for anyone running or reviewing the app, `stack.md` is
for anyone curious about the build process itself.

## AI pair-programming

- **Claude Code** (Anthropic's agentic CLI) was the primary interface for
  this entire project, start to finish: scaffolding both backend and
  frontend, writing tests, building and running the golden-dataset eval,
  diagnosing live bugs (including a live API schema-drift issue and a
  deployed-environment CORS bug), and drafting all documentation.
- **Agent Skills** (`addyosmani/agent-skills`, v0.6.13), a Claude Code plugin
  by Addy Osmani packaging senior-engineer workflows (spec-first,
  incremental implementation, verify-don't-assume, etc.) as invokable
  skills. Its `using-agent-skills` meta-skill shaped the working style
  throughout, even without every phase being invoked as an explicit slash
  command: writing `SPEC.md` before scaffolding code, logging the rationale
  behind every non-obvious decision in `working.md` as it was made rather
  than after the fact, surfacing assumptions and trade-offs instead of
  silently picking one, and treating "it compiles" as insufficient. Every
  claim of "done" in this repo is backed by a passing test, a real API eval
  run, or a manual check actually performed, not just that the code looks
  right.
- **Claude in Chrome** (browser extension/MCP), used specifically for the
  one class of problem that couldn't be diagnosed from the terminal: the
  live deployed site returning "Failed to fetch." Used to navigate to the
  deployed Netlify URL and inspect real network requests and console
  output, then to open the Render dashboard to find and correct the actual
  live `CORS_ALLOW_ORIGINS` value, which turned out to differ from what was
  committed in `render.yaml`. Documented in `working.md` section 16.

## Local dev environment

- OS: Ubuntu 22.04 LTS
- Python 3.10, via `virtualenv` (`backend/.venv`). Note the Debian/Ubuntu
  venv layout puts the activate script at `.venv/local/bin/activate`, not
  the usual `.venv/bin/activate`; both are called out in `README.md`.
- Node v22 (via nvm) locally; `netlify.toml` pins `NODE_VERSION=20` for the
  actual Netlify build, to keep the deployed build reproducible regardless
  of the local machine's Node version.
- `git` + GitHub CLI (`gh`), used to create the `ajayr4j/voiceppt` GitHub
  repo and push, rather than doing it through the GitHub web UI.

## Process notes worth calling out

- Every commit in this repo's history is authored and committed as the
  repo owner (`ajayr4j <ajayraj296@gmail.com>`), never attributed to
  Claude, with no `Co-Authored-By` trailers. This was maintained as a hard
  rule throughout development, including when it meant stopping to
  re-verify authorship before a push rather than proceeding on assumption.
- Decisions that turned out to be wrong are left in `working.md` alongside
  the correction (for example, the assumption that `render.yaml` always
  re-syncs a dashboard-edited env var, which live debugging proved false)
  rather than quietly rewritten. The log is a record of what was actually
  learned, not a cleaned-up retelling.
