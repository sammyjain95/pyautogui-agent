# Live test report: pyautogui-agent on a virtual Linux display

Date: 2026-11-27. Tester: Sam (the assistant), on this VM.
Method: Xvfb virtual display at 1920x1080, a tkinter test app
(`scripts/vm_live_test_app.py`: a "Name:" entry plus a green Submit
button that writes a result file when clicked), driven by
`scripts/vm_live_test.py` using the REAL package (no mocks).

## Environment caveats (read first)

- This VM has no physical display and no scrot or gnome-screenshot,
  so PyScreeze screenshots fail out of the box. The test used an `mss`
  screenshot shim (X11, patched onto `pyautogui.screenshot` and
  `pyscreeze.screenshot`). The package's own logic (observe, locate,
  click, waits, safety) was tested genuinely; only the screenshot
  backend was shimmed.
- No OpenCV installed, so all locate calls used the Pillow backend.
- No Tesseract binary (apt-get update took 6+ minutes just to
  download package lists, 273 MB in `partial/` and still going).
  The OCR live checks therefore could not run; the
  missing-dependency error path was verified instead, and the OCR
  matching logic was verified at unit level.
- Element listing is macOS-only, so on Linux `observe()` returns
  `elements_supported=False`. That is by design, not a failure.

## Results (7 of 9 live checks passed)

| Check | Result | Time | Notes |
|---|---|---|---|
| observe() | PASS | 0.09-0.11s | screen 1920x1080, mouse (960,540), screenshot (1920,1080), elements_supported=False |
| raw locateOnScreen (full button) | PASS | 0.23-0.24s | Pillow path, no OpenCV. Faster than the documented 1-2s. Found the button exactly. |
| wait_for_image (middle of button) | PASS | 0.20-0.21s | Smaller template also matched. |
| click_image (Submit) | PASS | 0.31-0.33s | Click landed, the app recorded it. |
| dry-run click_point | PASS | 0.00s | Logged, not executed, click count unchanged. |
| wait timeout (image not on screen) | PASS | 3.17s for a 3.0s timeout | ActionTimeoutError carried a saved last screenshot. |
| click_text('Submit') via OCR | NOT TESTABLE | - | Tesseract binary missing. ProviderNotInstalledError raised with a clear install message (correct behaviour). |
| fill_field('Name:', 'Hello') | NOT TESTABLE | - | Falls back to OCR on Linux, so same missing-binary error. |
| wait_for_condition (file) | PASS | 1.00s | Returned when the file appeared. (Second run showed 0.00s because the marker file persisted from run one; test artifact, not a package issue.) |

Whole 9-check run: about 8 seconds, most of it the 3-second timeout
test. The core loop (observe, locate, click) is about 0.6s.

## Unit-level OCR check (no binary needed)

`_find_text_match` on synthetic OCR words: finds "Submit" at center
(935, 485) with confidence 0.97, finds "Name:", returns None for an
absent "Cancel", and `_closest_word` gives "Submit" at 0.92 for the
typo "Submitt". The matching logic is sound; only the live OCR run
was blocked by the missing binary.

## Extra probe: confidence without OpenCV

Passing `confidence=0.9` to locate raises a raw
`NotImplementedError: The confidence keyword argument is only
available if OpenCV is installed.` The package passes `confidence`
through but does not handle this case. See improvement 1 below.

## Comparison with my own navigation

My browser navigation is DOM and accessibility based: I get
structured elements (roles, names, positions), I can wait for a
specific element, fill a form by selector, and read the page. That is
the equivalent of what this package's element listing is meant to
provide, and it is the reason my navigation is reliable.

On Linux, this package gives me none of that: `elements_supported`
is False, so an agent is still guessing pixels. The package as it
stands on Linux is a safer, better-organised PyAutoGUI (waits,
safety, observe, structured errors all work and are fast), but it is
not yet agent-grade in the way my browser navigation is. The thing
that would close the gap is structured element listing on Linux and
Windows, which is currently macOS-only and unverified.

Two things the package already does better than my browser setup:
the safety layer (dry-run, action log, confirmation hook) is a
library feature here, and the timeout errors carrying a screenshot
are genuinely useful for debugging a failed step.

## Where it needs improvement (ranked)

1. **Confidence without OpenCV raises a raw NotImplementedError.**
   Catch it and either fall back to exact matching with a warning or
   raise a clear package error telling the user to install
   opencv-python. This is the sharpest edge hit in testing.
2. **No structured elements on Linux or Windows.** The element list
   is the package's reason to exist, and it is macOS-only and
   unverified. AT-SPI (Linux) and UI Automation (Windows) providers
   are the highest-leverage next work. Without them, an agent on
   Linux is still guessing pixels.
