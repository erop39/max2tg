"""Tests for app/mute_tracker.py."""

import time

from app.mute_tracker import MuteTracker, _extract_dont_disturb_until


class TestExtractDontDisturb:
    def test_top_level(self):
        assert _extract_dont_disturb_until({"dontDisturbUntil": -1}) == -1

    def test_nested_settings(self):
        assert _extract_dont_disturb_until({"settings": {"dontDisturbUntil": -1}}) == -1


class TestMuteTracker:
    def test_permanent_mute(self):
        mt = MuteTracker()
        mt.update_chat({"id": 100, "dontDisturbUntil": -1})
        assert mt.is_muted(100) is True
        assert mt.is_muted("100") is True

    def test_unmute(self):
        mt = MuteTracker()
        mt.update_chat({"id": 100, "dontDisturbUntil": -1})
        mt.update_chat({"id": 100, "dontDisturbUntil": 0})
        assert mt.is_muted(100) is False

    def test_timed_mute_expires(self):
        mt = MuteTracker()
        past = int(time.time() * 1000) - 1000
        mt._apply(1, past)
        assert mt.is_muted(1) is False

    def test_timed_mute_active(self):
        mt = MuteTracker()
        future = int(time.time() * 1000) + 60_000
        mt._apply(1, future)
        assert mt.is_muted(1) is True

    def test_on_settings(self):
        mt = MuteTracker()
        mt.on_settings({
            "settings": {
                "chats": {
                    "-123": {"dontDisturbUntil": -1},
                    "456": {"dontDisturbUntil": 0},
                }
            }
        })
        assert mt.is_muted(-123) is True
        assert mt.is_muted(456) is False

    def test_load_from_chats(self):
        mt = MuteTracker()
        mt.load_from_chats([
            {"id": 10, "dontDisturbUntil": -1},
            {"id": 20},
        ])
        assert mt.is_muted(10) is True
        assert mt.is_muted(20) is False

    def test_notif_chat_update_unmutes(self):
        mt = MuteTracker()
        mt.update_chat({"id": 5, "dontDisturbUntil": -1})
        mt.update_chat({"id": 5, "dontDisturbUntil": 0})
        assert mt.is_muted(5) is False

    def test_load_from_snapshot_settings_chats(self):
        mt = MuteTracker()
        mt.load_from_snapshot({
            "chats": [
                {"id": 10, "title": "Visible"},
            ],
            "settings": {
                "chats": {
                    "-68093732121255": {"dontDisturbUntil": -1},
                    "10": {"dontDisturbUntil": 0},
                }
            },
        })
        assert mt.is_muted(-68093732121255) is True
        assert mt.is_muted(10) is False

    def test_update_from_payload_nested_chat(self):
        mt = MuteTracker()
        mt.update_from_payload({
            "chat": {"id": 99, "dontDisturbUntil": -1},
        })
        assert mt.is_muted(99) is True

    def test_update_from_payload_settings(self):
        mt = MuteTracker()
        mt.update_from_payload({
            "settings": {
                "chats": {"42": {"dontDisturbUntil": -1}},
            },
        })
        assert mt.is_muted(42) is True

    def test_update_from_payload_chat_id_top_level(self):
        mt = MuteTracker()
        mt.update_from_payload({
            "chatId": -123,
            "dontDisturbUntil": -1,
        })
        assert mt.is_muted(-123) is True

    def test_muted_count(self):
        mt = MuteTracker()
        assert mt.muted_count() == 0
        mt.update_chat({"id": 1, "dontDisturbUntil": -1})
        assert mt.muted_count() == 1
