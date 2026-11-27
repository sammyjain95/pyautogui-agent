"""Internal helpers for pyautogui_agent.

PyAutoGUI is imported lazily, inside functions, never at module import
time. Importing PyAutoGUI on a headless machine fails (its X11 backend
connects to the display at import time), so this package must import
cleanly with no display present and only fail when an action that needs
the screen is actually attempted.
"""

from __future__ import annotations

import os
import tempfile
import time

from .errors import DisplayUnavailableError


def get_pyautogui():
    """Import and return the pyautogui module, on first use.

    Raises DisplayUnavailableError when PyAutoGUI cannot be imported,
    which on Linux usually means there is no display to connect to.
    Tests inject a stub module into ``sys.modules["pyautogui"]`` and
    this function returns that stub, because ``import pyautogui`` picks
    it up from there.
    """
    try:
        import pyautogui
    except Exception as exc:  # noqa: BLE001 - any import failure is a display problem here
        raise DisplayUnavailableError(str(exc)) from exc
    return pyautogui


def opencv_available():
    """Return True when OpenCV is available for confidence matching.

    Checks PyScreeze's own flag first (it sets ``_useOpenCV`` at
    import time from whether cv2 imports), and falls back to trying
    to import cv2 directly. Importing cv2 is safe headless; it does
    not touch the display.
    """
    try:
        import pyscreeze
        flag = getattr(pyscreeze, "_useOpenCV", None)
        if flag is not None:
            return bool(flag)
    except Exception:
        pass
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def save_screenshot(image, directory=None):
    """Save a Pillow image to disk and return the path.

    Files go to ``directory`` (default: the system temp dir under
    ``pyautogui-agent/``) with a timestamped name, so failure-time
    screenshots never overwrite each other.
    """
    target_dir = directory or os.path.join(tempfile.gettempdir(),
                                           "pyautogui-agent")
    os.makedirs(target_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(target_dir, "screenshot-%s.png" % (stamp,))
    image.save(path)
    return path
