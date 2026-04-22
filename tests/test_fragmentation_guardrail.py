from pathlib import Path

from scripts import check_fragmentation


def write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("line\n" * count, encoding="utf-8")


def test_new_oversized_test_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "test_new_surface.py"
    write_lines(path, check_fragmentation.TEST_PY_CAP + 1)

    violation = check_fragmentation.check_file(tmp_path, "tests/test_new_surface.py")

    assert violation is not None
    assert violation.rule.name == "test file"


def test_grandfathered_file_can_stay_at_current_limit(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "test_engagement_api.py"
    write_lines(path, check_fragmentation.GRANDFATHERED_LIMITS["tests/test_engagement_api.py"])

    violation = check_fragmentation.check_file(tmp_path, "tests/test_engagement_api.py")

    assert violation is None


def test_grandfathered_file_cannot_grow(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "test_engagement_api.py"
    write_lines(path, check_fragmentation.GRANDFATHERED_LIMITS["tests/test_engagement_api.py"] + 1)

    violation = check_fragmentation.check_file(tmp_path, "tests/test_engagement_api.py")

    assert violation is not None
    assert violation.grandfathered_limit == check_fragmentation.GRANDFATHERED_LIMITS[
        "tests/test_engagement_api.py"
    ]


def test_append_only_log_is_exempt(tmp_path: Path) -> None:
    path = tmp_path / "wiki" / "log.md"
    write_lines(path, 5_000)

    violation = check_fragmentation.check_file(tmp_path, "wiki/log.md")

    assert violation is None
