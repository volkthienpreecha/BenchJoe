"""
logger.py — Parse Claude Code stream-json events into a structured trajectory.

A trajectory is a list of TrajectoryEvent dicts, each representing one
meaningful action the agent took: a tool call, a web fetch, a bash command,
a file operation, or a text message.

This is the key difference from just measuring pass/fail — the trajectory
tells us HOW the agent solved (or failed to solve) the task.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import json

# Domains that indicate the agent found public vulnerability info online
KNOWN_CVE_DOMAINS = {
    "issues.oss-fuzz.com",
    "bugs.chromium.org",
    "github.com",
    "cve.mitre.org",
    "nvd.nist.gov",
    "osv.dev",
    "security.googleblog.com",
    "exploit-db.com",
    "vuldb.com",
    "cvedetails.com",
    "packetstormsecurity.com",
    "seclists.org",
    "bugzilla.redhat.com",
    "bugzilla.mozilla.org",
}


@dataclass
class TrajectoryEvent:
    kind: str           # tool_call | web_fetch | bash | file_op | text | timeout
    name: str = ""      # tool name or description
    detail: str = ""    # command, URL, filename, or text snippet
    is_external: bool = False  # True if web_fetch to a known CVE domain


def parse_trajectory(events: list[dict]) -> list[TrajectoryEvent]:
    """
    Convert raw stream-json events into a structured trajectory.
    """
    trajectory: list[TrajectoryEvent] = []

    for event in events:
        etype = event.get("type", "")

        if etype == "timeout":
            trajectory.append(TrajectoryEvent(kind="timeout"))
            continue

        if etype == "assistant":
            message = event.get("message", {})
            for block in message.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    traj = _parse_tool_use(block)
                    if traj:
                        trajectory.append(traj)

        # text blocks from assistant (summaries / reasoning)
        if etype == "assistant":
            message = event.get("message", {})
            for block in message.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        trajectory.append(TrajectoryEvent(
                            kind="text",
                            detail=text[:300],  # truncate for storage
                        ))

    return trajectory


def _parse_tool_use(block: dict) -> TrajectoryEvent | None:
    name = block.get("name", "")
    inp = block.get("input", {})

    if name == "WebFetch":
        url = inp.get("url", "")
        is_external = _is_cve_domain(url)
        return TrajectoryEvent(
            kind="web_fetch",
            name="WebFetch",
            detail=url,
            is_external=is_external,
        )

    if name in ("Bash", "bash"):
        cmd = inp.get("command", "")
        return TrajectoryEvent(kind="bash", name="Bash", detail=cmd[:300])

    if name in ("Read", "Write", "Edit", "Glob", "Grep"):
        path = inp.get("file_path", inp.get("path", inp.get("pattern", "")))
        return TrajectoryEvent(kind="file_op", name=name, detail=str(path))

    if name == "WebSearch":
        query = inp.get("query", "")
        return TrajectoryEvent(kind="web_fetch", name="WebSearch", detail=query)

    # Any other tool — record generically
    return TrajectoryEvent(kind="tool_call", name=name, detail=str(inp)[:200])


def _is_cve_domain(url: str) -> bool:
    """Return True if the URL points to a known vulnerability info domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in KNOWN_CVE_DOMAINS)


def web_fetches(trajectory: list[TrajectoryEvent]) -> list[TrajectoryEvent]:
    """Return only web fetch events from the trajectory."""
    return [e for e in trajectory if e.kind == "web_fetch"]


def external_fetches(trajectory: list[TrajectoryEvent]) -> list[TrajectoryEvent]:
    """Return web fetches to known CVE/vulnerability domains."""
    return [e for e in trajectory if e.kind == "web_fetch" and e.is_external]


def bash_commands(trajectory: list[TrajectoryEvent]) -> list[TrajectoryEvent]:
    """Return all bash command events."""
    return [e for e in trajectory if e.kind == "bash"]


def timed_out(trajectory: list[TrajectoryEvent]) -> bool:
    return any(e.kind == "timeout" for e in trajectory)


def save_trajectory(trajectory: list[TrajectoryEvent], path: Path) -> None:
    """Save trajectory as JSONL — one event per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for event in trajectory:
            f.write(json.dumps(asdict(event)) + "\n")


def load_trajectory(path: Path) -> list[TrajectoryEvent]:
    """Load a trajectory from a JSONL file."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(TrajectoryEvent(**json.loads(line)))
    return events
