# Voice Slide Agent — Take-Home Prototype

> Status: architecture locked, implementation in progress. This README will fill in with setup/run instructions as the app is built.

## Overview
A voice-driven slide presentation app. The AI agent presents a 5-6 slide deck on a chosen topic, listens via voice, answers questions, automatically navigates to the relevant slide based on what's asked, and can be interrupted mid-response by the user.

**Stack:** FastAPI backend (serves slide data, mints ephemeral session tokens) + React frontend (renders slides, handles audio session, reacts to tool calls). Voice pipeline: OpenAI Realtime API over WebRTC, direct browser↔OpenAI connection.

---

## Appendix: Self-Hosted Alternative (Production Consideration)

This prototype uses OpenAI's Realtime API (cloud, hosted) because it was the fastest path to a working demo within the assessment's timeline. That's the right call for a 2-day prototype, but **not necessarily the right call for every production deployment** — in particular, a pharma customer whose security/compliance team won't allow voice audio to leave their VPC would rule out any third-party cloud voice API outright. For that scenario, the open-source self-hosted path below is the real proposal.

**Option 1 — Moshi (Kyutai), Apache-2.0, open weights:**
A genuinely full-duplex speech-to-speech foundation model, runnable on your own GPU (≈160ms theoretical / ≈200ms practical latency on an L4). Architecturally the closest open equivalent to OpenAI/Gemini's realtime models.
Limitation: it's built for natural spoken dialogue, not agentic tool-calling — there's no first-class "emit a structured function call mid-response" the way the cloud realtime APIs support. Using it here would mean inferring slide-routing intent from its text stream rather than a native tool call, which reintroduces the exact transcript-classification approach this project's architecture decisions deliberately avoided.

**Option 2 — Pipecat or LiveKit Agents (self-hosted orchestration frameworks, Apache-2.0):**
Assemble a cascaded pipeline yourself from self-hosted components — Whisper/faster-whisper (STT) → any function-calling-capable LLM (self-hosted via Ollama/vLLM, or still a hosted API if only the audio needs to stay local) → Piper/Kokoro/XTTS (TTS). Both frameworks handle interruption generically at the pipeline level (VAD-triggered cancellation of in-flight LLM/TTS tasks), so barge-in doesn't need to be hand-rolled. Since the LLM stage is a normal function-calling model, slide-routing via tool calls works exactly as designed in this project — this is the more complete open-source match to the actual requirements.
Trade-off: still a cascaded architecture (latency stacks across STT→LLM→TTS), and now you own GPU provisioning and model-serving ops for every component instead of a vendor doing it.

**When to actually reach for this:** data-residency/VPC-only requirements, strict regulatory constraints on where audio/PHI can be processed, or cost at a scale where the cloud API's per-minute pricing compounds meaningfully. Not for a quick prototype or pilot where proving the interaction model matters more than deployment topology.
