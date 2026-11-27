"""Structured screen elements on Linux via AT-SPI.

This provider walks the AT-SPI desktop tree (all applications) using
pyatspi, which wraps the AT-SPI D-Bus API. It collects role, name,
description, position (Component interface, screen coordinates),
size, enabled state, visibility, and, for text-like elements, the
current text value.

Install: ``sudo apt install python3-pyatspi at-spi2-core``. The
AT-SPI bus must be running (it normally starts with the desktop
session; under Xvfb start it with ``at-spi-bus-launcher`` or run
inside ``dbus-run-session``).

Live verification status: verified on this Ubuntu VM under Xvfb with
a GTK application (zenity). See TESTING.md for what the tree showed.
Positions are verified, not just the tree: a click on the listed OK
button's centre dismissed the dialog (scripts/atspi_click_test.py).
Position detail: getPosition(XY_SCREEN) returns (0, 0) for
descendants, so a top-level window's screen position comes from
XY_SCREEN and each descendant's screen position is that plus its
own XY_WINDOW offset. The provider returns a listing with
supported=False and a clear message when pyatspi is missing or the
AT-SPI registry cannot be reached, never a crash.

Note the difference from macOS: the macOS provider lists only the
focused application, while this provider lists the whole desktop
(all applications), because AT-SPI's desktop is the natural root.
The depth and count limits keep a large desktop bounded.
"""

from __future__ import annotations

import os
import sys

from .elements import Element, ElementListing, _unsupported_listing

_LINUX = sys.platform == "linux"

# Roles whose current text is collected as the element value. Other
# roles leave value None.
_TEXT_ROLES = {"entry", "text", "password text", "document text"}

# Cap on the text read from a text element, so a large document does
# not flood the listing.
_MAX_TEXT_LENGTH = 500


def _bus_available():
    """Return True when an AT-SPI bus is discoverable.

    libatspi aborts the whole process (SIGTRAP) when getDesktop is
    called with no D-Bus session bus to connect to, and Python cannot
    catch that. So this provider never calls getDesktop unless a bus
    address is visible in the environment. A desktop session (or
    dbus-run-session) sets DBUS_SESSION_BUS_ADDRESS, and the AT-SPI
    bus then auto-activates on demand. Residual risk, documented
    here: if the address is set but points at a dead bus, libatspi
    may still abort; that means the session itself is broken.
    """
    return bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")
                or os.environ.get("AT_SPI_BUS_ADDRESS"))


def list_elements_linux(max_depth=12, max_elements=500, scale=None):
    """List UI elements from the AT-SPI desktop tree.

    ``scale`` is accepted for a uniform provider signature but is
    ignored: AT-SPI positions are already screen pixels, not points.
    Returns an ElementListing. When pyatspi is missing, when no bus
    is discoverable, or when the AT-SPI registry cannot be reached,
    the listing has supported=False and a message saying so.
    """
    if not _LINUX:
        return _unsupported_listing(
            "The AT-SPI provider only runs on Linux.")
    if not _bus_available():
        return _unsupported_listing(
            "No D-Bus session bus found (DBUS_SESSION_BUS_ADDRESS is "
            "not set). The AT-SPI bus needs a logged-in GUI session, "
            "or a session bus started with dbus-run-session.")
    try:
        import pyatspi
    except ImportError:
        return _unsupported_listing(
            "Element listing on Linux needs pyatspi. Install it with: "
            "sudo apt install python3-pyatspi")
    try:
        desktop = pyatspi.Registry.getDesktop(0)
    except Exception as exc:
        return _unsupported_listing(
            "Could not connect to the AT-SPI registry (%s). Is the "
            "AT-SPI bus running and is there a logged-in GUI session?"
            % (exc,))
    listing = ElementListing(elements=[], supported=True,
                             platform=sys.platform, message="")
    # Breadth-first walk, so a huge tree is cut off by the count limit
    # before it can grow without bound. Each queued item carries the
    # screen position of its top-level window, because descendant
    # positions are computed from it (see _screen_position). The root
    # is seeded with (0, 0): the desktop is the screen origin, so a
    # node directly under it is already in screen coordinates.
    # (accessible, depth, toplevel_screen_pos, parent_is_application)
    queue = [(desktop, 0, (0, 0), False)]
    visited = 0
    while queue and visited < max_elements:
        acc, depth, toplevel_pos, parent_is_app = queue.pop(0)
        visited += 1
        role = _role_name(acc)
        position, size = _screen_position(acc, pyatspi, toplevel_pos,
                                          parent_is_app)
        if position is not None and size is not None:
            listing.elements.append(
                _to_element(acc, pyatspi, position, size))
        # The top-level screen position this node's children inherit:
        # for a top-level window it is the window's own screen
        # position; otherwise it is inherited from the parent.
        if parent_is_app:
            my_toplevel_pos = position
        else:
            my_toplevel_pos = toplevel_pos
        if depth < max_depth:
            try:
                count = acc.childCount
            except Exception:
                count = 0
            is_app = (role == "application")
            for i in range(count):
                try:
                    child = acc.getChildAtIndex(i)
                except Exception:
                    continue
                if child is not None:
                    queue.append((child, depth + 1, my_toplevel_pos,
                                  is_app))
    if visited >= max_elements:
        listing.message = ("Element walk stopped at the count limit "
                           "(%d elements)." % (max_elements,))
    return listing