3. **Locate is exact-match by default.** It was fast here (0.24s)
   because the template was an exact crop on a clean screen. On a
   real, busy desktop the Pillow path is 1-2s per call and brittle.
   Make OpenCV the documented recommended install, and search a
   region near the last known location first.
4. **`fill_field` clicks the label, not the field.** It clicks the
   centre of the label text and assumes the app focuses the field.
   Many apps do not. It should click to the right of the label (where
   the field usually sits) or find the nearest input-like region. The
   test app needed a label-click-to-focus binding for this to work.
5. **No vision interpretation.** The package hands the agent a
   screenshot but does not help it understand the screen. A
   `describe()` helper, or guidance to pair it with a vision model,
   would close the loop.
6. **Screenshot dependency on Linux is fragile.** On a bare Linux
   box, PyScreeze screenshots fail without scrot or gnome-screenshot,
   and this VM's apt took 6+ minutes just for package lists. A
   bundled X11 screenshot fallback (mss or python-xlib) would make
   Linux work out of the box. The test only ran because of an mss
   shim.
7. **`wait_for_image` does not validate the image path.** A
   nonexistent file raises a raw FileNotFoundError instead of a clear
   package error. Fail fast with a clear message.
8. **No post-action verification.** After a click, nothing checks
   the click had the intended effect. A `click_and_verify` helper
   would help agents recover from misclicks.

## Verdict

The package does what it promises on the parts that run here, and it
does them fast: observe, locate, click, waits, dry-run, and timeout
errors all work, and the core loop is about 0.6s. The gaps are the
ones the design already names: structured elements are macOS-only
and unverified, and on Linux the agent is still working from pixels.
Fix improvements 1, 2, and 4 first; they are the difference between
a nicer PyAutoGUI and a genuinely agent-grade desktop tool.

---

# v0.2.0 retest (2026-11-27): fixes 1, 2, and 4

Fixes 1 (confidence without OpenCV), 4 (fill_field clicks the
field), and 2 (AT-SPI Linux and UI Automation Windows providers)
are implemented. Version bumped to 0.2.0. Unit suite: 66 passed.

## Environment changes since the first run

- `scrot` 1.10 and `tesseract` 5.3.4 are now installed, so the live
  test uses the real PyScreeze screenshot path and runs the OCR
  checks for real. The driver (`scripts/vm_live_test.py`) prefers
  the real path when scrot exists and only installs the mss shim as
  a fallback, printing which path it used.
- PyScreeze 1.0.1 quirk found: it only recognises X11 from
  `XDG_SESSION_TYPE=x11`; under `xvfb-run` that variable is unset,
  so PyScreeze refused to use scrot even though scrot was
  installed ("install gnome-screenshot"). The driver now sets
  `XDG_SESSION_TYPE=x11` (via setdefault, so a real Wayland session
  is untouched) before importing pyautogui. This is a PyScreeze
  limitation, not a package bug; the package does not modify
  PyScreeze.

## Results (9 of 9 live checks passed, real scrot path)

Run: `xvfb-run -a -s "-screen 0 1920x1080x24" python3
scripts/vm_live_test.py`. Screenshot path: real PyScreeze (scrot).
Whole run: about 14 seconds (OCR is slower at 2x upscale, see
below).

| Check | Result | Time | Notes |
|---|---|---|---|
| observe() | PASS | 0.17s | screen 1920x1080, mouse (960,540), screenshot (1920,1080), elements_supported=False (no AT-SPI bus in plain xvfb-run; the AT-SPI probe below uses dbus-run-session) |
| raw locateOnScreen (full button) | PASS | 0.35s | Pillow path, no OpenCV. Box (888, 460, 143, 51). |
| wait_for_image (middle of button) | PASS | 0.35s | Smaller template also matched. |
| click_image (Submit) | PASS | 0.48s | Click landed, the app recorded it. |
| dry-run click_point | PASS | 0.00s | Logged, not executed, click count unchanged. |
| wait timeout (image not on screen) | PASS | 3.81s for a 3.0s timeout | ActionTimeoutError carried a saved last screenshot. |
| click_text('Submit') via OCR | PASS | 2.17s | OCR runs for real now. Clicked at (959, 483). |
| fill_field('Name:', 'Hello') | PASS | 2.68s | Clicked the field to the right of the label and typed; the app recorded `clicked entry='Hello'`. The label-click-to-focus binding was removed from the test app, so this genuinely verifies the new field-point click. |
| wait_for_condition (file) | PASS | 0.00s | Marker file persisted from the earlier run; test artifact, not a package issue. |

## OCR finding: psm 11 and a 2x upscale

