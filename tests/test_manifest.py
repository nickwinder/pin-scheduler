# tests/test_manifest.py
from datetime import datetime

import pytest

from manifest import append_row, mark, read_rows, remaining_capacity


def test_read_missing_file_returns_empty(tmp_path):
    assert read_rows(tmp_path / "manifest.csv") == []


def test_append_creates_draft_row(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "Title A", "Desc A")
    rows = read_rows(path)
    assert rows == [{
        "filename": "a.mp4", "title": "Title A", "description": "Desc A",
        "status": "draft", "scheduled_time": "", "error": "",
    }]


def test_mark_updates_matching_row(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "T", "D")
    append_row(path, "b.mp4", "T2", "D2")
    mark(path, "b.mp4", "scheduled", scheduled_time="2026-06-12T09:00")
    rows = read_rows(path)
    assert rows[0]["status"] == "draft"
    assert rows[1]["status"] == "scheduled"
    assert rows[1]["scheduled_time"] == "2026-06-12T09:00"


def test_mark_unknown_filename_raises(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "T", "D")
    with pytest.raises(KeyError):
        mark(path, "missing.mp4", "scheduled", scheduled_time="2026-06-12T09:00")


def test_mark_scheduled_requires_time(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "T", "D")
    with pytest.raises(ValueError):
        mark(path, "a.mp4", "scheduled")


def test_mark_writes_full_row(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "T", "D")
    mark(path, "a.mp4", "failed", error="upload timed out")
    rows = read_rows(path)
    assert rows[0]["status"] == "failed"
    assert rows[0]["error"] == "upload timed out"
    assert rows[0]["scheduled_time"] == ""


def test_capacity_counts_only_future_scheduled():
    now = datetime(2026, 6, 12, 12, 0)
    rows = [
        {"status": "scheduled", "scheduled_time": "2026-06-12T10:00"},  # already published
        {"status": "scheduled", "scheduled_time": "2026-06-12T14:00"},  # still queued
        {"status": "approved", "scheduled_time": ""},
        {"status": "draft", "scheduled_time": ""},
    ]
    assert remaining_capacity(rows, now=now, cap=10) == 9