def _role_name(acc):
    """Return an accessible's role name, or "unknown"."""
    try:
        role = acc.getRoleName()
    except Exception:
        return "unknown"
    return role if isinstance(role, str) and role else "unknown"


def _screen_position(acc, pyatspi, toplevel_pos, is_toplevel):
    """Return ((x, y), (width, height)) in screen pixels, or (None, None).

    Positions are the hard part of AT-SPI. Two findings from live
    testing under Xvfb (see TESTING.md):

    - ``getPosition(XY_SCREEN)`` is unreliable for descendants: it
      returned (0, 0) for every child of a dialog, even though the
      children sit at real offsets inside it. It appears to return
      the top-level window's position instead of the element's own.
    - ``getPosition(XY_WINDOW)`` is reliable for descendants: it
      returns the element's position relative to its top-level
      window (the OK button of a dialog reported (14, 166)).

    So a top-level window's screen position comes from XY_SCREEN
    (which is correct for the window itself), and a descendant's
    screen position is its top-level window's screen position plus
    its own XY_WINDOW offset. Elements with no Component interface
    are skipped as elements (their children are still walked).
    """
    try:
        comp = acc.queryComponent()
    except Exception:
        comp = None
    if comp is None:
        return None, None
    try:
        width, height = comp.getSize()
        size = (int(width), int(height))
    except Exception:
        return None, None
    if is_toplevel:
        for coord in (pyatspi.XY_SCREEN, pyatspi.XY_WINDOW):
            try:
                x, y = comp.getPosition(coord)
                return (int(x), int(y)), size
            except Exception:
                continue
        return None, None
    if toplevel_pos is None:
        return None, None
    try:
        x, y = comp.getPosition(pyatspi.XY_WINDOW)
        return (toplevel_pos[0] + int(x), toplevel_pos[1] + int(y)), size
    except Exception:
        return None, None


def _safe_str(acc, attribute):
    """Return a string attribute of an accessible, or None."""
    try:
        value = getattr(acc, attribute)
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _to_element(acc, pyatspi, position, size):
    """Build an Element record from one accessible."""
    try:
        role = acc.getRoleName()
    except Exception:
        role = "unknown"
    if not isinstance(role, str) or not role:
        role = "unknown"
    enabled = True
    visible = True
    try:
        state = acc.getState()
        enabled = state.contains(pyatspi.STATE_ENABLED)
        visible = state.contains(pyatspi.STATE_SHOWING)
    except Exception:
        pass
    value = None
    if role in _TEXT_ROLES:
        try:
            text = acc.queryText()
            value = text.get_text(0, _MAX_TEXT_LENGTH)
        except Exception:
            value = None
        if not isinstance(value, str):
            value = None
    return Element(
        role=role,
        title=_safe_str(acc, "name"),
        description=_safe_str(acc, "description"),
        position=position,
        size=size,
        enabled=enabled,
        value=value,
        visible=visible,
    )
