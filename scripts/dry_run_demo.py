#!/usr/bin/env python3
"""Headless dry-run demo of pyautogui_agent.

Run: python3 scripts/dry_run_demo.py

Runs the same end-to-end pass as tests/test_end_to_end.py, but as a
plain script with printed output: observe() against a stub screen, a
dry-run click (logged, never executed), and a wait that times out
with a structured error carrying a screenshot path. Needs no display.
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402


def _install_stub():
    """Install a stub pyautogui module so nothing touches a display."""
    fake = types.ModuleType("pyautogui")

    class ImageNotFoundException(Exception):
        pass

    fake.ImageNotFoundException = ImageNotFoundException
    fake.FAILSAFE = True
    fake.PAUSE = 0.1
    fake.screenshot = lambda: Image.new("RGB", (800, 600), "white")
    fake.locateOnScreen = lambda image, **kwargs: None
    fake.size = lambda: (1920, 1080)
    fake.position = lambda: (100, 200)
    fake.click = lambda x, y, button="left", **kwargs: None
    fake.typewrite = lambda text, interval=0.0: None
    sys.modules["pyautogui"] = fake


def main():
    _install_stub()
    from pyautogui_agent import Session, click_point, observe, wait_for_condition
    from pyautogui_agent.errors import ActionTimeoutError

    print("pyautogui-agent dry-run demo (stub screen, no display)")
    session = Session(dry_run=True)

    obs = observe()
    print("observe: screen=%s mouse=%s screenshot=%s elements supported=%s"
          % (obs.screen_size, obs.mouse_position, obs.screenshot.size,
             obs.elements.supported))

    result = click_point(500, 500, session=session)
    print("dry-run click_point returned: %r" % (result,))
    for line in session.format_log():
        print("  log: " + line)

    try:
        wait_for_condition(lambda: False, timeout=0.3, interval=0.05,
                           description="demo wait")
    except ActionTimeoutError as err:
        print("wait timed out as expected: %s" % (err,))
        print("last screenshot: %s" % (err.last_screenshot,))

    print("Done. No real clicks were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
