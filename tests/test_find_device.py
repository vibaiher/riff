"""Tests for find_input_device — system default first, then fallback."""

from unittest.mock import patch

from riff.audio.capture import find_input_device


class TestFindInputDevice:
    @patch("riff.audio.capture.sd")
    def test_uses_system_default_when_available(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Scarlett Solo", "max_input_channels": 4, "max_output_channels": 2},
            {"name": "MacBook Mic", "max_input_channels": 1, "max_output_channels": 0},
        ]
        mock_sd.default.device = (1, 0)

        idx, name = find_input_device()

        assert idx == 1
        assert name == "MacBook Mic"

    @patch("riff.audio.capture.sd")
    def test_does_not_prefer_focusrite_over_default(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Focusrite Scarlett", "max_input_channels": 2, "max_output_channels": 2},
            {"name": "iPhone Mic", "max_input_channels": 1, "max_output_channels": 0},
        ]
        mock_sd.default.device = (1, 0)

        idx, name = find_input_device()

        assert idx == 1
        assert name == "iPhone Mic"

    @patch("riff.audio.capture.sd")
    def test_falls_back_to_first_input_device(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Speaker Only", "max_input_channels": 0, "max_output_channels": 2},
            {"name": "Some Mic", "max_input_channels": 1, "max_output_channels": 0},
        ]
        mock_sd.default.device = (-1, 0)

        idx, name = find_input_device()

        assert idx == 1
        assert name == "Some Mic"

    @patch("riff.audio.capture.sd")
    def test_returns_default_when_no_input_devices(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Speaker Only", "max_input_channels": 0, "max_output_channels": 2},
        ]
        mock_sd.default.device = (-1, 0)

        idx, name = find_input_device()

        assert idx == 0
        assert name == "Default"
