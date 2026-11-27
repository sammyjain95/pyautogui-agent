"""Tests for waits, using the stub pyautogui from conftest."""

import os

import pytest

from pyautogui_agent.errors import ActionTimeoutError
from pyautogui_agent.wait import wait_for_condition, wait_for_image


def test_wait_for_condition_returns_truthy_value():
    attempts = {"n": 0}

    def check():
        attempts["n"] += 1
        return "found" if attempts["n"] >= 3 else None

    assert wait_for_condition(check, timeout=5.0, interval=0.01) == "found"
    assert attempts["n"] == 3


def test_wait_for_condition_timeout_saves_screenshot(tmp_path):
    with pytest.raises(ActionTimeoutError) as excinfo:
        wait_for_condition(lambda: None, timeout=0.2, interval=0.05,
                           description="test condition",
                           screenshot_dir=str(tmp_path))
    err = excinfo.value
    assert err.what == "test condition"
    assert err.timeout == 0.2
    assert err.waited == 0.2
    assert err.last_screenshot is not None
    assert os.path.isfile(err.last_screenshot)
    assert err.last_screenshot.endswith(".png")


def test_wait_for_image_returns_box_when_found(fake_pyautogui):
    fake_pyautogui.locate_result = (10, 20, 100, 40)
    assert wait_for_image("ok.png", timeout=5.0) == (10, 20, 100, 40)


def test_wait_for_image_timeout_saves_screenshot(tmp_path):
    with pytest.raises(ActionTimeoutError) as excinfo:
        wait_for_image("missing.png", timeout=0.2, interval=0.05,
                       screenshot_dir=str(tmp_path))
    err = excinfo.value
    assert "missing.png" in err.what
    assert err.last_screenshot is not None
    assert os.path.isfile(err.last_screenshot)


def test_wait_for_image_treats_not_found_exception_as_miss(fake_pyautogui, tmp_path):
    # Raise via the stub module's own exception class: wait.py reads
    # that same class through getattr, so identity must match. (Do not
    # import the class from tests.conftest: pytest loads conftest under
    # a different module name, giving a second, distinct class object.)
    import sys

    stub = sys.modules["pyautogui"]
    fake_pyautogui.locate_raises = stub.ImageNotFoundException("no match")
    with pytest.raises(ActionTimeoutError):
        wait_for_image("missing.png", timeout=0.2, interval=0.05,
                       screenshot_dir=str(tmp_path))


def test_wait_for_image_passes_confidence_and_region(fake_pyautogui):
    fake_pyautogui.locate_result = (0, 0, 5, 5)
    wait_for_image("ok.png", timeout=5.0, confidence=0.9,
                   region=(0, 0, 100, 100))
    _, _, kwargs = fake_pyautogui.calls[-1]
    assert kwargs["confidence"] == 0.9
    assert kwargs["region"] == (0, 0, 100, 100)
