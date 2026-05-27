"""
fetcher.py — Set up a CyberGym task workspace locally.

Calls cybergym.task.gen_task (which must be installed) to produce:
  workspace/
    description.txt   — vulnerability description
    README.md         — task instructions (structured, CyberGym format)
    repo-vul.tar.gz   — vulnerable source repo archive
    submit.sh         — submission script (calls CyberGym server)

BenchJoe reads the description and repo; it does NOT use the README.md
as the agent prompt — that is the structured CyberGym format.
The natural-language prompt is built separately by prompt.py.
"""

import subprocess
import sys
from pathlib import Path


def fetch_task(
    task_id: str,
    *,
    cybergym_data_dir: Path,
    server: str,
    workspaces_dir: Path,
    mask_map: str | None = None,
    difficulty: str = "level1",
    agent_id: str | None = None,
) -> Path:
    """
    Generate a CyberGym task workspace via cybergym.task.gen_task.

    Returns the path to the workspace directory.
    """
    task_slug = task_id.replace(":", "_")
    task_dir = workspaces_dir / task_slug
    task_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "cybergym.task.gen_task",
        "--task-id", task_id,
        "--out-dir", str(task_dir),
        "--data-dir", str(cybergym_data_dir),
        "--server", server,
        "--difficulty", difficulty,
    ]
    if mask_map:
        cmd += ["--mask-map", mask_map]
    if agent_id:
        cmd += ["--agent-id", agent_id]

    subprocess.run(cmd, check=True)
    return task_dir


def workspace_ready(task_dir: Path) -> bool:
    """Return True if the workspace has the minimum expected files."""
    return (task_dir / "description.txt").exists() and (task_dir / "submit.sh").exists()


def read_description(task_dir: Path) -> str:
    """Return the raw vulnerability description text."""
    path = task_dir / "description.txt"
    if not path.exists():
        raise FileNotFoundError(f"description.txt not found in {task_dir}")
    return path.read_text(encoding="utf-8").strip()


def read_error_output(task_dir: Path) -> str | None:
    """Return the error.txt content if present (level2+ tasks)."""
    path = task_dir / "error.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None
