"""Golden-dataset eval for slide-routing accuracy.

Tests the model's show_slide tool-calling decisions against a labeled set of
user utterances, using the exact instructions/tools the real app builds from
app/slides.py. Runs in TEXT mode directly over the Realtime WebSocket API
(not audio/WebRTC) to isolate routing/reasoning accuracy from speech-
recognition accuracy - the latter is a separately-solved problem the deck's
prompt/tool design has no influence over.

Makes real calls against OPENAI_API_KEY in backend/.env (small cost, a few
cents for the full dataset).

Usage:
    source .venv/local/bin/activate
    python eval/run_eval.py
"""

import asyncio
import json
import sys
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.slides import build_instructions, build_tools

WS_URL = f"wss://api.openai.com/v1/realtime?model={settings.realtime_model}"
DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.json"


def _extract_show_slide_call(response: dict) -> int | None:
    for item in response.get("output", []):
        if item.get("type") == "function_call" and item.get("name") == "show_slide":
            return json.loads(item["arguments"]).get("slide_number")
    return None


def _grade_turn(turn: dict, actual_slide: int | None) -> dict:
    expected = turn["expected"]
    etype = expected["type"]
    if etype == "specific":
        passed = actual_slide == expected["slide_id"]
    elif etype == "any_of":
        passed = actual_slide in expected["slide_ids"] or (
            expected.get("allow_no_change") and actual_slide is None
        )
    elif etype == "no_change":
        passed = actual_slide is None
    else:
        raise ValueError(f"unknown expected type: {etype}")
    return {
        "user_text": turn["user_text"],
        "expected": expected,
        "actual_slide": actual_slide,
        "passed": passed,
    }


async def run_case(case: dict) -> dict:
    turn_results = []
    async with websockets.connect(
        WS_URL,
        additional_headers={"Authorization": f"Bearer {settings.openai_api_key}"},
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "type": "realtime",
                        "instructions": build_instructions(),
                        "tools": build_tools(),
                        "tool_choice": "auto",
                    },
                }
            )
        )

        # Mirrors the real frontend: it fires an unprompted response.create
        # immediately on connect, before the user can have said anything, so
        # the "greet + present slide 1" instruction is consumed exactly once
        # here - not on the user's first real question below.
        await ws.send(
            json.dumps({"type": "response.create", "response": {"output_modalities": ["text"]}})
        )
        async for raw in ws:
            event = json.loads(raw)
            if event["type"] in ("response.done", "error"):
                break

        for turn in case["turns"]:
            await ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": turn["user_text"]}],
                        },
                    }
                )
            )
            await ws.send(
                json.dumps({"type": "response.create", "response": {"output_modalities": ["text"]}})
            )

            actual_slide = None
            turn_error = None
            async for raw in ws:
                event = json.loads(raw)
                if event["type"] == "response.done":
                    actual_slide = _extract_show_slide_call(event["response"])
                    break
                if event["type"] == "error":
                    turn_error = event["error"]
                    break

            if turn_error:
                turn_results.append(
                    {"user_text": turn["user_text"], "expected": turn["expected"], "error": turn_error, "passed": False}
                )
            else:
                turn_results.append(_grade_turn(turn, actual_slide))

    return {"id": case["id"], "category": case["category"], "turns": turn_results}


def _print_summary(results: list[dict]) -> None:
    total = 0
    passed = 0
    by_category: dict[str, list[int]] = {}
    failures = []

    for case in results:
        for turn in case["turns"]:
            total += 1
            counts = by_category.setdefault(case["category"], [0, 0])
            counts[1] += 1
            if turn.get("passed"):
                passed += 1
                counts[0] += 1
            else:
                failures.append((case["id"], turn))

    print("\n=== Golden Dataset Eval Summary ===")
    print(f"Overall: {passed}/{total} ({passed / total:.0%})\n")
    print(f"{'Category':28s} Pass")
    for cat, (p, t) in sorted(by_category.items()):
        print(f"{cat:28s} {p}/{t}")

    if failures:
        print("\n--- Failures ---")
        for case_id, turn in failures:
            print(f'[{case_id}] "{turn["user_text"]}"')
            print(f"    expected: {turn['expected']}")
            if "error" in turn:
                print(f"    error: {turn['error']}")
            else:
                print(f"    actual_slide: {turn.get('actual_slide')}")
    else:
        print("\nAll cases passed.")


async def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text())
    results = []
    for case in dataset:
        print(f"Running {case['id']} ({case['category']})...", flush=True)
        results.append(await run_case(case))

    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    _print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
