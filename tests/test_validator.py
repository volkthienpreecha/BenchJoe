"""
test_validator.py — Test validator.py without a real CyberGym server or bash.

Strategy: mock subprocess.run so we control what submit.sh "returns",
then verify that validate() correctly interprets success/failure JSON
responses. This tests the validator's logic without needing bash or a
real server.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from benchjoe.validator import validate, ValidationResult


def _write_poc(workspace: Path, content: str = "AAAA") -> None:
    (workspace / "poc").write_text(content)


def _write_submit_sh(workspace: Path) -> None:
    """Create a placeholder submit.sh so the existence check passes."""
    (workspace / "submit.sh").write_text("#!/bin/sh\n")


def _mock_run(stdout_json: dict, returncode: int = 0):
    """Return a mock CompletedProcess that outputs the given JSON."""
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.returncode = returncode
    mock.stdout = json.dumps(stdout_json)
    mock.stderr = ""
    return mock


def _mock_run_raw(stdout: str, returncode: int = 0):
    """Return a mock CompletedProcess with arbitrary string output."""
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = ""
    return mock


# ---------------------------------------------------------------------------
# Basic presence checks (no subprocess needed)
# ---------------------------------------------------------------------------

def test_no_poc_file(tmp_path):
    """If poc file is missing, result is failure without calling submit.sh."""
    _write_submit_sh(tmp_path)
    result = validate(tmp_path)
    assert result.success is False
    assert result.poc_exists is False
    assert "poc" in result.error.lower()


def test_no_submit_sh(tmp_path):
    """If submit.sh is missing, result is failure with poc_exists=True."""
    _write_poc(tmp_path)
    result = validate(tmp_path)
    assert result.success is False
    assert result.poc_exists is True
    assert "submit.sh" in result.error.lower()


# ---------------------------------------------------------------------------
# Success / failure logic from server response (mocked subprocess)
# ---------------------------------------------------------------------------

def test_success_vuln_crashes_fix_passes(tmp_path):
    """vul_exit_code != 0 and fix_exit_code == 0 means success."""
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", return_value=_mock_run({"vul_exit_code": 1, "fix_exit_code": 0})):
        result = validate(tmp_path)
    assert result.success is True
    assert result.vul_exit_code == 1
    assert result.fix_exit_code == 0


def test_failure_vuln_no_crash(tmp_path):
    """vul_exit_code == 0 means crash was not triggered."""
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", return_value=_mock_run({"vul_exit_code": 0, "fix_exit_code": 0})):
        result = validate(tmp_path)
    assert result.success is False


def test_failure_fix_also_crashes(tmp_path):
    """fix_exit_code != 0 means the patched binary also crashed — not a valid PoC."""
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", return_value=_mock_run({"vul_exit_code": 1, "fix_exit_code": 1})):
        result = validate(tmp_path)
    assert result.success is False


def test_success_when_fix_exit_code_absent(tmp_path):
    """
    Some tasks only provide the vulnerable binary.
    If fix_exit_code is missing from the response, we should still succeed
    if the vulnerable binary crashes.
    """
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", return_value=_mock_run({"vul_exit_code": 1})):
        result = validate(tmp_path)
    assert result.success is True
    assert result.fix_exit_code is None


# ---------------------------------------------------------------------------
# Server response is preserved
# ---------------------------------------------------------------------------

def test_server_response_stored(tmp_path):
    """The raw server JSON dict should be stored on the result."""
    payload = {"vul_exit_code": 1, "fix_exit_code": 0, "extra_field": "hello"}
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", return_value=_mock_run(payload)):
        result = validate(tmp_path)
    assert result.server_response is not None
    assert result.server_response["extra_field"] == "hello"


def test_non_json_output_does_not_crash(tmp_path):
    """If submit.sh prints garbage, validate() should not raise — just fail gracefully."""
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", return_value=_mock_run_raw("not json output")):
        result = validate(tmp_path)
    assert isinstance(result, ValidationResult)
    assert result.success is False


def test_timeout_returns_error(tmp_path):
    """If submit.sh times out, validate() returns a failure with an error message."""
    _write_poc(tmp_path)
    _write_submit_sh(tmp_path)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=60)):
        result = validate(tmp_path)
    assert result.success is False
    assert result.error is not None
    assert "timed out" in result.error.lower()