The first v0.2.0 live run failed `fill_field('Name:', 'Hello')`:
OCR on the full screen did not find "Name:" at all (closest match
was "Status:" at 0.33). The label IS on screen and readable when
the region is cropped, so this was an OCR segmentation problem, not
a fill_field problem. Testing the saved screenshot directly:

- Default psm 3, 1x: finds "Status:", "clicked", "Submit"; misses
  "Name:" entirely.
- psm 11, 1x: finds "Name" (the colon is dropped).
- psm 3, 2x: still misses "Name:", and also loses "Submit".
- psm 11, 2x: finds "Name:" (with the colon), "Status:",
  "clicked", and "Submit", all at correct positions.

So `_ocr_words` now uses `--psm 11` (sparse text, for labels
scattered across a UI) on a 2x upscaled image, dividing the
returned coordinates back by 2. That is why the OCR checks take
about 2 seconds each now. A unit test pins the psm 11 config, the
2x image size, and the coordinate scaling.

## AT-SPI Linux provider: live probe and click test

Run under `dbus-run-session -- xvfb-run -a -s "-screen 0
1920x1080x24"` with a zenity dialog (`scripts/atspi_live_probe.py`).
The provider connects, walks the tree, and returns 14 elements:
1 desktop frame, 1 dialog, 1 push button ("OK"), 3 labels, 6
panels, 1 image, 1 separator. Roles, names, and sizes are correct,
and `find_element` finds "Probe Window" (dialog) and "OK" (button).
The tkinter test app does NOT appear in the tree (Tk has limited
accessibility support), as expected.

Position problem found and fixed: at first every element reported
position (0, 0). Diagnosis, confirmed by direct probes:
`getPosition(XY_SCREEN)` returns (0, 0) for every descendant of a
dialog (it appears to return the top-level window's position),
while `getPosition(XY_WINDOW)` returns the real position relative
to the top-level window (the OK button reported (14, 166)). The
provider now takes a top-level window's screen position from
XY_SCREEN and computes each descendant's screen position as the
top-level position plus its own XY_WINDOW offset. After the fix the
probe shows real positions: the OK button at (14, 166) with size
(528, 44) (bottom of the 538x210 dialog), the "AT-SPI probe
window" label at (86, 88), the dialog icon at (42, 88). A click
test (`scripts/atspi_click_test.py`) clicked the OK button's centre
(278, 188) from the provider's listing and zenity exited with code
0, proving the reported position is the button's real screen
position.

Two environment notes from the probe:
- The desktop frame reports size (1024, 768) while the X screen is
  1920x1080; that is the AT-SPI desktop frame's own reported size,
  not a provider bug. Positions are unaffected.
- A guard was needed: calling `pyatspi.Registry.getDesktop(0)`
  with no D-Bus session bus aborts the whole process with SIGTRAP
  (exit 133), which Python cannot catch. The provider checks for a
  bus address in the environment first and returns a clear
  unsupported listing when there is none, never calling getDesktop.
  Residual risk: if the address is set but points at a dead bus,
  libatspi may still abort; that means the session itself is broken.

## Status of the earlier improvement list

- 1 (confidence without OpenCV): FIXED. `wait_for_image` raises
  `ProviderNotInstalledError("OpenCV", ...)` with the install hint
  when confidence is passed without OpenCV, and converts a raw
  NotImplementedError from locate the same way.
- 2 (structured elements on Linux/Windows): PARTLY DONE. Linux
  AT-SPI is implemented and verified live (tree, roles, names,
  sizes, positions, and a real click). Windows UI Automation is
  implemented from the specification and marked UNVERIFIED
  (cannot be tested on this Linux VM). macOS provider unchanged
  and still unverified on a Mac.
- 4 (fill_field clicks the field): FIXED. Verified live: the test
  app's label-click binding was removed and `fill_field("Name:",
  "Hello")` still works, clicking right of the label.
- 3, 5, 6, 7, 8: unchanged, still open. Note 6 (screenshot
  dependency) is less sharp now that scrot is installed, but the
  PyScreeze XDG_SESSION_TYPE quirk above is a new instance of the
  same fragility.

## What remains unverified

- Windows UI Automation provider: implemented from the spec,
  marked UNVERIFIED in code and docs. Needs a Windows machine.
- macOS provider: unchanged from v0.1.0, still unverified on a Mac.
- AT-SPI on a real Linux desktop: verified here under Xvfb with a
  GTK dialog; on a real desktop with a window manager and a
  compositor, positions should be the same (the XY_WINDOW plus
  top-level offset computation does not depend on Xvfb), but that
  has not been run.
- The 2x OCR upscale cost: OCR checks take about 2 seconds each
  now, versus under a second before (when they could not run at
  all). Acceptable for an agent action, but worth knowing.
