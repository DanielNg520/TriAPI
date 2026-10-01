from hashlib import sha256
from pathlib import Path

import pytest

from scripts.dispatch import (
    load_stored_response,
    responses_dir,
    store_response,
)


def test_store_response_writes_hash_named_file_with_exact_text(tmp_path: Path) -> None:
    text = "hello world"
    path = store_response(text)

    expected_name = sha256(text.encode("utf-8")).hexdigest() + ".txt"
    assert path == responses_dir() / expected_name
    assert path.read_text(encoding="utf-8") == text


def test_store_response_is_idempotent() -> None:
    text = "same text twice"
    first = store_response(text)
    second = store_response(text)

    assert first == second


def test_load_stored_response_round_trips() -> None:
    text = "round trip me"
    path = store_response(text)

    assert load_stored_response(path) == text


def test_load_stored_response_rejects_file_outside_responses_dir(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "x.txt"
    outside.write_text("not in responses dir", encoding="utf-8")

    with pytest.raises(ValueError):
        load_stored_response(outside)


def test_load_stored_response_rejects_non_hash_filename() -> None:
    responses_dir().mkdir(parents=True, exist_ok=True)
    bad = responses_dir() / "bad.txt"
    bad.write_text("not a hash name", encoding="utf-8")

    with pytest.raises(ValueError):
        load_stored_response(bad)


def test_load_stored_response_rejects_tampered_file() -> None:
    path = store_response("original content")
    path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError):
        load_stored_response(path)


def test_store_and_load_non_ascii_text() -> None:
    text = "héllo ✓"
    path = store_response(text)

    assert load_stored_response(path) == text
