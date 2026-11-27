"""Shared fixtures: stub pyautogui (and optionally pytesseract).

The real pyautogui cannot be imported on this headless VM (its X11
backend connects to the display at import time), so every test runs
against a stub module injected into sys.modules. The package imports
pyautogui lazily, inside functions, so the stub is picked up at call
time. The one test that checks the real import failure removes the
stub first (see test_util.py).
"""

import shutil
import sys
import types

import pytest
from PIL import Image


class FakeImageNotFoundException(Exception):
    """Stand-in for pyautogui.ImageNotFoundException."""


class FakePyAutoGUI:
    """Records calls and returns canned values."""

    def __init__(self):
        self.calls = []
        self.locate_result = None
        self.locate_raises = None
        self.screenshot_image = Image.new("RGB", (800, 600), "white")
        self.screen_size = (1920, 1080)
        self.mouse_position = (100, 200)

    def screenshot(self):
        self.calls.append(("screenshot",))
        return self.screenshot_image

    def locateOnScreen(self, image, **kwargs):
        self.calls.append(("locateOnScreen", image, kwargs))
        if self.locate_raises is not None:
            raise self.locate_raises
        return self.locate_result

    def size(self):
        self.calls.append(("size",))
        return self.screen_size

    def position(self):
        self.calls.append(("position",))
        return self.mouse_position

    def click(self, x, y, button="left", **kwargs):
        self.calls.append(("click", x, y, button))
        return None

    def typewrite(self, text, interval=0.0):
        self.calls.append(("typewrite", text, interval))
        return None


def build_pyautogui_stub(fake):
    module = types.ModuleType("pyautogui")
    module.ImageNotFoundException = FakeImageNotFoundException
    module.FAILSAFE = True
    module.PAUSE = 0.1
    module.screenshot = fake.screenshot
    module.locateOnScreen = fake.locateOnScreen
    module.size = fake.size
    module.position = fake.position
    module.click = fake.click
    module.typewrite = fake.typewrite
    return module


@pytest.fixture(autouse=True)
def fake_pyautogui():
    fake = FakePyAutoGUI()
    previous = sys.modules.get("pyautogui")
    sys.modules["pyautogui"] = build_pyautogui_stub(fake)
    yield fake
    if previous is None:
        sys.modules.pop("pyautogui", None)
    else:
        sys.modules["pyautogui"] = previous


def ocr_data(words):
    """Build a pytesseract image_to_data dict from (text, x, y, w, h, conf)."""
    return {
        "text": [w[0] for w in words],
        "left": [w[1] for w in words],
        "top": [w[2] for w in words],
        "width": [w[3] for w in words],
        "height": [w[4] for w in words],
        "conf": [w[5] for w in words],
        "level": [5] * len(words),
        "block_num": [1] * len(words),
        "par_num": [1] * len(words),
        "line_num": [1] * len(words),
    }


@pytest.fixture
def fake_ocr(monkeypatch):
    """Install a stub pytesseract module and a fake tesseract binary.

    Returns a holder dict; tests replace ``holder["data"]`` to change
    what OCR sees. Default data: the word "Submit" at (100, 200).
    """
    holder = {"data": ocr_data([("Submit", 100, 200, 60, 20, 95.0)])}
    module = types.ModuleType("pytesseract")

    class Output:
        DICT = "dict"

    module.Output = Output
    module.image_to_data = lambda image, lang="eng", output_type=None: holder["data"]
    monkeypatch.setitem(sys.modules, "pytesseract", module)
    monkeypatch.setattr(
        shutil, "which",
        lambda name: "/usr/bin/tesseract" if name == "tesseract" else None)
    return holder
