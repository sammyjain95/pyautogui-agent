"""Live probe of the Linux AT-SPI element provider.

Starts a GTK application (zenity) and the tkinter test app under
Xvfb with a D-Bus session bus, then runs list_elements() for real and
prints what the AT-SPI tree contains.

Run: dbus-run-session -- xvfb-run -a -s "-screen 0 1920x1080x24" \
         python3 scripts/atspi_live_probe.py

Requires: python3-pyatspi, at-spi2-core, zenity. The AT-SPI bus
auto-activates on demand once a session bus exists; no manual
at-spi-bus-launcher step is needed.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import pyautogui_agent as agent

    procs = []
    try:
        zenity = subprocess.Popen(
            ["zenity", "--info", "--title=Probe Window",
             "--text=AT-SPI probe window", "--width=400", "--height=200"])
        procs.append(zenity)
        app = subprocess.Popen(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "vm_live_test_app.py")])
        procs.append(app)
        time.sleep(3.0)  # let both windows draw and register with AT-SPI

        listing = agent.list_elements()
        print(f"supported={listing.supported} platform={listing.platform}")
        print(f"message={listing.message!r}")
        print(f"elements={len(listing.elements)}")
        roles = {}
        for el in listing.elements:
            roles[el.role] = roles.get(el.role, 0) + 1
        print("roles:", dict(sorted(roles.items())))
        print("--- first 25 elements ---")
        for el in listing.elements[:25]:
            print(f"  {el.role!r} title={el.title!r} "
                  f"pos={el.position} size={el.size} "
                  f"visible={el.visible} enabled={el.enabled}")
        print("--- search ---")
        for query in ("Submit", "Name", "Probe Window", "OK"):
            found = agent.find_element(title=query)
            print(f"  find_element(title={query!r}): "
                  f"{found.role if found else None} "
                  f"{found.position if found else None}")
            found = agent.find_element(title_contains=query)
            print(f"  find_element(title_contains={query!r}): "
                  f"{found.role if found else None} "
                  f"{found.position if found else None}")
        return 0
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
