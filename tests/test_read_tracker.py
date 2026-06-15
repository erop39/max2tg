"""Tests for app/read_tracker.py."""

import pytest

from app.read_tracker import ReadTracker


class TestReadTracker:
    def test_is_unread_without_mark(self):
        rt = ReadTracker()
        assert rt.is_unread(100, 5000) is True

    def test_is_read_when_time_before_mark(self):
        rt = ReadTracker()
        rt._update_mark(100, 5000)
        assert rt.is_unread(100, 5000) is False
        assert rt.is_unread(100, 4999) is False

    def test_is_unread_when_time_after_mark(self):
        rt = ReadTracker()
        rt._update_mark(100, 5000)
        assert rt.is_unread(100, 5001) is True

    def test_mark_only_increases(self):
        rt = ReadTracker()
        rt._update_mark(100, 5000)
        rt._update_mark(100, 4000)
        assert rt._marks[100] == 5000

    def test_on_notif_mark_ignores_other_users(self):
        rt = ReadTracker()
        rt.set_my_id(1)
        rt.on_notif_mark({"userId": 2, "chatId": 100, "mark": 9000})
        assert rt._marks == {}

    def test_on_notif_mark_tracks_own_reads(self):
        rt = ReadTracker()
        rt.set_my_id(1)
        rt.on_notif_mark({"userId": 1, "chatId": 100, "mark": 9000, "unread": 0})
        assert rt._marks[100] == 9000

    def test_load_from_chats(self):
        rt = ReadTracker()
        rt.load_from_chats([
            {"id": 10, "mark": 1000},
            {"id": 20, "mark": 2000},
            {"id": 30},
        ])
        assert rt._marks == {10: 1000, 20: 2000}

    def test_none_timestamp_treated_as_unread(self):
        rt = ReadTracker()
        rt._update_mark(1, 99999)
        assert rt.is_unread(1, None) is True
