"""Tests for structured errors."""

from pyautogui_agent.errors import (
    ActionDeclinedError,
    ActionTimeoutError,
    AgentError,
    DisplayUnavailableError,
    ElementNotFoundError,
    NotSupportedError,
    ProviderNotInstalledError,
)


def test_all_errors_derive_from_agent_error():
    for cls in (ElementNotFoundError, ActionTimeoutError,
                ProviderNotInstalledError, NotSupportedError,
                ActionDeclinedError, DisplayUnavailableError):
        assert issubclass(cls, AgentError)


def test_element_not_found_carries_context():
    err = ElementNotFoundError("Submit", screenshot_path="/tmp/shot.png",
                               closest_match="Submti", confidence=0.71)
    assert err.query == "Submit"
    assert err.screenshot_path == "/tmp/shot.png"
    assert err.closest_match == "Submti"
    assert err.confidence == 0.71
    message = str(err)
    assert "Submit" in message
    assert "/tmp/shot.png" in message
    assert "Submti" in message


def test_element_not_found_without_optional_context():
    err = ElementNotFoundError("Cancel")
    assert err.screenshot_path is None
    assert err.closest_match is None
    assert "Cancel" in str(err)


def test_action_timeout_carries_context():
    err = ActionTimeoutError("image 'ok.png' to appear", timeout=5.0,
                             waited=5.0, last_screenshot="/tmp/last.png")
    assert err.what == "image 'ok.png' to appear"
    assert err.timeout == 5.0
    assert err.waited == 5.0
    assert err.last_screenshot == "/tmp/last.png"
    assert "/tmp/last.png" in str(err)


def test_provider_not_installed_carries_hint():
    err = ProviderNotInstalledError("Tesseract", "brew install tesseract")
    assert err.provider == "Tesseract"
    assert "brew install tesseract" in str(err)


def test_not_supported_carries_platform():
    err = NotSupportedError("Element listing", "linux",
                            "macOS only in V1.")
    assert err.platform == "linux"
    assert "linux" in str(err)
    assert "macOS only in V1." in str(err)


def test_action_declined_carries_action_and_args():
    err = ActionDeclinedError("click_point", {"x": 1, "y": 2})
    assert err.action == "click_point"
    assert err.action_args == {"x": 1, "y": 2}


def test_display_unavailable_message():
    err = DisplayUnavailableError("KeyError: 'DISPLAY'")
    assert "display" in str(err).lower()
