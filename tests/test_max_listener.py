"""Tests for app/max_listener.py — pure helper functions."""

from datetime import datetime, timezone

import pytest
from app.max_listener import (
    SEPARATOR_LINE,
    MessageFormatter,
    _build_header,
    _format_body_text,
    _format_time,
    _guess_media_kind,
    _human_size,
    _join_header_body,
    _needs_separator,
)


# ---------------------------------------------------------------------------
# _human_size
# ---------------------------------------------------------------------------

class TestHumanSize:
    """Tests for the _human_size byte-formatter."""

    # Byte range (< 1024)
    def test_zero_bytes(self):
        assert _human_size(0) == "0 Б"

    def test_single_byte(self):
        assert _human_size(1) == "1 Б"

    def test_max_bytes(self):
        assert _human_size(1023) == "1023 Б"

    # Kilobyte range (1024 – 1024²-1)
    def test_exact_one_kb(self):
        assert _human_size(1024) == "1.0 КБ"

    def test_fractional_kb(self):
        assert _human_size(1536) == "1.5 КБ"

    def test_large_kb(self):
        assert _human_size(1023 * 1024) == "1023.0 КБ"

    # Megabyte range
    def test_exact_one_mb(self):
        assert _human_size(1024 ** 2) == "1.0 МБ"

    def test_fractional_mb(self):
        assert _human_size(int(2.5 * 1024 ** 2)) == "2.5 МБ"

    def test_large_mb(self):
        assert _human_size(500 * 1024 ** 2) == "500.0 МБ"

    # Gigabyte range
    def test_exact_one_gb(self):
        assert _human_size(1024 ** 3) == "1.0 ГБ"

    def test_fractional_gb(self):
        assert _human_size(int(1.5 * 1024 ** 3)) == "1.5 ГБ"

    # Terabyte range (overflow past ГБ loop)
    def test_terabyte(self):
        result = _human_size(1024 ** 4)
        assert "ТБ" in result

    def test_large_terabyte(self):
        result = _human_size(5 * 1024 ** 4)
        assert result.startswith("5")
        assert "ТБ" in result

    # Return type
    def test_returns_string(self):
        assert isinstance(_human_size(42), str)


# ---------------------------------------------------------------------------
# _guess_media_kind
# ---------------------------------------------------------------------------

class TestGuessMediaKind:
    """Tests for the filename-to-media-kind classifier."""

    # Photo extensions
    def test_jpg_is_photo(self):
        assert _guess_media_kind("image.jpg") == "photo"

    def test_jpeg_is_photo(self):
        assert _guess_media_kind("photo.jpeg") == "photo"

    def test_png_is_photo(self):
        assert _guess_media_kind("screenshot.png") == "photo"

    def test_gif_is_photo(self):
        assert _guess_media_kind("anim.gif") == "photo"

    def test_webp_is_photo(self):
        assert _guess_media_kind("sticker.webp") == "photo"

    def test_bmp_is_photo(self):
        assert _guess_media_kind("old.bmp") == "photo"

    # Video extensions
    def test_mp4_is_video(self):
        assert _guess_media_kind("clip.mp4") == "video"

    def test_mov_is_video(self):
        assert _guess_media_kind("recording.mov") == "video"

    def test_avi_is_video(self):
        assert _guess_media_kind("video.avi") == "video"

    def test_mkv_is_video(self):
        assert _guess_media_kind("movie.mkv") == "video"

    def test_webm_is_video(self):
        assert _guess_media_kind("stream.webm") == "video"

    # Document / unknown extensions
    def test_pdf_is_document(self):
        assert _guess_media_kind("report.pdf") == "document"

    def test_zip_is_document(self):
        assert _guess_media_kind("archive.zip") == "document"

    def test_docx_is_document(self):
        assert _guess_media_kind("contract.docx") == "document"

    def test_txt_is_document(self):
        assert _guess_media_kind("notes.txt") == "document"

    def test_no_extension_is_document(self):
        assert _guess_media_kind("README") == "document"

    def test_empty_string_is_document(self):
        assert _guess_media_kind("") == "document"

    # Case-insensitivity
    def test_uppercase_jpg_is_photo(self):
        assert _guess_media_kind("PHOTO.JPG") == "photo"

    def test_mixed_case_mp4_is_video(self):
        assert _guess_media_kind("Video.MP4") == "video"

    def test_mixed_case_png_is_photo(self):
        assert _guess_media_kind("Image.PNG") == "photo"

    # Paths with directories
    def test_full_path_jpg(self):
        assert _guess_media_kind("/tmp/uploads/img.jpg") == "photo"

    def test_full_path_mp4(self):
        assert _guess_media_kind("/home/user/videos/clip.mp4") == "video"

    # Extension appearing in the middle of filename should not trigger false match
    def test_mp4_in_name_not_extension_is_document(self):
        assert _guess_media_kind("mp4_notes.txt") == "document"


