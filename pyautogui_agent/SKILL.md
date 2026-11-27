# pyautogui-agent

Drive a desktop GUI as an agent, on top of PyAutoGUI, with structured
screen elements, one-call observation, waits, task-level actions, and
a safety layer. PyAutoGUI only understands pixels; this package adds
what an agent needs to decide its next move and to act safely.

## When to use

Use this package when an agent needs to operate a desktop GUI: click
a button, fill a form, wait for a window, or check what is on screen.
Use it instead of raw PyAutoGUI calls, because the task-level actions
(click by text, fill by label) and the structured errors (with
screenshots) are what make agent-driven GUI use workable.

Do NOT use it when the task can be done without a GUI: files, CLIs,
and APIs are always more reliable than driving pixels. Do NOT use it
headless: it needs a logged-in GUI session with a display. Do NOT use
it with no safety session: always pass a Session, and use dry-run
mode while testing a new task.

## Install

- Base: `pip install pyautogui-agent` (needs PyAutoGUI and Pillow).
- OCR text clicking: `pip install "pyautogui-agent[ocr]"` plus the
  Tesseract binary (`brew install tesseract` on macOS,
  `sudo apt install tesseract-ocr` on Ubuntu/Debian).
- macOS element listing: `pip install "pyautogui-agent[macos]"`.
- Windows element listing: `pip install "pyautogui-agent[windows]"`.
- Linux element listing: `sudo apt install python3-pyatspi
  at-spi2-core` (pyatspi is not on PyPI, so there is no pip extra).
  Needs a D-Bus session bus (a logged-in GUI session, or
  `dbus-run-session` under Xvfb).

## Core workflow

1. Observe first. Call `observe()` and read the screen size, the
   mouse position, and the element list. `list_elements()` works on
   macOS (Accessibility, focused application only), Linux (AT-SPI,
   whole desktop), and Windows (UI Automation). On a platform with
   no provider, or when the provider's dependency is missing, the
   listing reports `supported=False` with a clear message; an empty
   list there means "no provider", not "no elements".
2. Act by name, not by coordinates. Prefer `click_text("Submit")`,
   `fill_field("Email", "x@y.com")`, `click_image("ok.png")`, or
   `click_element(element)`. Use `click_point(x, y)` only when the
   target cannot be named.
3. Wait instead of sleeping. Use `wait_for_image(...)` or
   `wait_for_condition(...)` with a timeout. Never poll
   `locateOnScreen` in a loop.
4. Read the error, then look at the screenshot. On failure,
   `ElementNotFoundError` and `ActionTimeoutError` carry
   `screenshot_path`. Open that image before retrying; it shows what
   the screen actually looked like.

## Safety rules (do not skip these)

- Always pass a `Session`. The default session exists, but an
  explicit session makes the action log reviewable.
- Test every new task with `Session(dry_run=True)` first. Dry-run
  logs the action and does not execute it. Check the log, then run
  for real.
- Put a confirmation hook on destructive actions. Supply
  `confirm_hook` (a callable returning True to allow, False to
  decline) and `confirm_predicate` (which actions need confirmation).
  A declined action raises `ActionDeclinedError` and is not executed.
- Never turn off PyAutoGUI's fail-safe (`FAILSAFE`) in a script that
  moves the mouse on its own. Moving the mouse to the upper-left
  corner is the emergency stop.

## API

- `observe(include_elements=True, take_screenshot=True, scale=None)`
  returns an `Observation`: `screenshot`, `screen_size`,
  `mouse_position`, `elements`, `timestamp`.
- `list_elements(max_depth=12, max_elements=500, scale=None)`
  returns an `ElementListing`: `elements`, `supported`, `platform`,
  `message`, `scale`, `app_name`. Three providers (macOS, Linux
  AT-SPI, Windows UI Automation), one shape.
- `find_element(role=None, title=None, title_contains=None,
  description=None, ...)` returns the first match or None.
  `find_all(...)` returns all matches.
- `click_element(element, session=None)`.
- `wait_for_image(image, timeout=10.0, interval=0.5, confidence=None,
  region=None, screenshot_dir=None)` returns the box. Confidence
  rule: passing `confidence` without OpenCV installed raises
  `ProviderNotInstalledError("OpenCV", ...)`; without OpenCV only
  exact matching is available.
- `wait_for_condition(fn, timeout=10.0, interval=0.5,
  description="condition", screenshot_dir=None)` returns fn()'s
  truthy value.
- `click_text(text, timeout=10.0, interval=1.0, session=None,
  language="eng", screenshot_dir=None)` returns the (x, y) center.
  OCR uses Tesseract psm 11 (sparse text) on a 2x upscaled image,
  so small labels are found; each OCR pass takes about 2 seconds on
  a 1920x1080 screen.
- `fill_field(text, value, session=None, timeout=10.0, interval=0.05,
  field_gap=30)`. The accessibility path (macOS) clicks the real
  field element. The OCR path finds the label's box and clicks the
  FIELD: the point to the right of the label on the same row,
  `(label_right + field_gap, label_center_y)`, defaulting to 30px;
  when the label spans nearly the full screen width, it clicks
  below the label instead, `(label_center_x, label_bottom +
  field_gap)`. It does NOT click the label itself.
- `click_image(image, session=None, timeout=10.0, interval=0.5,
  confidence=None, region=None)` returns the (x, y) center.
- `click_point(x, y, button="left", session=None)`.
- `Session(dry_run=False, confirm_hook=None, confirm_predicate=None)`,
  `Session.execute(action, args, fn)`, `Session.dry_run_mode()`,
  `dry_run()`, `get_default_session()`, `set_default_session(session)`.
- Errors, all under `AgentError`: `ElementNotFoundError`,
  `ActionTimeoutError`, `ProviderNotInstalledError`,
  `NotSupportedError`, `ActionDeclinedError`,
  `DisplayUnavailableError`.

## Worked example

```python
from pyautogui_agent import (
    Session, click_text, fill_field, observe, wait_for_image,
)

session = Session(dry_run=True)  # dry run first, check the log
obs = observe()
print(obs.screen_size, obs.mouse_position)

click_text("Search", session=session)
fill_field("Search", "pyautogui", session=session)
wait_for_image("results.png", timeout=10.0)

print("\n".join(session.format_log()))
```

When the log looks right, run the same code with
`Session(dry_run=False)` (and a confirmation hook for anything
destructive).

## Limits and verification status

- Coordinates are top-left origin, primary display only. That is a
  PyAutoGUI limit, not this package's.
- Image matching is slow (1 to 2 seconds per locate call) and breaks
  on scaling or theme changes. Prefer the element list or OCR text.
  Without OpenCV, `confidence` is not available (see the confidence
  rule above); install `opencv-python` for fuzzy matching.
- Linux AT-SPI element listing is verified live under Xvfb with a
  GTK dialog, and OCR clicking plus `fill_field` are verified live
  on this VM (9 of 9 live checks pass). See TESTING.md.
- macOS element listing and Windows UI Automation are implemented
  from API specifications and are UNVERIFIED. Verify macOS with
  `scripts/mac_live_test.py` on the owner's Mac before relying on
  it. Waits, errors, safety, dry-run, the action log, and the
  observe() structure are unit tested with mocks and need no display.
