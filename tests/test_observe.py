"""Tests for observe() with the stub pyautogui."""

import os

import pytest

from pyautogui_agent.observe import observe


def test_observe_returns_full_observation(fake_pyautogui):
    obs = observe()
    assert obs.screenshot is not None
    assert obs.screenshot.size == (800, 600)
    assert obs.screen_size == (1920, 1080)
    assert obs.mouse_position == (100, 200)
    # On this Linux VM there is no element provider, so the listing is
    # included with supported False, never omitted or silently empty.
    assert obs.elements is not None
    assert obs.elements.supported is False
    assert obs.elements.elements == []
    assert "linux" in obs.elements.message
    assert obs.timestamp is not None


def test_observe_without_elements(fake_pyautogui):
    obs = observe(include_elements=False)
    assert obs.elements is None
    assert obs.screen_size == (1920, 1080)


def test_observe_without_screenshot(fake_pyautogui):
    obs = observe(take_screenshot=False)
    assert obs.screenshot is None
    kinds = [call[0] for call in fake_pyautogui.calls]
    assert "screenshot" not in kinds


def test_observation_save_screenshot(tmp_path):
    obs = observe()
    path = str(tmp_path / "obs.png")
    obs.save_screenshot(path)
    assert os.path.isfile(path)


def test_observation_save_screenshot_noop_when_none():
    obs = observe(take_screenshot=False)
    obs.save_screenshot("/tmp/does-not-matter.png")