# ---------------------------------------------------------------------------
# _format_time
# ---------------------------------------------------------------------------

class TestFormatTime:
    def test_none_returns_empty(self):
        assert _format_time(None) == ""

    def test_invalid_returns_empty(self):
        assert _format_time("not-a-number") == ""

    def test_seconds_timestamp(self):
        ts = int(datetime(2024, 6, 18, 14, 30, tzinfo=timezone.utc).timestamp())
        assert _format_time(ts) == datetime.fromtimestamp(ts).strftime("%H:%M")

    def test_milliseconds_timestamp(self):
        ts = int(datetime(2024, 6, 18, 9, 5, tzinfo=timezone.utc).timestamp()) * 1000
        assert _format_time(ts) == datetime.fromtimestamp(ts // 1000).strftime("%H:%M")


# ---------------------------------------------------------------------------
# _needs_separator
# ---------------------------------------------------------------------------

class TestNeedsSeparator:
    def test_disabled(self):
        assert _needs_separator(("c", "s"), "c", "s2", False) is False

    def test_first_message_no_separator(self):
        assert _needs_separator(None, "c", "s", True) is False

    def test_same_sender_no_separator(self):
        assert _needs_separator(("c", "s"), "c", "s", True) is False

    def test_different_sender_separator(self):
        assert _needs_separator(("c", "s1"), "c", "s2", True) is True


# ---------------------------------------------------------------------------
# _build_header
# ---------------------------------------------------------------------------

class TestBuildHeader:
    def test_plain_dm(self):
        assert _build_header("Ivan", "", True, "plain", None, True) == "✉ <b>Ivan</b>"

    def test_plain_group_with_chat(self):
        result = _build_header("Ivan", "Work", False, "plain", None, True)
        assert result == "💬 <b>Work</b> | Ivan"

    def test_enhanced_dm_with_time(self):
        ts = int(datetime(2024, 6, 18, 14, 30, tzinfo=timezone.utc).timestamp())
        result = _build_header("Ivan", "", True, "enhanced", ts, True)
        assert result.startswith("✉ <b>Ivan</b> ·")

    def test_enhanced_group_two_lines(self):
        ts = int(datetime(2024, 6, 18, 14, 30, tzinfo=timezone.utc).timestamp())
        result = _build_header("Petr", "Work", False, "enhanced", ts, True)
        assert "💬 <b>Work</b>" in result
        assert "👤 <b>Petr</b>" in result


# ---------------------------------------------------------------------------
# _format_body_text
# ---------------------------------------------------------------------------

class TestFormatBodyText:
    def test_plain(self):
        assert _format_body_text("hi", "plain") == "hi"

    def test_enhanced_blockquote(self):
        assert _format_body_text("hi", "enhanced") == "<blockquote>hi</blockquote>"

    def test_no_blockquote_override(self):
        assert _format_body_text("hi", "enhanced", use_blockquote=False) == "hi"


# ---------------------------------------------------------------------------
# MessageFormatter
# ---------------------------------------------------------------------------

class TestMessageFormatter:
    def test_enhanced_adds_separator_on_sender_change(self):
        fmt = MessageFormatter(style="enhanced")
        first = fmt.begin_message("c1", "u1", "Ivan", "", False, None)
        second = fmt.begin_message("c1", "u2", "Petr", "", False, None)
        assert SEPARATOR_LINE not in first
        assert SEPARATOR_LINE in second

    def test_compact_hides_repeated_header(self):
        fmt = MessageFormatter(style="compact")
        first = fmt.format_text_message("c1", "u1", "Ivan", "", False, "hi", None)
        second = fmt.format_text_message("c1", "u1", "Ivan", "", False, "again", None)
        assert "Ivan" in first
        assert "Ivan" not in second
        assert "<blockquote>again</blockquote>" in second

    def test_plain_matches_legacy_format(self):
        fmt = MessageFormatter(style="plain", separator_enabled=True, show_timestamp=True)
        text = fmt.format_text_message("c1", "u1", "Ivan", "Work", False, "hello", None)
        assert text == "💬 <b>Work</b> | Ivan\nhello"

    def test_join_header_body(self):
        assert _join_header_body("hdr", "body") == "hdr\n\nbody"
        assert _join_header_body("", "body") == "body"
