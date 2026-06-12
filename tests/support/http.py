"""Helpers for mocking the `requests` library in provider tests."""

from unittest.mock import MagicMock


def mock_response(json_data=None, status=200, text=""):
    """Build a fake requests.Response with .status_code / .json() / .text."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    return resp
