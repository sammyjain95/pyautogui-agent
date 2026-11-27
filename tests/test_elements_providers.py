"""Tests for the element providers: dispatch, AT-SPI (fake), Windows guard."""

import sys
import types

from pyautogui_agent.elements import _dispatch, _list_elements_macos
from pyautogui_agent.elements_linux import list_elements_linux
from pyautogui_agent.elements_windows import list_elements_windows


def test_dispatch_returns_macos_provider():
    assert _dispatch("darwin") is _list_elements_macos


def test_dispatch_returns_linux_provider():
    assert _dispatch("linux") is list_elements_linux


def test_dispatch_returns_windows_provider():
    assert _dispatch("win32") is list_elements_windows


def test_dispatch_returns_none_for_unknown_platform():
    assert _dispatch("freebsd") is None
    assert _dispatch("sunos") is None


class FakeState:
    def __init__(self, states):
        self._states = set(states)

    def contains(self, state):
        return state in self._states


class FakeComponent:
    """Stand-in for a pyatspi Component.

    Models the live AT-SPI behaviour found under Xvfb (see TESTING.md):
    XY_SCREEN is correct for a top-level window but returns (0, 0)
    for descendants (it appears to return the top-level window's
    position instead of the element's own), while XY_WINDOW returns
    the element's position relative to its top-level window and is
    correct for descendants. ``is_toplevel`` marks a top-level
    window, for which XY_SCREEN returns the true screen position.
    """

    def __init__(self, screen_position, window_position, is_toplevel,
                 size):
        self._screen_position = screen_position
        self._window_position = window_position
        self._is_toplevel = is_toplevel
        self._size = size

    def getPosition(self, coord_type):
        if coord_type == "XY_WINDOW":
            return self._window_position
        if self._is_toplevel:
            return self._screen_position
        return (0, 0)

    def getSize(self):
        return self._size


class FakeText:
    def __init__(self, text):
        self._text = text

    def get_text(self, start, end):
        return self._text[start:end if end >= 0 else None]


class FakeAccessible:
    """Minimal stand-in for a pyatspi Accessible.

    ``position`` is the true screen position (the ground truth the
    provider must compute); ``window_position`` is the position
    relative to the top-level window; ``is_toplevel`` marks a
    top-level window (a direct child of an application).
    """

    def __init__(self, role, name=None, description=None, position=None,
                 size=None, children=None, text=None, states=None,
                 window_position=None, is_toplevel=False):
        self._role = role
        self.name = name
        self.description = description
        self._position = position
        self._size = size
        self._children = children or []
        self._text = text
        self._states = (states if states is not None
                        else {"enabled", "showing"})
        self._window_position = (window_position if window_position
                                 is not None else position)
        self._is_toplevel = is_toplevel

    def getRoleName(self):
        return self._role

    def getState(self):
        return FakeState(self._states)

    def queryComponent(self):
        if self._position is None:
            raise Exception("no component interface")
        return FakeComponent(self._position, self._window_position,
                             self._is_toplevel, self._size)

    @property
    def childCount(self):
        return len(self._children)

    def getChildAtIndex(self, i):
        return self._children[i]

    def queryText(self):
        if self._text is None:
            raise Exception("no text interface")
        return FakeText(self._text)


def build_fake_pyatspi(desktop):
    module = types.ModuleType("pyatspi")
    module.XY_SCREEN = "XY_SCREEN"
    module.XY_WINDOW = "XY_WINDOW"
    module.STATE_ENABLED = "enabled"
    module.STATE_SHOWING = "showing"

    class Registry:
        @staticmethod
        def getDesktop(index):
            return desktop

    module.Registry = Registry
    return module


