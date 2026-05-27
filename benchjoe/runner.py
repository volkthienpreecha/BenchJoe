"""
runner.py — Run Claude Code against a task workspace without isolation.

Key differences from CyberGym's agent execution:
  - No Docker container: runs directly on the host
  - No Squid proxy: full unrestricted internet access
  - No permission prompts: --dangerously-skip-permissions
  - stream-json output: every tool call captured for trajectory logging

The agent writes its PoC to `workspace/poc`.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator


def stream_claude(
    prompt: str,
    workspace: Path,
    *,
    model: str = "claude-opus-4-7",
    timeout: int = 600,
    max_turns: int = 50,
) -> Iterator[dict]:
    """
    Yield stream-json events from a Claude Code session.

    Runs `claude` directly on the host with no network restrictions.
    Each yielded dict is one parsed JSON event line.
    """
    cmd = [
        "claude",
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--model", model,
        "--max-turns", str(max_turns),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    deadline = time.monotonic() + timeout
    try:
        for line in proc.stdout:
            if time.monotonic() > deadline:
                proc.kill()
                yield {"type": "timeout", "elapsed": timeout}
                return
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON lines (e.g. stderr mixed in) — skip
                pass
    finally:
        proc.wait()


def run_task(
    prompt: str,
    workspace: Path,
    *,
    model: str = "claude-opus-4-7",
    timeout: int = 600,
    max_turns: int = 50,
) -> tuple[list[dict], float]:
    """
    Run a full Claude Code session and return (events, wall_clock_seconds).

    This is the main entry point. Collects all stream-json events into a list
    so they can be passed to the logger and classifier.
    """
    start = time.monotonic()
    events = list(stream_claude(
        prompt,
        workspace,
        model=model,
        timeout=timeout,
        max_turns=max_turns,
    ))
    elapsed = round(time.monotonic() - start, 2)
    return events, elapsed
