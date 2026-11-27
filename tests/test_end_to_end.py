"""Dry-run end-to-end pass: observe, dry-run click, wait timeout.

This is the same pass a human runs by hand after install. It uses
the stub pyautogui from conftest, so it needs no display, and it
proves the modules work together: observe() reads the screen state,
a dry-run click is logged but never executed, and a wait that never
succeeds raises the structured timeout error with a screenshot.
"""

import pytest

from pyautogui_agent import (
    Session,
    click_point,
    observe,
    wait_for_condition,
)
from pyautogui_agent.errors import ActionTimeoutError


def test_dry_run_end_to_end(fake_pyautogui, tmp_path):
    session = Session(dry_run=True)

    obs = observe()
    assert obs.screen_size == (1920, 1080)
    assert obs.mouse_position == (100, 200)
    assert obs.screenshot is not None
    assert obs.elements is not None
    assert obs.elements.supported is False

    result = click_point(500, 500, session=session)
    assert result is None
    assert [c for c in fake_pyautogui.calls if c[0] == "click"] == []
    assert len(session.log) == 1
    assert session.log[0].action == "click_point"
    assert session.log[0].executed is False

    with pytest.raises(ActionTimeoutError) as excinfo:
        wait_for_condition(lambda: False, timeout=0.2, interval=0.05,
                           description="end-to-end wait",
                           screenshot_dir=str(tmp_path))
    assert excinfo.value.last_screenshot is not None

    lines = session.format_log()
    assert len(lines) == 1
    assert "click_point" in lines[0]
    assert "dry run" in lines[0]
