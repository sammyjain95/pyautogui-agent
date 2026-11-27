#!/usr/bin/env python3
"""Live test for pyautogui_agent on the owner's Mac.

Run: python3 scripts/mac_live_test.py

This script NEVER clicks anything real. The only action it performs
is a dry-run click through a dry-run Session, which is logged and not
executed. It prints what it finds so the result can be checked by eye:

- the accessibility element list (role, title, center) for the
  focused application,
- one observe() call (screen size, mouse position, screenshot size),
- one dry-run action and the resulting action log.

UNVERIFIED: the macOS element listing is implemented from the
Accessibility API specification and has not been run yet. This script
is the first run. Expect rough edges: report what it prints.

Prereqs on the Mac: the package installed (pip install -e . from the
repo root), a logged-in GUI session, and for element listing the
macOS extra (pip install "pyautogui-agent[macos]"). Accessibility
permission may be needed: System Settings, Privacy and Security,
Accessibility, allow the terminal (or the app running this script).
"""

import os
import platform
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def header(title):
    print("\n=== %s ===" % (title,))


def main():
    print("pyautogui-agent live test")
    print("platform: %s %s" % (platform.system(), platform.release()))
    print("python: %s" % (sys.version.split()[0]))
    print("UNVERIFIED RUN: element listing has not been run on a Mac before.")

    try:
        import pyautogui_agent
        from pyautogui_agent import Session, click_point, list_elements, observe
    except Exception:
        print("FAILED to import pyautogui_agent:")
        traceback.print_exc()
        return 1

    print("pyautogui_agent version: %s" % (pyautogui_agent.__version__,))

    header("1. Element list (focused application)")
    try:
        listing = list_elements()
        print("supported: %s" % (listing.supported,))
        print("platform: %s" % (listing.platform,))
        print("scale (backing factor): %s" % (listing.scale,))
        print("focused app: %s" % (listing.app_name,))
        print("message: %s" % (listing.message,))
        print("elements found: %d" % (len(listing.elements),))
        for element in listing.elements[:25]:
            print("  %-12s title=%r center=(%.0f, %.0f) enabled=%s"
                  % (element.role, element.title, element.center[0],
                     element.center[1], element.enabled))
        if len(listing.elements) > 25:
            print("  ... and %d more" % (len(listing.elements) - 25,))
    except Exception:
        print("FAILED to list elements:")
        traceback.print_exc()

    header("2. observe()")
    try:
        obs = observe()
        print("screen size: %s" % (obs.screen_size,))
        print("mouse position: %s" % (obs.mouse_position,))
        if obs.screenshot is not None:
            print("screenshot size: %s" % (obs.screenshot.size,))
            out_dir = "/tmp/pyautogui-agent-live"
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, "observe.png")
            obs.save_screenshot(path)
            print("screenshot saved to: %s" % (path,))
        else:
            print("screenshot: None")
        if obs.elements is not None:
            print("elements in observation: %d (supported=%s)"
                  % (len(obs.elements.elements), obs.elements.supported))
    except Exception:
        print("FAILED to observe:")
        traceback.print_exc()

    header("3. Dry-run action (nothing is clicked)")
    try:
        session = Session(dry_run=True)
        result = click_point(500, 500, session=session)
        print("click_point returned: %r (None means dry run)" % (result,))
        for line in session.format_log():
            print("  " + line)
        print("If the mouse did not move, dry-run mode works.")
    except Exception:
        print("FAILED dry-run action:")
        traceback.print_exc()

    print("\nDone. Check the output above, then report what worked and "
          "what did not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
