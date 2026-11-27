"""Waits: poll for something to appear, with a deadline.

PyAutoGUI has no wait primitive. Agents sleep blindly or poll
``locateOnScreen`` in a loop at one to two seconds per call. These
functions poll with a deadline and, when they give up, raise
``ActionTimeoutError`` carrying the last screenshot path, so the
caller can see what the screen looked like at give-up time.
"""

from __future__ import annotations

import time

from .errors import ActionTimeoutError
from ._util import get_pyautogui, save_screenshot


def _last_screenshot(pg, screenshot_dir):
    """Take a screenshot and save it, returning the path or None."""
    try:
        image = pg.screenshot()
    except Exception:
        return None
    try:
        return save_screenshot(image, directory=screenshot_dir)
    except Exception:
        return None


def wait_for_image(image, timeout=10.0, interval=0.5, confidence=None,
                   region=None, screenshot_dir=None):
    """Wait until an image appears on screen, then return its box.

    Polls ``pyautogui.locateOnScreen`` until it returns a box
    ``(left, top, width, height)`` or the timeout expires. Raises
    ``ActionTimeoutError`` carrying the last screenshot path.
    ``confidence`` and ``region`` are passed through to locateOnScreen
    when given.
    """
    pg = get_pyautogui()
    not_found = getattr(pg, "ImageNotFoundException", None)
    deadline = time.monotonic() + timeout
    while True:
        try:
            kwargs = {}
            if confidence is not None:
                kwargs["confidence"] = confidence
            if region is not None:
                kwargs["region"] = region
            found = pg.locateOnScreen(image, **kwargs)
        except Exception as exc:
            if not_found is not None and isinstance(exc, not_found):
                found = None
            else:
                raise
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            waited = timeout
            path = _last_screenshot(pg, screenshot_dir)
            raise ActionTimeoutError("image %r to appear" % (image,),
                                     timeout, waited,
                                     last_screenshot=path)
        time.sleep(interval)


def wait_for_condition(fn, timeout=10.0, interval=0.5,
                       description="condition", screenshot_dir=None):
    """Wait until ``fn`` returns a truthy value, then return it.

    Raises ``ActionTimeoutError`` carrying the last screenshot path.
    Use for anything that is not an image: a window title, a file
    appearing, an element becoming enabled.
    """
    pg = get_pyautogui()
    deadline = time.monotonic() + timeout
    while True:
        value = fn()
        if value:
            return value
        if time.monotonic() >= deadline:
            path = _last_screenshot(pg, screenshot_dir)
            raise ActionTimeoutError(description, timeout, timeout,
                                     last_screenshot=path)
        time.sleep(interval)
