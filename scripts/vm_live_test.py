"""Live end-to-end test of pyautogui-agent against a real virtual screen.

Runs the tkinter test app under Xvfb, then drives it with the REAL
pyautogui_agent package (no mocks): observe, locate, click, waits,
dry-run, OCR text click, and fill_field. Every step is timed and the
result is printed as a table.

Run: xvfb-run -a -s "-screen 0 1920x1080x24" python3 scripts/vm_live_test.py
Requires: scrot (PyScreeze screenshots on Linux), tesseract-ocr and
pytesseract for the OCR steps (those steps report a clear skip/error
when Tesseract is absent).

NOTE on screenshots: on a bare Linux box PyScreeze needs scrot or
gnome-screenshot. When scrot is present, the real PyScreeze path is
used. When neither is installed, this driver installs an ``mss``
screenshot shim (X11, no scrot needed) and patches both
``pyautogui.screenshot`` and ``pyscreeze.screenshot`` with it, so the
package's own logic (observe, locate, click, waits) is tested against
the real screen. The driver prints which path it used; the shim is a
test harness choice, not part of the package.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULT_DIR = "/tmp/pyautogui-agent-test"
RESULT_FILE = os.path.join(RESULT_DIR, "result.txt")
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "vm_live_test_app.py")

BUTTON_GREEN = (46, 125, 50)  # #2e7d32, the Submit button background


def result_lines():
    if not os.path.exists(RESULT_FILE):
        return []
    with open(RESULT_FILE) as f:
        return [line.strip() for line in f if line.strip()]


def find_green_box(image):
    """Bounding box of the green Submit button in a screenshot."""
    pixels = image.load()
    w, h = image.size
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = pixels[x, y][:3]
            if abs(r - BUTTON_GREEN[0]) < 12 and \
               abs(g - BUTTON_GREEN[1]) < 12 and \
               abs(b - BUTTON_GREEN[2]) < 12:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
    if max_x < 0:
        return None
    return (min_x, min_y, max_x + 1, max_y + 1)


def main():
    # PyScreeze 1.0.1 only recognises X11 from XDG_SESSION_TYPE=x11
    # (it does not fall back to DISPLAY), and under xvfb-run that
    # variable is unset, so PyScreeze would refuse to use scrot even
    # though scrot is installed. Xvfb IS X11, so set it before
    # importing pyautogui (PyScreeze reads it at import time).
    # setdefault leaves a real Wayland session untouched.
    os.environ.setdefault("XDG_SESSION_TYPE", "x11")
    import pyautogui_agent as agent
    from pyautogui_agent.safety import Session

    os.makedirs(RESULT_DIR, exist_ok=True)
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)

    app = subprocess.Popen([sys.executable, APP])
    results = []

    def record(name, ok, detail, seconds):
        results.append((name, ok, detail, seconds))
        print(f"[{'PASS' if ok else 'FAIL'}] {name} ({seconds:.2f}s) {detail}")

    try:
        time.sleep(2.5)  # let the window draw
        pg = agent._util.get_pyautogui()

        # Screenshot path: prefer the real PyScreeze backend (scrot)
        # when it exists; only fall back to the mss shim when it does
        # not. Print which path is in use so the results say so.
        import shutil
        if shutil.which("scrot") is not None:
            print("screenshot: real PyScreeze path (scrot found)")
        else:
            try:
                import pyscreeze
                import mss as mss_lib
                from PIL import Image as _Image

                def _mss_shot(imageFilename=None, region=None):
                    with mss_lib.MSS() as sct:
                        mon = sct.monitors[1]
                        if region is not None:
                            mon = {"left": region[0], "top": region[1],
                                   "width": region[2],
                                   "height": region[3]}
                        grab = sct.grab(mon)
                        img = _Image.frombytes("RGB", grab.size, grab.bgra,
                                               "raw", "BGRX")
                        if imageFilename is not None:
                            img.save(imageFilename)
                        return img

                pyscreeze.screenshot = _mss_shot
                pg.screenshot = _mss_shot
                print("screenshot: mss shim installed (no scrot on this VM)")
            except Exception as exc:
                print(f"screenshot: mss shim NOT installed ({exc!r}); "
                      "using PyScreeze default")

        # T1: observe()
        t0 = time.monotonic()
        obs = agent.observe()
        t1 = time.monotonic() - t0
        record("observe()", obs.screen_size == (1920, 1080)
               and obs.screenshot is not None,
               f"screen={obs.screen_size} mouse={obs.mouse_position} "
               f"shot={obs.screenshot.size if obs.screenshot else None} "
               f"elements_supported={obs.elements.supported if obs.elements else None}",
               t1)

        # Build reference images from the live screenshot (green button).
        shot = pg.screenshot()
        box = find_green_box(shot)
        if box is None:
            print("FAIL: could not find the green button in the screenshot")
            return 1
        ref = shot.crop((box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2))
        ref_path = os.path.join(RESULT_DIR, "button.png")
        ref.save(ref_path)
        # A harder, smaller template: the middle of the button.
        bw, bh = box[2] - box[0], box[3] - box[1]
        sub = shot.crop((box[0] + bw // 4, box[1] + bh // 4,
                         box[2] - bw // 4, box[3] - bh // 4))
        sub_path = os.path.join(RESULT_DIR, "button_middle.png")
        sub.save(sub_path)

        # T2: single locate timing (raw pyautogui, for comparison).
        t0 = time.monotonic()
        found = pg.locateOnScreen(ref_path)
        t1 = time.monotonic() - t0
        record("raw locateOnScreen (full button)", found is not None,
               f"box={found} (expected near {box})", t1)

        # T3: wait_for_image with the smaller template.
        t0 = time.monotonic()
        try:
            found = agent.wait_for_image(sub_path, timeout=10.0)
            t1 = time.monotonic() - t0
            record("wait_for_image (middle of button)", found is not None,
                   f"box={found}", t1)
        except Exception as exc:
            record("wait_for_image (middle of button)", False, repr(exc),
                   time.monotonic() - t0)

        # T4: click_image on the real button, verify the app saw it.
        before = len(result_lines())
        t0 = time.monotonic()
        try:
            at = agent.click_image(ref_path, timeout=10.0)
            t1 = time.monotonic() - t0
            time.sleep(0.5)
            after = result_lines()
            record("click_image (Submit)", len(after) == before + 1,
                   f"clicked at {at}, result lines={len(after)}", t1)
        except Exception as exc:
            record("click_image (Submit)", False, repr(exc),
                   time.monotonic() - t0)

        # T5: dry-run must log and NOT click.
        before = len(result_lines())
        dry = Session(dry_run=True)
        t0 = time.monotonic()
        agent.click_point(960, 540, session=dry)
        t1 = time.monotonic() - t0
        time.sleep(0.3)
        log = dry.log
        record("dry-run click_point", len(result_lines()) == before
               and len(log) == 1 and log[0].action == "click_point",
               f"lines stayed {before}, log={[(e.action, e.result) for e in log]}",
               t1)

        # T6: wait timeout must raise with a screenshot. Use a real image
        # file that is NOT on screen (a magenta square), so the timeout
        # path is exercised rather than a missing-file error.
        from PIL import Image as _PILImage
        missing = os.path.join(RESULT_DIR, "not_on_screen.png")
        _PILImage.new("RGB", (50, 50), (255, 0, 255)).save(missing)
        t0 = time.monotonic()
        try:
            agent.wait_for_image(missing, timeout=3.0, interval=0.5)
            record("wait timeout (image not on screen)", False,
                   "no exception raised", time.monotonic() - t0)
        except agent.ActionTimeoutError as exc:
            t1 = time.monotonic() - t0
            shot_ok = exc.last_screenshot and os.path.exists(
                exc.last_screenshot)
            record("wait timeout (image not on screen)", shot_ok,
                   f"elapsed={t1:.2f}s (timeout 3.0s) "
                   f"last_screenshot={'saved' if shot_ok else 'missing'}",
                   t1)
        except Exception as exc:
            record("wait timeout (image not on screen)", False, repr(exc),
                   time.monotonic() - t0)

        # T7: OCR click_text on the Submit label.
        before = len(result_lines())
        t0 = time.monotonic()
        try:
            at = agent.click_text("Submit", timeout=15.0)
            t1 = time.monotonic() - t0
            time.sleep(0.5)
            record("click_text('Submit') via OCR",
                   len(result_lines()) == before + 1,
                   f"clicked at {at}, result lines={len(result_lines())}",
                   t1)
        except agent.ProviderNotInstalledError as exc:
            record("click_text('Submit') via OCR", False,
                   f"Tesseract not installed: {exc}", time.monotonic() - t0)
        except Exception as exc:
            record("click_text('Submit') via OCR", False, repr(exc),
                   time.monotonic() - t0)

        # T8: fill_field by label, then submit, verify the typed value.
        t0 = time.monotonic()
        try:
            agent.fill_field("Name:", "Hello", timeout=15.0)
            agent.click_image(ref_path, timeout=10.0)
            time.sleep(0.5)
            lines = result_lines()
            t1 = time.monotonic() - t0
            record("fill_field('Name:', 'Hello')",
                   any("entry='Hello'" in line for line in lines),
                   f"last lines={lines[-2:]}", t1)
        except Exception as exc:
            record("fill_field('Name:', 'Hello')", False, repr(exc),
                   time.monotonic() - t0)

        # T9: wait_for_condition on a file appearing.
        t0 = time.monotonic()
        marker = os.path.join(RESULT_DIR, "marker.txt")

        def _make_marker():
            time.sleep(1.0)
            with open(marker, "w") as f:
                f.write("here\n")

        import threading
        threading.Thread(target=_make_marker, daemon=True).start()
        try:
            value = agent.wait_for_condition(
                lambda: os.path.exists(marker), timeout=5.0,
                description="marker file to appear")
            t1 = time.monotonic() - t0
            record("wait_for_condition (file)", bool(value),
                   f"returned after {t1:.2f}s", t1)
        except Exception as exc:
            record("wait_for_condition (file)", False, repr(exc),
                   time.monotonic() - t0)

    finally:
        app.terminate()
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()

    passed = sum(1 for _, ok, _, _ in results if ok)
    print(f"\n{passed}/{len(results)} live checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
