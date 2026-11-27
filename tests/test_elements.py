"""Tests for elements: records, platform guard, search helpers."""

import sys

import pytest

from pyautogui_agent.elements import (
    Element,
    ElementListing,
    find_all,
    find_element,
    list_elements,
)
from pyautogui_agent.errors import NotSupportedError


def test_element_center_is_computed():
    el = Element(role="AXButton", title="OK", description=None,
                 position=(100, 200), size=(60, 20))
    assert el.center == (130.0, 210.0)
    assert el.enabled is True


def test_element_listing_defaults():
    listing = ElementListing(elements=[], supported=False,
                             platform="linux", message="no provider")
    assert listing.scale is None
    assert listing.app_name is None


def test_list_elements_on_linux_is_explicit_not_silent():
    listing = list_elements()
    assert listing.supported is False
    assert listing.elements == []
    assert listing.platform == sys.platform
    assert "not supported" in listing.message.lower()
    assert sys.platform in listing.message


def test_find_element_raises_not_supported_on_linux():
    with pytest.raises(NotSupportedError) as excinfo:
        find_element(title="OK")
    assert excinfo.value.platform == sys.platform


def test_find_all_raises_not_supported_on_linux():
    with pytest.raises(NotSupportedError):
        find_all(role="AXButton")
