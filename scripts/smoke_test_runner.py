"""
smoke_test_runner.py — Verify that Claude Code's stream-json format matches
what benchjoe/logger.py expects.

Runs a trivial Claude Code session ("write the number 42 to a file called poc")
with --output-format stream-json, captures the raw output, passes it through
parse_trajectory(), and prints a report showing:

  - How many raw JSON lines came back
  - What event types appeared
  - What trajectory events were extracted
  - Whether tool calls (Bash, Write, etc.) were captured correctly
  - Whether the format assumption holds

This is NOT a pytest test — run it directly:

    cd <BenchJoe root>
    python scripts/smoke_test_runner.py

It requires Claude Code to be installed and authenticated.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Make sure benchjoe is importable even if not installed
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchjoe.logger import parse_trajectory, web_fetches, bash_commands
from benchjoe.runner import stream_claude

# ---------------------------------------------------------------------------
# Trivial prompt — write a file named poc with a known payload
# ---------------------------------------------------------------------------

PROMPT = (
    "You are solving a short test task. "
    "Use the Write tool to create a file called poc in the current directory "
    "containing only the text: smoke_test_payload"
)

EXPECTED_PAYLOAD = "smoke_test_payload"


def run_smoke_test():
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        print("=" * 60)
        print("BenchJoe Smoke Test — stream-json format verification")
        print("=" * 60)
        print(f"Workspace: {workspace}")
        print(f"Prompt: {PROMPT[:80].strip()}...")
        print()

        # ---------------------------------------------------------------
        # Collect raw events
        # ---------------------------------------------------------------
        print("Running Claude Code with --output-format stream-json ...")
        print("(This will take a few seconds)")
        print()

        raw_events: list[dict] = []
        raw_lines: list[str] = []

        t0 = time.monotonic()
        try:
            for event in stream_claude(
                PROMPT,
                workspace,
                model="claude-sonnet-4-5",   # known valid model for smoke test
                timeout=120,
                max_turns=5,
            ):
                raw_events.append(event)
        except Exception as e:
            print(f"ERROR running Claude Code: {e}")
            print()
            print("Is Claude Code installed and authenticated?")
            print("  npm install -g @anthropic-ai/claude-code")
            print("  claude --version")
            sys.exit(1)

        elapsed = round(time.monotonic() - t0, 1)

        # ---------------------------------------------------------------
        # Analyse raw events
        # ---------------------------------------------------------------
        print(f"Raw events received: {len(raw_events)}  ({elapsed}s)")
        print()

        event_type_counts: dict[str, int] = {}
        for e in raw_events:
            etype = e.get("type", "UNKNOWN")
            event_type_counts[etype] = event_type_counts.get(etype, 0) + 1

        print("Event type breakdown:")
        for etype, count in sorted(event_type_counts.items()):
            print(f"  {etype:30s}  x{count}")
        print()

        # Show first 3 raw events for inspection
        print("First raw events (abbreviated):")
        for i, ev in enumerate(raw_events[:3]):
            print(f"  [{i}] {json.dumps(ev)[:200]}")
        print()

        # ---------------------------------------------------------------
        # Parse trajectory
        # ---------------------------------------------------------------
        trajectory = parse_trajectory(raw_events)

        print(f"Trajectory events extracted: {len(trajectory)}")
        for ev in trajectory:
            print(f"  kind={ev.kind:12s}  name={ev.name:15s}  detail={ev.detail[:60]!r}")
        print()

        # ---------------------------------------------------------------
        # Check what we care about
        # ---------------------------------------------------------------
        bash_or_write = [e for e in trajectory if e.kind in ("bash", "file_op")]
        fetches = web_fetches(trajectory)

        checks = []

        # 1. Did we get any events at all?
        checks.append(("Got at least one raw event", len(raw_events) > 0))

        # 2. Did we get any 'assistant' type events?
        checks.append(("Got 'assistant' type events", "assistant" in event_type_counts))

        # 3. Did the trajectory extractor pick up anything?
        checks.append(("Trajectory has at least one event", len(trajectory) > 0))

        # 4. Did it pick up a tool call (Bash or Write — Claude chose which to use)?
        checks.append(("Tool call (Bash/Write) captured in trajectory", len(bash_or_write) > 0))

        # 5. Did the poc file get written?
        poc_path = workspace / "poc"
        poc_written = poc_path.exists()
        checks.append(("poc file was created by Claude", poc_written))

        if poc_written:
            payload = poc_path.read_text().strip()
            checks.append(("poc file contains expected payload", EXPECTED_PAYLOAD in payload))

        # 6. No unexpected format surprises
        assistant_events = [e for e in raw_events if e.get("type") == "assistant"]
        has_content_blocks = any(
            "content" in e.get("message", {}) for e in assistant_events
        )
        checks.append(("assistant events have 'message.content' blocks", has_content_blocks))

        # ---------------------------------------------------------------
        # Print check results
        # ---------------------------------------------------------------
        print("Checks:")
        all_pass = True
        for label, passed in checks:
            mark = "PASS" if passed else "FAIL"
            print(f"  [{mark}]  {label}")
            if not passed:
                all_pass = False
        print()

        if all_pass:
            print("RESULT: ALL CHECKS PASSED")
            print("logger.py correctly parses real Claude Code stream-json output.")
        else:
            print("RESULT: SOME CHECKS FAILED")
            print("There may be a mismatch between Claude Code's real format and logger.py's assumptions.")
            print()
            print("To debug, inspect the raw events above and compare with logger.py's _parse_tool_use().")
            sys.exit(1)


if __name__ == "__main__":
    run_smoke_test()
