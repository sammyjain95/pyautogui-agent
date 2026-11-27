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
