"""Tests for task-level actions, using the stub pyautogui and OCR."""

import os
import sys

import pytest

from pyautogui_agent.actions import (
    click_image,
    click_point,
    click_text,
    fill_field,
)
from pyautogui_agent.errors import (
    ActionTimeoutError,
    ElementNotFoundError,
    ProviderNotInstalledError,
)
from pyautogui_agent.safety import Session
from tests.conftest import ocr_data


def test_click_text_without_tesseract_raises_clear_error(monkeypatch):
    # Force the missing-Tesseract condition regardless of this VM
    # (Tesseract may or may not be installed here): block the
    # pytesseract import and hide the binary, then the install
    # message must be raised.
    import shutil
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ProviderNotInstalledError) as excinfo:
        click_text("Submit", timeout=0.2, interval=0.05)
    assert "tesseract" in str(excinfo.value).lower()
    assert "pip install" in str(excinfo.value)


def test_click_text_clicks_word_center(fake_pyautogui, fake_ocr):
    session = Session()
    result = click_text("Submit", timeout=5.0, session=session)
    # Word "Submit" is at (100, 200) with size 60x20, center (130, 210).
    assert result == (130.0, 210.0)
    clicks = [c for c in fake_pyautogui.calls if c[0] == "click"]
    assert clicks == [("click", 130.0, 210.0, "left")]
    assert session.log[0].action == "click_text"
    assert session.log[0].executed is True


def test_ocr_uses_sparse_text_and_upscale(fake_pyautogui, fake_ocr):
    # OCR must use psm 11 (sparse text) on a 2x upscaled image, and
    # the coordinates it returns must be scaled back to screen
    # pixels: the fake returns the canned word doubled (as Tesseract
    # would for a 2x image), so the click must still land at the
    # screen center (130, 210), and the image passed to OCR must be
    # 1600x1200 for an 800x600 screenshot.
    result = click_text("Submit", timeout=5.0)
    assert result == (130.0, 210.0)
    assert fake_ocr["config"] is not None
    assert "--psm 11" in fake_ocr["config"]
    assert fake_ocr["image_size"] == (1600, 1200)


def test_click_text_matches_multiword_phrase(fake_pyautogui, fake_ocr):
    fake_ocr["data"] = ocr_data([
        ("Submit", 100, 200, 60, 20, 95.0),
        ("form", 165, 200, 40, 20, 90.0),
        ("Cancel", 300, 200, 60, 20, 88.0),
    ])
    result = click_text("Submit form", timeout=5.0)
    # Union box (100, 200, 105, 20), center (152.5, 210).
    assert result == (152.5, 210.0)


def test_click_text_not_found_carries_screenshot_and_closest(
        fake_pyautogui, fake_ocr, tmp_path):
    with pytest.raises(ElementNotFoundError) as excinfo:
        click_text("Submitt", timeout=0.2, interval=0.05,
                   screenshot_dir=str(tmp_path))
    err = excinfo.value
    assert err.query == "Submitt"
    assert err.screenshot_path is not None
    assert os.path.isfile(err.screenshot_path)
    assert err.closest_match == "Submit"
    assert err.confidence is not None and err.confidence > 0.5


def test_click_text_dry_run_does_not_click(fake_pyautogui, fake_ocr):
    session = Session(dry_run=True)
    result = click_text("Submit", timeout=5.0, session=session)
    assert result is None
    assert [c for c in fake_pyautogui.calls if c[0] == "click"] == []
    assert session.log[0].action == "click_text"
    assert session.log[0].executed is False


def test_click_image_clicks_box_center(fake_pyautogui):
    fake_pyautogui.locate_result = (10, 20, 100, 40)
    session = Session()
    result = click_image("ok.png", session=session, timeout=5.0)
    assert result == (60.0, 40.0)
    clicks = [c for c in fake_pyautogui.calls if c[0] == "click"]
    assert clicks == [("click", 60.0, 40.0, "left")]


def test_click_image_timeout_raises_action_timeout(fake_pyautogui, tmp_path):
    with pytest.raises(ActionTimeoutError) as excinfo:
        click_image("missing.png", timeout=0.2, interval=0.05)
    assert "missing.png" in str(excinfo.value)


def test_click_point_goes_through_session(fake_pyautogui):
    session = Session()
    click_point(500, 600, session=session)
    assert ("click", 500, 600, "left") in fake_pyautogui.calls
    assert session.log[0].action == "click_point"


def test_click_point_dry_run_logs_without_clicking(fake_pyautogui):
    session = Session(dry_run=True)
    click_point(1, 2, session=session)
    assert [c for c in fake_pyautogui.calls if c[0] == "click"] == []
    assert session.log[0].executed is False


def test_fill_field_clicks_field_right_of_label_then_types(
        fake_pyautogui, fake_ocr):
    session = Session()
    fill_field("Submit", "hello", session=session)
    # The "Submit" word is at (100, 200, 60, 20). The field point is
    # 30px past its right edge, at its vertical center: (190, 210).
    # The label itself is never clicked.
    kinds = [c[0] for c in fake_pyautogui.calls]
    assert kinds.index("click") < kinds.index("typewrite")
    clicks = [c for c in fake_pyautogui.calls if c[0] == "click"]
    assert clicks == [("click", 190.0, 210.0, "left")]
    typed = [c for c in fake_pyautogui.calls if c[0] == "typewrite"]
    assert typed == [("typewrite", "hello", 0.05)]
    actions = [r.action for r in session.log]
    assert actions == ["click_field", "type"]
    assert session.log[0].args["placement"] == "right"


def test_field_point_right_of_label():
    from pyautogui_agent.actions import _field_point
    point, placement = _field_point((100, 200, 60, 20), (1920, 1080))
    assert point == (190.0, 210.0)
    assert placement == "right"


def test_field_point_below_full_width_label():
    from pyautogui_agent.actions import _field_point
    # Label spans nearly the full width: no room for a field to its
    # right, so the point falls below it.
    point, placement = _field_point((100, 200, 1800, 20), (1920, 1080))
    assert point == (1000.0, 250.0)
    assert placement == "below"


def test_field_point_custom_gap():
    from pyautogui_agent.actions import _field_point
    point, placement = _field_point((100, 200, 60, 20), (1920, 1080),
                                    field_gap=10)
    assert point == (170.0, 210.0)
    assert placement == "right"


def test_fill_field_missing_label_raises(fake_pyautogui, fake_ocr, tmp_path):
    # On Linux there is no element provider, and OCR sees only
    # "Submit", so a different label must fail with context.
    with pytest.raises(ElementNotFoundError) as excinfo:
        fill_field("Nonexistent", "x", timeout=0.2)
    assert excinfo.value.query == "Nonexistent"
