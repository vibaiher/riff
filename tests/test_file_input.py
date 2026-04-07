"""Tests for file input mode with tab-completion."""

import os
import tempfile

from riff.ui.file_input import complete_path, InputBuffer


class TestCompletePath:
    def test_returns_empty_for_nonexistent_prefix(self):
        results = complete_path("/nonexistent_path_xyz_1234567890/foo")

        assert results == []

    def test_returns_matching_files(self, tmp_path):
        (tmp_path / "song.mid").touch()
        (tmp_path / "song.txt").touch()

        results = complete_path(str(tmp_path / "song"))

        assert str(tmp_path / "song.mid") in results
        assert str(tmp_path / "song.txt") in results

    def test_directories_have_trailing_slash(self, tmp_path):
        (tmp_path / "subdir").mkdir()

        results = complete_path(str(tmp_path / "sub"))

        assert results == [str(tmp_path / "subdir") + "/"]

    def test_expands_tilde(self):
        home = os.path.expanduser("~")

        results = complete_path("~/")

        assert all(r.startswith(home) for r in results)
        assert len(results) > 0


class TestInputBuffer:
    def test_starts_empty(self):
        buf = InputBuffer()

        assert buf.text == ""

    def test_append_character(self):
        buf = InputBuffer()

        buf.append("a")
        buf.append("b")

        assert buf.text == "ab"

    def test_backspace_removes_last(self):
        buf = InputBuffer()
        buf.append("a")
        buf.append("b")

        buf.backspace()

        assert buf.text == "a"

    def test_backspace_on_empty_stays_empty(self):
        buf = InputBuffer()

        buf.backspace()

        assert buf.text == ""

    def test_clear_resets(self):
        buf = InputBuffer()
        buf.append("x")

        buf.clear()

        assert buf.text == ""

    def test_tab_complete_single_match_replaces(self, tmp_path):
        (tmp_path / "mysong.mid").touch()
        buf = InputBuffer()
        buf.text = str(tmp_path / "my")

        buf.tab_complete()

        assert buf.text == str(tmp_path / "mysong.mid")

    def test_tab_complete_multiple_matches_completes_common_prefix(self, tmp_path):
        (tmp_path / "song_a.mid").touch()
        (tmp_path / "song_b.mid").touch()
        buf = InputBuffer()
        buf.text = str(tmp_path / "so")

        buf.tab_complete()

        assert buf.text == str(tmp_path / "song_")

    def test_tab_complete_no_matches_unchanged(self):
        buf = InputBuffer()
        buf.text = "/nonexistent_xyz_999/foo"

        buf.tab_complete()

        assert buf.text == "/nonexistent_xyz_999/foo"

    def test_tab_complete_common_prefix_is_path_aware(self, tmp_path):
        (tmp_path / "song_alpha.mid").touch()
        (tmp_path / "song_beta.mid").touch()
        buf = InputBuffer()
        buf.text = str(tmp_path / "song")

        buf.tab_complete()

        assert buf.text == str(tmp_path / "song_")

    def test_tab_complete_dir_and_file_with_same_prefix(self, tmp_path):
        (tmp_path / "music").mkdir()
        (tmp_path / "music.txt").touch()
        buf = InputBuffer()
        buf.text = str(tmp_path / "mus")

        buf.tab_complete()

        assert buf.text == str(tmp_path / "music")
