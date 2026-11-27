"""Structured errors for pyautogui_agent.

Every error carries the context an agent needs to self-correct: what was
looked for, what the screen showed when it gave up, and what to install
when a capability is missing. Plain ``None`` returns are never used for
failures in this package.
"""

from __future__ import annotations


class AgentError(Exception):
    """Base class for all errors raised by pyautogui_agent."""


class ElementNotFoundError(AgentError):
    """Raised when a UI element or on-screen text could not be found.

    Attributes:
        query: what was looked for (element title, text, or image name).
        screenshot_path: path of the screenshot saved at failure time,
            or None when no screenshot could be taken.
        closest_match: the nearest text or element found, if any.
        confidence: confidence of the closest match, 0.0 to 1.0, if known.
    """

    def __init__(self, query, screenshot_path=None, closest_match=None,
                 confidence=None):
        self.query = query
        self.screenshot_path = screenshot_path
        self.closest_match = closest_match
        self.confidence = confidence
        parts = ["Could not find %r on screen." % (query,)]
        if closest_match is not None:
            if confidence is not None:
                parts.append("Closest match: %r (confidence %.2f)."
                             % (closest_match, confidence))
            else:
                parts.append("Closest match: %r." % (closest_match,))
        if screenshot_path is not None:
            parts.append("Screenshot saved to: %s" % (screenshot_path,))
        super().__init__(" ".join(parts))


class ActionTimeoutError(AgentError):
    """Raised when a wait gives up before its condition became true.

    Attributes:
        what: description of what was waited for.
        timeout: the timeout that was configured, in seconds.
        waited: how long was actually waited, in seconds.
        last_screenshot: path of the screenshot taken at give-up time,
            or None when no screenshot could be taken.
    """

    def __init__(self, what, timeout, waited, last_screenshot=None):
        self.what = what
        self.timeout = timeout
        self.waited = waited
        self.last_screenshot = last_screenshot
        message = ("Timed out after %.1f seconds waiting for %s "
                   "(timeout %.1f seconds)."
                   % (waited, what, timeout))
        if last_screenshot is not None:
            message += " Last screenshot: %s" % (last_screenshot,)
        super().__init__(message)


class ProviderNotInstalledError(AgentError):
    """Raised when an optional capability is needed but not installed.

    Attributes:
        provider: name of the missing provider (for example "Tesseract").
        install_hint: concrete install instructions for the provider.
    """

    def __init__(self, provider, install_hint):
        self.provider = provider
        self.install_hint = install_hint
        super().__init__("%s is not installed. %s" % (provider, install_hint))


class NotSupportedError(AgentError):
    """Raised when a feature is not supported on the current platform.

    Attributes:
        feature: what was attempted.
        platform: the platform string (``sys.platform``).
        detail: extra detail, for example what is needed instead.
    """

    def __init__(self, feature, platform, detail=""):
        self.feature = feature
        self.platform = platform
        self.detail = detail
        message = ("%s is not supported on %s yet."
                   % (feature, platform))
        if detail:
            message += " " + detail
        super().__init__(message)


class ActionDeclinedError(AgentError):
    """Raised when the confirmation hook declines an action.

    Attributes:
        action: the action that was declined.
        action_args: the arguments the action was called with.
            (Named ``action_args``, not ``args``: BaseException coerces
            any value assigned to ``.args`` into a tuple, so a dict
            stored there would silently lose its values.)
    """

    def __init__(self, action, args=None):
        self.action = action
        self.action_args = args or {}
        super().__init__("Action declined by confirmation hook: %s %s"
                         % (action, self.action_args))


class DisplayUnavailableError(AgentError):
    """Raised when PyAutoGUI cannot connect to a display.

    This happens on a headless machine (no X server, no logged-in GUI
    session). The package itself imports cleanly without a display;
    this error only appears when an action that needs the screen is
    attempted.
    """

    def __init__(self, detail=""):
        self.detail = detail
        message = ("PyAutoGUI could not connect to a display. "
                   "Run on a machine with a logged-in GUI session.")
        if detail:
            message += " Detail: %s" % (detail,)
        super().__init__(message)
