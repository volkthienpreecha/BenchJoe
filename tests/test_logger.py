import json
from pathlib import Path

from benchjoe.logger import (
    parse_trajectory,
    web_fetches,
    external_fetches,
    bash_commands,
    timed_out,
    save_trajectory,
    load_trajectory,
    TrajectoryEvent,
)


def _make_tool_event(name: str, input_dict: dict) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": name, "input": input_dict}
            ]
        }
    }


def test_parse_web_fetch_event():
    events = [_make_tool_event("WebFetch", {"url": "https://example.com", "prompt": "get it"})]
    trajectory = parse_trajectory(events)
    fetches = web_fetches(trajectory)
    assert len(fetches) == 1
    assert fetches[0].detail == "https://example.com"


def test_web_fetch_to_cve_domain_is_external():
    events = [_make_tool_event("WebFetch", {"url": "https://github.com/google/oss-fuzz/issues/123"})]
    trajectory = parse_trajectory(events)
    ext = external_fetches(trajectory)
    assert len(ext) == 1
    assert ext[0].is_external is True


def test_web_fetch_to_unknown_domain_not_external():
    events = [_make_tool_event("WebFetch", {"url": "https://pypi.org/project/requests"})]
    trajectory = parse_trajectory(events)
    ext = external_fetches(trajectory)
    assert len(ext) == 0


def test_parse_bash_event():
    events = [_make_tool_event("Bash", {"command": "ls -la"})]
    trajectory = parse_trajectory(events)
    cmds = bash_commands(trajectory)
    assert len(cmds) == 1
    assert "ls" in cmds[0].detail


def test_timeout_event():
    events = [{"type": "timeout", "elapsed": 600}]
    trajectory = parse_trajectory(events)
    assert timed_out(trajectory) is True


def test_no_timeout():
    events = [_make_tool_event("Bash", {"command": "echo hi"})]
    trajectory = parse_trajectory(events)
    assert timed_out(trajectory) is False


def test_save_and_load_trajectory(tmp_path):
    events = [
        _make_tool_event("Bash", {"command": "cat description.txt"}),
        _make_tool_event("WebFetch", {"url": "https://github.com/google/oss-fuzz/issues/1"}),
    ]
    trajectory = parse_trajectory(events)
    path = tmp_path / "traj.jsonl"
    save_trajectory(trajectory, path)
    assert path.exists()

    loaded = load_trajectory(path)
    assert len(loaded) == len(trajectory)
    assert loaded[0].kind == trajectory[0].kind


def test_empty_events():
    trajectory = parse_trajectory([])
    assert trajectory == [] or all(e.kind == "text" for e in trajectory)
