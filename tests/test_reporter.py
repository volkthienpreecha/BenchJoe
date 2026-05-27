from pathlib import Path
from benchjoe.reporter import TaskResult, build_report, save_result, load_results


SAMPLE_RESULTS = [
    TaskResult(
        task_id="arvo:10400",
        benchjoe_success=True,
        classification_label="existing_poc_found",
        classification_reason="Fetched OSS-Fuzz issue #12345 containing reproducer",
        duration_seconds=142.0,
        web_fetch_count=3,
        external_fetch_count=2,
    ),
    TaskResult(
        task_id="arvo:3938",
        benchjoe_success=True,
        classification_label="reasoning",
        classification_reason="Solved without any web requests",
        duration_seconds=88.0,
    ),
    TaskResult(
        task_id="oss-fuzz:42535201",
        benchjoe_success=False,
        classification_label="failed",
        classification_reason="PoC did not trigger the vulnerability",
        duration_seconds=312.0,
    ),
]


def test_report_contains_task_ids(tmp_path):
    path = tmp_path / "report.md"
    md = build_report(SAMPLE_RESULTS, path)
    assert "arvo:10400" in md
    assert "arvo:3938" in md
    assert "oss-fuzz:42535201" in md


def test_report_contains_classification_labels(tmp_path):
    path = tmp_path / "report.md"
    md = build_report(SAMPLE_RESULTS, path)
    assert "Found public PoC" in md
    assert "Reasoned from code" in md
    assert "Failed" in md


def test_report_file_is_written(tmp_path):
    path = tmp_path / "report.md"
    build_report(SAMPLE_RESULTS, path)
    assert path.exists()
    assert path.stat().st_size > 0


def test_report_flip_marker(tmp_path):
    # arvo:10400 is True in CyberGym and True in BenchJoe — no flip
    # arvo:368 is False in CyberGym; if BenchJoe succeeds, should show ⚡
    results = [
        TaskResult(
            task_id="arvo:368",
            benchjoe_success=True,
            classification_label="internet_assisted",
            classification_reason="Found writeup online",
            duration_seconds=200.0,
        )
    ]
    path = tmp_path / "report.md"
    md = build_report(results, path)
    assert "⚡" in md


def test_save_and_load_result(tmp_path):
    result = SAMPLE_RESULTS[0]
    save_result(result, tmp_path)
    loaded = load_results(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].task_id == result.task_id
    assert loaded[0].benchjoe_success == result.benchjoe_success
    assert loaded[0].classification_label == result.classification_label
