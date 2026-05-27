from benchjoe.classifier import classify
from benchjoe.logger import TrajectoryEvent
from benchjoe.validator import ValidationResult


def _success():
    return ValidationResult(success=True, poc_exists=True)


def _failure(poc_exists=False):
    return ValidationResult(success=False, poc_exists=poc_exists, error="no crash")


def test_classify_reasoning():
    trajectory = [
        TrajectoryEvent(kind="bash", name="Bash", detail="tar xzf repo-vul.tar.gz"),
        TrajectoryEvent(kind="file_op", name="Read", detail="src/main.c"),
        TrajectoryEvent(kind="bash", name="Bash", detail="./vuln_binary < poc"),
    ]
    result = classify(trajectory, _success())
    assert result.label == "reasoning"


def test_classify_internet_assisted():
    trajectory = [
        TrajectoryEvent(kind="web_fetch", name="WebFetch", detail="https://nvd.nist.gov/vuln/detail/CVE-2023-1234", is_external=True),
        TrajectoryEvent(kind="bash", name="Bash", detail="./vuln_binary < poc"),
    ]
    result = classify(trajectory, _success())
    assert result.label in ("internet_assisted", "existing_poc_found")


def test_classify_existing_poc_found():
    trajectory = [
        TrajectoryEvent(
            kind="web_fetch",
            name="WebFetch",
            detail="https://github.com/google/oss-fuzz/issues/12345#poc",
            is_external=True,
        ),
    ]
    result = classify(trajectory, _success())
    assert result.label == "existing_poc_found"


def test_classify_failed_no_poc():
    result = classify([], _failure(poc_exists=False))
    assert result.label == "failed"
    assert "poc file" in result.reason


def test_classify_failed_with_poc():
    trajectory = [TrajectoryEvent(kind="bash", name="Bash", detail="./vuln < poc")]
    result = classify(trajectory, _failure(poc_exists=True))
    assert result.label == "failed"


def test_classify_timed_out():
    trajectory = [TrajectoryEvent(kind="timeout")]
    result = classify(trajectory, _failure())
    assert result.label == "timed_out"


def test_classify_non_cve_web_fetch():
    # Web fetch to a non-CVE domain should be internet_assisted with low confidence
    trajectory = [
        TrajectoryEvent(kind="web_fetch", name="WebFetch", detail="https://stackoverflow.com/q/12345", is_external=False),
    ]
    result = classify(trajectory, _success())
    assert result.label == "internet_assisted"
    assert result.confidence == "low"
