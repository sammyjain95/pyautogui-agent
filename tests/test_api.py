"""Tests for the public API surface and lazy importing."""

import os
import subprocess
import sys

import pyautogui_agent

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_all_public_names_are_accessible():
    for name in pyautogui_agent.__all__:
        assert hasattr(pyautogui_agent, name), name
    assert pyautogui_agent.__version__ == "0.2.0"


def test_lazy_import_of_pyautogui():
    # In a fresh interpreter, importing pyautogui_agent must NOT import
    # pyautogui (which would fail headless). This runs as a subprocess
    # so the parent process's stub injection cannot mask it.
    code = ("import sys; import pyautogui_agent; "
            "print('pyautogui' in sys.modules)")
    env = dict(os.environ)
    env.pop("DISPLAY", None)
    env["PYTHONPATH"] = REPO_ROOT
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_unknown_attribute_raises():
    try:
        pyautogui_agent.does_not_exist
    except AttributeError:
        pass
    else:
        raise AssertionError("expected AttributeError")
