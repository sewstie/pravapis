from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _check_file(path: Path) -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from check_no_request_text_logging import check_file
    finally:
        sys.path.pop(0)
    return check_file(path)


def _write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")
    return path


def test_flags_text_argument_on_the_log_call(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "log.info('got %s', text)\n",
    )
    assert _check_file(path)


def test_flags_unresolved_attribute_a_few_lines_away(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "n = len(result.unresolved)\n"
        "count = n\n"
        "extra = count\n"
        "log.info('unresolved count', count)\n",
    )
    assert _check_file(path)


def test_flags_req_dot_text_attribute_access(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "chars = len(req.text)\nlog.info('chars=%s', chars)\n",
    )
    assert _check_file(path)


def test_allows_metadata_only_logging(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "direction = req.direction\n"
        "char_count = len(req.text)\n"
        "\n\n\n\n\n\n\n\n\n"
        "log.info('endpoint=%s direction=%s chars=%s', endpoint, direction, char_count)\n",
    )
    assert _check_file(path) == []


def test_does_not_trip_on_prose_in_a_docstring(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '"""Never log request text or the unresolved list, not even a hash of it."""\n'
        "\n\n\n\n\n\n\n\n\n"
        "log.info('status=%s', status)\n",
    )
    assert _check_file(path) == []


def test_does_not_trip_on_a_comment_mentioning_text(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "# text and unresolved are never logged here\n"
        "\n\n\n\n\n\n\n\n\n"
        "log.info('status=%s', status)\n",
    )
    assert _check_file(path) == []


def test_ignores_a_far_away_banned_identifier(tmp_path: Path) -> None:
    lines = ["x = 1\n"] * 20
    lines.append("text = 'unrelated, far from any log call'\n")
    lines += ["y = 2\n"] * 20
    lines.append("log.info('status=%s', status)\n")
    path = _write(tmp_path, "".join(lines))
    assert _check_file(path) == []


def test_ignores_a_log_call_with_no_nearby_banned_identifier(tmp_path: Path) -> None:
    path = _write(tmp_path, "log.info('status=%s', status)\n")
    assert _check_file(path) == []


def test_the_repos_own_api_directory_passes(tmp_path: Path) -> None:
    del tmp_path
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from check_no_request_text_logging import API_DIR, check_file
    finally:
        sys.path.pop(0)
    problems: list[str] = []
    for path in sorted(API_DIR.rglob("*.py")):
        problems += check_file(path)
    assert problems == []
