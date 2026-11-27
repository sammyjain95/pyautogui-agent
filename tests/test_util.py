"""Tests for the lazy pyautogui import helper."""

import os
import sys

import pytest

from pyautogui_agent._util import get_pyautogui, save_screenshot
from pyautogui_agent.errors import DisplayUnavailableError


def test_get_pyautogui_returns_stub(fake_pyautogui):
    pg = get_pyautogui()
    assert pg.size() == (1920, 1080)


def test_get_pyautogui_fails_clearly_with_no_display(monkeypatch):
    # Remove the stub so the real import is attempted, and remove
    # DISPLAY so the real import fails the way it does headless.
    sys.modules.pop("pyautogui", None)
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(DisplayUnavailableError):
        get_pyautogui()


def test_save_screenshot_writes_png(tmp_path):
    from PIL import Image

    image = Image.new("RGB", (10, 10), "red")
    path = save_screenshot(image, directory=str(tmp_path))
    assert os.path.isfile(path)
    assert path.endswith(".png")
