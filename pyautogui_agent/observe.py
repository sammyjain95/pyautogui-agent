"""The agent observation primitive.

One call returns everything an agent needs to decide its next move:
a screenshot, the screen size, the mouse position, and (when
available) the structured element list. Without this, the agent has
to assemble the same picture from four separate calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .elements import ElementListing, list_elements
from ._util import get_pyautogui


@dataclass
class Observation:
    """The result of observe().

    screenshot is a Pillow image, or None when no screenshot was
    taken. screen_size and mouse_position are (x, y) tuples, or None
    when they could not be read. elements is the ElementListing, or
    None when element listing was not requested.
    """

    screenshot: object | None
    screen_size: tuple | None
    mouse_position: tuple | None
    elements: ElementListing | None
    timestamp: datetime

    def save_screenshot(self, path):
        """Save the observation screenshot to path. No-op when None."""
        if self.screenshot is not None:
            self.screenshot.save(path)


def observe(include_elements=True, take_screenshot=True, scale=None):
    """Take one observation of the current screen state.

    Args:
        include_elements: when True, include the accessibility element
            list. On platforms without an element provider the listing
            is included with ``supported`` False, not omitted.
        take_screenshot: when False, skip the screenshot (faster, and
            avoids storing image data when only the element list is
            needed).
        scale: backing scale factor override passed to list_elements.
    """
    pg = get_pyautogui()
    screenshot = pg.screenshot() if take_screenshot else None
    size = pg.size()
    position = pg.position()
    listing = None
    if include_elements:
        listing = list_elements(scale=scale)
    return Observation(screenshot=screenshot, screen_size=size,
                       mouse_position=position, elements=listing,
                       timestamp=datetime.now())
