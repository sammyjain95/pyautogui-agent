"""Structured screen elements via the OS accessibility layer.

UNVERIFIED: the macOS path in this module is implemented from the
Accessibility API specification (ApplicationServices.AXUIElement,
pyobjc) and has NOT been run on a Mac. It cannot run on this Linux VM.
Verify with ``scripts/mac_live_test.py`` on the owner's Mac before
relying on it. Everything else in this module (the data records, the
platform guard, the search helpers) is covered by unit tests.

Why this exists: PyAutoGUI only understands pixels. An agent that wants
to click a button must guess coordinates or supply a reference image.
The accessibility tree answers "what buttons exist, what are they
called, and where are they" directly.

Coordinate note: Accessibility positions are in points. PyAutoGUI
coordinates are in pixels. On Retina displays one point is two pixels,
so positions are scaled by the display backing scale factor, detected
from ``NSScreen.mainScreen().backingScaleFactor()``, with an explicit
``scale`` override when the caller knows better.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from .errors import NotSupportedError
from .safety import get_default_session
from ._util import get_pyautogui

# Attribute failures are skipped, not fatal: many elements do not
# expose every attribute, and a single unreadable element must not
# break the whole walk.


@dataclass
class Element:
    """One UI element from the accessibility tree.

    All coordinates are PyAutoGUI pixel coordinates (points scaled by
    the backing scale factor), with (0, 0) at the top-left of the
    primary display.
    """

    role: str
    title: str | None
    description: str | None
    position: tuple
    size: tuple
    enabled: bool = True
    value: str | None = None
    visible: bool = True
    center: tuple = field(init=False)

    def __post_init__(self):
        x, y = self.position
        width, height = self.size
        self.center = (x + width / 2.0, y + height / 2.0)


@dataclass
class ElementListing:
    """The result of list_elements().

    ``supported`` is False on platforms without an element provider
    yet, or when the provider for the platform is not installed.
    Callers must check it; the list is never silently empty on an
    unsupported platform.
    """

    elements: list
    supported: bool
    platform: str
    message: str
    scale: float | None = None
    app_name: str | None = None


def _unsupported_listing(message):
    return ElementListing(elements=[], supported=False,
                          platform=sys.platform, message=message)


def _dispatch(platform):
    """Return the element provider function for a platform string.

    Returns None when no provider exists for the platform. The
    providers are imported lazily so importing this module never
    pulls in pyobjc, pyatspi, or comtypes. Tests call this directly
    with a platform string to check dispatch without changing the
    real platform.
    """
    if platform == "darwin":
        return _list_elements_macos
    if platform == "linux":
        from .elements_linux import list_elements_linux
        return list_elements_linux
    if platform == "win32":
        from .elements_windows import list_elements_windows
        return list_elements_windows
    return None


def list_elements(max_depth=12, max_elements=500, scale=None):
    """List the UI elements of the focused application (macOS) or of
    the desktop (Linux, Windows).

    Returns an ElementListing. The provider depends on the platform:
    macOS walks the accessibility tree of the focused application,
    Linux walks the AT-SPI desktop tree (all applications), and
    Windows walks the UI Automation tree from the desktop root. All
    three are depth- and count-limited and return the same
    ElementListing and Element shape. On a platform with no provider,
    or when the provider is not installed, the listing has
    ``supported`` False and a message saying so, never a silent
    empty list.
    """
    provider = _dispatch(sys.platform)
    if provider is None:
        return _unsupported_listing(
            "Element listing is not supported on %s yet."
            % (sys.platform,))
    return provider(max_depth=max_depth, max_elements=max_elements,
                    scale=scale)


def _list_elements_macos(max_depth, max_elements, scale):
    # UNVERIFIED: implemented from the Accessibility API specification.
    # Requires pyobjc on the Mac: pip install "pyautogui-agent[macos]".
    try:
        from ApplicationServices import (
            AXUIElementCreateSystemWide,
            AXUIElementCopyAttributeValue,
            AXValueGetValue,
            kAXChildrenAttribute,
            kAXDescriptionAttribute,
            kAXEnabledAttribute,
            kAXErrorSuccess,
            kAXFocusedApplicationAttribute,
            kAXPositionAttribute,
            kAXRoleAttribute,
            kAXSizeAttribute,
            kAXTitleAttribute,
            kAXValueAttribute,
            kAXValueCGPointType,
            kAXValueCGSizeType,
        )
    except ImportError:
        return _unsupported_listing(
            "Element listing needs pyobjc on macOS. Install it with: "
            "pip install \"pyautogui-agent[macos]\"")

    if scale is None:
        scale = _backing_scale_factor()
    listing = ElementListing(elements=[], supported=True,
                             platform=sys.platform, scale=scale,
                             message="")

    def ax_attr(element, attribute):
        """Read one accessibility attribute, or None when unreadable."""
        try:
            error, value = AXUIElementCopyAttributeValue(
                element, attribute, None)
        except Exception:
            return None
        if error != kAXErrorSuccess:
            return None
        return value

    def ax_point(ax_value):
        """Convert an AXValue holding a CGPoint to an (x, y) tuple."""
        if ax_value is None:
            return None
        try:
            result = AXValueGetValue(ax_value, kAXValueCGPointType, None)
        except Exception:
            return None
        # pyobjc returns (success, point) for out parameters.
        if isinstance(result, tuple) and len(result) == 2:
            ok, point = result
            if not ok or point is None:
                return None
            return (float(point[0]), float(point[1]))
        return None

    def ax_size(ax_value):
        """Convert an AXValue holding a CGSize to a (width, height) tuple."""
        if ax_value is None:
            return None
        try:
            result = AXValueGetValue(ax_value, kAXValueCGSizeType, None)
        except Exception:
            return None
        if isinstance(result, tuple) and len(result) == 2:
            ok, size = result
            if not ok or size is None:
                return None
            return (float(size[0]), float(size[1]))
        return None

    try:
        system_wide = AXUIElementCreateSystemWide()
        focused_app = ax_attr(system_wide, kAXFocusedApplicationAttribute)
    except Exception:
        focused_app = None
    if focused_app is None:
        listing.message = "No focused application found."
        return listing

    app_title = ax_attr(focused_app, kAXTitleAttribute)
    if isinstance(app_title, str):
        listing.app_name = app_title

    # Breadth-first walk, so a huge tree is cut off by the count limit
    # before it can grow without bound.
    queue = [(focused_app, 0)]
    visited = 0
    while queue and visited < max_elements:
        element, depth = queue.pop(0)
        visited += 1
        role = ax_attr(element, kAXRoleAttribute)
        if not isinstance(role, str):
            role = "unknown"
        position = ax_point(ax_attr(element, kAXPositionAttribute))
        size = ax_size(ax_attr(element, kAXSizeAttribute))
        if position is not None and size is not None:
            title = ax_attr(element, kAXTitleAttribute)
            description = ax_attr(element, kAXDescriptionAttribute)
            value = ax_attr(element, kAXValueAttribute)
            enabled = ax_attr(element, kAXEnabledAttribute)
            listing.elements.append(Element(
                role=role,
                title=title if isinstance(title, str) else None,
                description=(description
                             if isinstance(description, str) else None),
                position=(position[0] * scale, position[1] * scale),
                size=(size[0] * scale, size[1] * scale),
                enabled=bool(enabled) if enabled is not None else True,
                value=value if isinstance(value, str) else None,
            ))
        if depth < max_depth:
            children = ax_attr(element, kAXChildrenAttribute)
            if children:
                for child in children:
                    queue.append((child, depth + 1))
    if visited >= max_elements:
        listing.message = ("Element walk stopped at the count limit "
                           "(%d elements)." % (max_elements,))
    return listing


def _backing_scale_factor():
    """Return the main display backing scale factor, or 1.0.

    UNVERIFIED: implemented from the AppKit specification.
    """
    try:
        from AppKit import NSScreen
        screen = NSScreen.mainScreen()
        if screen is not None:
            return float(screen.backingScaleFactor())
    except Exception:
        pass
    return 1.0


def _matches(element, role, title, title_contains, description):
    if role is not None and element.role != role:
        return False
    if title is not None and element.title != title:
        return False
    if title_contains is not None:
        haystack = element.title or ""
        if title_contains.lower() not in haystack.lower():
            return False
    if description is not None and element.description != description:
        return False
    return True


def find_all(role=None, title=None, title_contains=None, description=None,
             max_depth=12, max_elements=500, scale=None):
    """Return all elements matching the given filters, or raise.

    Raises NotSupportedError on platforms without an element provider.
    Returns an empty list when nothing matches.
    """
    listing = list_elements(max_depth=max_depth, max_elements=max_elements,
                            scale=scale)
    if not listing.supported:
        raise NotSupportedError("Element listing", listing.platform,
                                listing.message)
    return [element for element in listing.elements
            if _matches(element, role, title, title_contains, description)]


def find_element(role=None, title=None, title_contains=None,
                 description=None, max_depth=12, max_elements=500,
                 scale=None):
    """Return the first element matching the filters, or None.

    Raises NotSupportedError on platforms without an element provider.
    """
    matches = find_all(role=role, title=title,
                       title_contains=title_contains,
                       description=description, max_depth=max_depth,
                       max_elements=max_elements, scale=scale)
    return matches[0] if matches else None


def click_element(element, session=None):
    """Click the center of an Element, through the safety layer."""
    session = session or get_default_session()
    pg = get_pyautogui()
    x, y = element.center
    return session.execute(
        "click_element",
        {"role": element.role, "title": element.title, "x": x, "y": y},
        lambda: pg.click(x, y),
        result_summary="clicked (%s, %s)" % (x, y))
