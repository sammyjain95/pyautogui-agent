"""pyautogui_agent: an agent-friendly companion layer on top of PyAutoGUI.

PyAutoGUI only understands pixels. This package adds what an agent
needs to drive a desktop: a structured element list, one-call
observation, waits with deadlines, task-level actions (click by text,
fill a field), structured errors that carry screenshots, and a safety
layer (dry-run mode, action log, confirmation hook).

Importing this package never touches the display. PyAutoGUI itself is
imported lazily, inside the functions that need it, because importing
PyAutoGUI on a headless machine fails. The failure only appears when
an action that needs the screen is attempted, as
DisplayUnavailableError.

The public names are imported eagerly here (none of the submodules
imports PyAutoGUI at module level, so this is still display-free).
Eager import matters for one name: the ``observe`` function lives in
the ``observe`` module, and a lazy loader would let
``from pyautogui_agent import observe`` bind the module instead of
the function once the submodule had been imported anywhere.

UNVERIFIED: the macOS element listing is implemented from the
Accessibility API specification and has not been run on a Mac. See
``elements.py`` and ``scripts/mac_live_test.py``.
"""

from __future__ import annotations

from .actions import click_image, click_point, click_text, fill_field
from .elements import (
    Element,
    ElementListing,
    click_element,
    find_all,
    find_element,
    list_elements,
)
from .errors import (
    ActionDeclinedError,
    ActionTimeoutError,
    AgentError,
    DisplayUnavailableError,
    ElementNotFoundError,
    NotSupportedError,
    ProviderNotInstalledError,
)
from .observe import Observation, observe
from .safety import (
    ActionRecord,
    Session,
    dry_run,
    get_default_session,
    set_default_session,
)
from .wait import wait_for_condition, wait_for_image

__version__ = "0.1.0"

__all__ = [
    # errors
    "AgentError",
    "ElementNotFoundError",
    "ActionTimeoutError",
    "ProviderNotInstalledError",
    "NotSupportedError",
    "ActionDeclinedError",
    "DisplayUnavailableError",
    # safety
    "Session",
    "ActionRecord",
    "get_default_session",
    "set_default_session",
    "dry_run",
    # elements
    "Element",
    "ElementListing",
    "list_elements",
    "find_element",
    "find_all",
    "click_element",
    # observe
    "Observation",
    "observe",
    # wait
    "wait_for_image",
    "wait_for_condition",
    # actions
    "click_text",
    "click_image",
    "click_point",
    "fill_field",
]


def __dir__():
    return sorted(__all__)