def _fake_tree():
    # The frame is the top-level window at screen (100, 100). Its
    # children are given window-relative positions, so the provider
    # must compute their screen positions as toplevel + offset:
    # entry (100, 100) + (100, 100) = (200, 200); button
    # (100, 100) + (100, 200) = (200, 300). XY_SCREEN for the
    # children returns (0, 0) (the live broken behaviour), so a
    # provider that used it would report the wrong positions.
    button = FakeAccessible("push button", name="Submit",
                            description="Submit the form",
                            position=(200, 300), size=(100, 40),
                            window_position=(100, 200))
    entry = FakeAccessible("entry", name="Name",
                           position=(200, 200), size=(200, 30),
                           text="hello", window_position=(100, 100))
    window = FakeAccessible("frame", name="Test Window",
                            position=(100, 100), size=(800, 600),
                            children=[entry, button],
                            window_position=(100, 100),
                            is_toplevel=True)
    app = FakeAccessible("application", name="TestApp",
                         position=(0, 0), size=(1920, 1080),
                         children=[window], window_position=(0, 0))
    desktop = FakeAccessible("desktop", name=None, position=None,
                             size=None, children=[app])
    return desktop


def test_linux_provider_walks_fake_atspi_tree(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake")
    monkeypatch.setitem(sys.modules, "pyatspi",
                        build_fake_pyatspi(_fake_tree()))
    listing = list_elements_linux()
    assert listing.supported is True
    assert listing.platform == sys.platform
    # Breadth-first: application, frame, entry, push button. The
    # desktop root has no component, so it is walked but not listed.
    assert [e.title for e in listing.elements] == [
        "TestApp", "Test Window", "Name", "Submit"]
    button = listing.elements[-1]
    assert button.role == "push button"
    # The button's screen position is computed as the top-level
    # window's (100, 100) plus its window-relative (100, 200), not
    # from XY_SCREEN (which the fake returns as (0, 0) for children).
    assert button.position == (200, 300)
    assert button.size == (100, 40)
    assert button.center == (250.0, 320.0)
    assert button.description == "Submit the form"
    assert button.enabled is True
    assert button.visible is True
    entry = listing.elements[2]
    assert entry.role == "entry"
    assert entry.position == (200, 200)
    assert entry.value == "hello"
    window = listing.elements[1]
    assert window.position == (100, 100)


def test_linux_provider_without_bus_never_touches_pyatspi(monkeypatch):
    # No bus address in the environment: the provider must return
    # its explicit failure listing WITHOUT calling getDesktop, because
    # libatspi aborts the whole process (SIGTRAP) when getDesktop is
    # called with no bus. The fake pyatspi here raises if getDesktop
    # is ever called, so the test fails loudly if the guard is bypassed.
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("AT_SPI_BUS_ADDRESS", raising=False)

    class GuardedRegistry:
        @staticmethod
        def getDesktop(index):
            raise AssertionError("getDesktop must not be called "
                                 "without a bus")

    module = types.ModuleType("pyatspi")
    module.XY_SCREEN = "XY_SCREEN"
    module.STATE_ENABLED = "enabled"
    module.STATE_SHOWING = "showing"
    module.Registry = GuardedRegistry
    monkeypatch.setitem(sys.modules, "pyatspi", module)
    listing = list_elements_linux()
    assert listing.supported is False
    assert listing.elements == []
    assert "bus" in listing.message.lower()
    assert "AT-SPI" in listing.message


def test_linux_provider_without_pyatspi_returns_clear_message(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake")
    monkeypatch.setitem(sys.modules, "pyatspi", None)
    listing = list_elements_linux()
    assert listing.supported is False
    assert listing.elements == []
    assert "pyatspi" in listing.message
    assert "apt install" in listing.message


def test_linux_provider_registry_failure_returns_clear_message(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake")
    module = types.ModuleType("pyatspi")
    module.XY_SCREEN = "XY_SCREEN"
    module.STATE_ENABLED = "enabled"
    module.STATE_SHOWING = "showing"

    class FailingRegistry:
        @staticmethod
        def getDesktop(index):
            raise Exception("cannot connect to accessibility bus")

    module.Registry = FailingRegistry
    monkeypatch.setitem(sys.modules, "pyatspi", module)
    listing = list_elements_linux()
    assert listing.supported is False
    assert "AT-SPI" in listing.message


def test_windows_provider_not_imported_on_non_windows():
    assert "comtypes" not in sys.modules
    listing = list_elements_windows()
    assert listing.supported is False
    assert listing.elements == []
    assert "Windows" in listing.message
    # The guard must return before importing comtypes.
    assert "comtypes" not in sys.modules
