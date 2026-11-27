"""Structured screen elements on Windows via UI Automation.

UNVERIFIED: implemented from the UI Automation COM specification
(comtypes, IUIAutomation) and has NOT been run on Windows. It cannot
run on this Linux VM. Verify on a real Windows machine before relying
on it. The parts most likely to need correction on first contact with
a real system are the COM object creation (CLSID/ProgID), the
TreeWalker traversal, and the bounding-rectangle property access.

Install: ``pip install comtypes`` (``pip install
"pyautogui-agent[windows]"``). UI Automation is built into Windows;
no separate runtime is needed.

The provider walks the UI Automation tree from the desktop root
(all applications), breadth-first with the same depth and count
limits as the other providers, and returns the same ElementListing
and Element shape. Coordinates are screen pixels already, so the
``scale`` argument is accepted for a uniform provider signature and
ignored. Elements with a zero-area bounding rectangle are skipped:
they cannot be clicked and would pollute the list with bogus (0, 0)
centers.
"""

from __future__ import annotations

import sys

from .elements import Element, ElementListing, _unsupported_listing

_WINDOWS = sys.platform == "win32"

# CLSID of the CUIAutomation COM class. The ProgID is
# "UIAutomationCore.CUIAutomation".
_CUIAUTOMATION_CLSID = "{ff48dba4-60ef-4201-aa87-54103eef594e}"

# UIA_ValuePatternId, for reading an edit control's current text.
_VALUE_PATTERN_ID = 10002

# UIA control type ids (UIA_ControlTypeIds). Only the common ones are
# named; anything else falls back to "ControlType_<id>".
_CONTROL_TYPES = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50027: "Thumb",
    50028: "DataGrid",
    50029: "DataItem",
    50030: "Document",
    50031: "SplitButton",
    50032: "Window",
    50033: "Pane",
    50034: "Header",
    50035: "HeaderItem",
    50036: "Table",
    50037: "TitleBar",
    50038: "Separator",
    50039: "SemanticZoom",
    50040: "AppBar",
}


def list_elements_windows(max_depth=12, max_elements=500, scale=None):
    """List UI elements from the UI Automation tree.

    UNVERIFIED: implemented from the UI Automation specification and
    never run on Windows. ``scale`` is accepted for a uniform provider
    signature but is ignored: UI Automation coordinates are already
    screen pixels. Returns an ElementListing. When comtypes is missing
    or UI Automation cannot be reached, the listing has supported=False
    and a message saying so, never a crash.
    """
    if not _WINDOWS:
        # Never import comtypes on another platform. This guard is
        # what the unit test checks: the Windows provider must not
        # pull in comtypes (or any Windows-only module) on Linux/macOS.
        return _unsupported_listing(
            "The UI Automation provider only runs on Windows.")
    try:
        import comtypes.client
    except ImportError:
        return _unsupported_listing(
            "Element listing on Windows needs comtypes. Install it "
            "with: pip install \"pyautogui-agent[windows]\"")
    try:
        # UNVERIFIED: CLSID for CUIAutomation; ProgID alternative is
        # "UIAutomationCore.CUIAutomation".
        uia = comtypes.client.CreateObject(_CUIAUTOMATION_CLSID)
        root = uia.GetRootElement()
    except Exception as exc:
        return _unsupported_listing(
            "Could not connect to UI Automation (%s)." % (exc,))
    listing = ElementListing(elements=[], supported=True,
                             platform=sys.platform, message="")
    try:
        walker = uia.CreateTreeWalker(uia.CreateTrueCondition())
    except Exception as exc:
        return _unsupported_listing(
            "Could not create the UI Automation tree walker (%s)."
            % (exc,))
    # Breadth-first walk, so a huge tree is cut off by the count limit
    # before it can grow without bound.
    queue = [(root, 0)]
    visited = 0
    while queue and visited < max_elements:
        element, depth = queue.pop(0)
        visited += 1
        record = _to_element(element)
        if record is not None:
            listing.elements.append(record)
        if depth < max_depth:
            try:
                child = walker.GetFirstChildElement(element)
            except Exception:
                child = None
            while child is not None:
                queue.append((child, depth + 1))
                try:
                    child = walker.GetNextSiblingElement(child)
                except Exception:
                    child = None
    if visited >= max_elements:
        listing.message = ("Element walk stopped at the count limit "
                           "(%d elements)." % (max_elements,))
    return listing


def _to_element(element):
    """Build an Element record from one UI Automation element.

    Returns None when the element has no clickable area (a zero-area
    bounding rectangle) or its properties cannot be read.
    """
    try:
        rect = element.CurrentBoundingRectangle
        left, top = int(rect.left), int(rect.top)
        width, height = int(rect.right) - left, int(rect.bottom) - top
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    try:
        control_type = int(element.CurrentControlType)
    except Exception:
        control_type = -1
    role = _CONTROL_TYPES.get(control_type,
                              "ControlType_%d" % (control_type,))
    try:
        name = element.CurrentName
    except Exception:
        name = None
    if not isinstance(name, str) or not name:
        name = None
    try:
        help_text = element.CurrentHelpText
    except Exception:
        help_text = None
    if not isinstance(help_text, str) or not help_text:
        help_text = None
    try:
        enabled = bool(element.CurrentIsEnabled)
    except Exception:
        enabled = True
    try:
        visible = not bool(element.CurrentIsOffscreen)
    except Exception:
        visible = True
    value = None
    if role in ("Edit", "Document", "Text"):
        try:
            pattern = element.GetCurrentPattern(_VALUE_PATTERN_ID)
            value = pattern.Value
        except Exception:
            value = None
        if not isinstance(value, str):
            value = None
    return Element(
        role=role,
        title=name,
        description=help_text,
        position=(left, top),
        size=(width, height),
        enabled=enabled,
        value=value,
        visible=visible,
    )
