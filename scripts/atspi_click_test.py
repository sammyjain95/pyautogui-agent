"""End-to-end click test for the AT-SPI Linux provider.

Launches a zenity dialog, finds its OK button through the package's
AT-SPI element listing, clicks the button's centre, and reports
whether zenity exited (which proves the reported position is the
button's real screen position, not a stale or zero coordinate).

Run under a session bus and Xvfb, e.g.:
    dbus-run-session -- xvfb-run -a -s "-screen 0 1920x1080x24" \
        python3 scripts/atspi_click_test.py

Exit code 0 means the click dismissed the dialog.
"""

import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from pyautogui_agent import click_point, list_elements


def main():
    zenity = subprocess.Popen(
        ["zenity", "--info", "--title=Probe Window",
         "--text=AT-SPI probe window", "--width=400", "--height=200"])
    time.sleep(3.0)
    try:
        listing = list_elements()
        if not listing.supported:
            print("listing not supported:", listing.message)
            return 1
        ok = None
        for element in listing.elements:
            if element.role == "push button" and element.title == "OK":
                ok = element
                break
        if ok is None:
            print("OK button not found in listing")
            return 1
        cx, cy = ok.center
        print("OK button at pos=%s size=%s center=(%s, %s)"
              % (ok.position, ok.size, cx, cy))
        click_point(int(cx), int(cy))
        print("clicked centre (%s, %s)" % (int(cx), int(cy)))
        try:
            zenity.wait(timeout=5)
            print("zenity exited with code %s: click landed on OK"
                  % (zenity.returncode,))
            return 0
        except subprocess.TimeoutExpired:
            print("zenity still running after 5s: click missed the OK "
                  "button")
            return 1
    finally:
        if zenity.poll() is None:
            zenity.terminate()
            try:
                zenity.wait(timeout=5)
            except subprocess.TimeoutExpired:
                zenity.kill()


if __name__ == "__main__":
    sys.exit(main())
