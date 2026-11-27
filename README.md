# pyautogui-agent

An agent-friendly companion layer on top of PyAutoGUI. PyAutoGUI only
understands pixels; this package adds what an agent needs to drive a
desktop: a structured element list, one-call observation, waits with
deadlines, task-level actions, structured errors that carry
screenshots, and a safety layer (dry-run mode, action log,
confirmation hook).

It never modifies PyAutoGUI or PyScreeze. It only calls them. It is
additive and backwards compatible by construction, and it lives in
its own repository so it can be published under its own name.

## Install

```bash
pip install pyautogui-agent
```

Optional extras:

```bash
pip install "pyautogui-agent[ocr]"    # OCR text clicking (pytesseract)
pip install "pyautogui-agent[macos]"   # macOS element listing (pyobjc)
pip install "pyautogui-agent[windows]" # Windows element listing (comtypes)
pip install "pyautogui-agent[dev]"     # running the tests (pytest)
```

Linux element listing needs pyatspi, which is not on PyPI:
`sudo apt install python3-pyatspi at-spi2-core`. It also needs a
D-Bus session bus (a logged-in GUI session, or `dbus-run-session`
under Xvfb).

OCR also needs the Tesseract binary itself: `brew install tesseract`
on macOS, `sudo apt install tesseract-ocr` on Ubuntu/Debian. Without
it, `click_text` raises `ProviderNotInstalledError` with install
instructions instead of failing silently.

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
`Session(dry_run=False)`, and add a confirmation hook for anything
destructive.

## What is in the package

| Module | What it does |
| --- | --- |
| `elements.py` | `list_elements()`, `find_element()`, `find_all()`, `click_element()`. Dispatches by platform: macOS Accessibility, Linux AT-SPI, Windows UI Automation. Each returns the same `ElementListing` shape; a missing provider dependency returns an explicit "not supported" result. |
| `elements_linux.py` | Linux AT-SPI provider (pyatspi). Verified live under Xvfb. |
| `elements_windows.py` | Windows UI Automation provider (comtypes). Implemented from spec, UNVERIFIED. |
| `observe.py` | `observe()`: one call returning screenshot, screen size, mouse position, and the element list. |
| `wait.py` | `wait_for_image()`, `wait_for_condition()`: poll with a deadline; the timeout error carries the last screenshot path. |
| `actions.py` | `click_text()` (OCR), `fill_field()`, `click_image()`, `click_point()`. Task-level actions, all through the safety layer. |
| `errors.py` | Structured errors: `ElementNotFoundError`, `ActionTimeoutError`, `ProviderNotInstalledError`, `NotSupportedError`, `ActionDeclinedError`, `DisplayUnavailableError`. All derive from `AgentError`. |
| `safety.py` | `Session`: dry-run mode, action log, confirmation hook. |
| `llms.txt`, `SKILL.md` | Machine-readable API spec, shipped in the package. |

## Safety

- Always pass a `Session`. Test every new task with
  `Session(dry_run=True)` first; dry-run logs the action and does not
  execute it.
- Put a confirmation hook on destructive actions:
  `Session(confirm_hook=..., confirm_predicate=...)`. A declined
  action raises `ActionDeclinedError` and is not executed.
- Never turn off PyAutoGUI's fail-safe in a script that moves the
  mouse on its own. Moving the mouse to the upper-left corner is the
  emergency stop.
- This package needs a logged-in GUI session with a display. It
  cannot run headless. Importing it is safe headless (PyAutoGUI is
  imported lazily); only actions that need the screen raise
  `DisplayUnavailableError`.

## Verification status (honest)

Verified live on this Linux VM under Xvfb (see `TESTING.md` for the
full report):

- 66 unit tests pass, including provider dispatch, a fake AT-SPI
  tree, the Windows import guard, the confidence rule, the
  fill_field field-point computation, and the OCR psm 11 plus 2x
  upscale.
- 9 of 9 live checks pass with the real scrot screenshot path:
  observe, locate, wait_for_image, click_image, dry-run, wait
  timeout with a saved screenshot, OCR click_text, fill_field
  ("Name:", "Hello" typed into the field to the right of the
  label), and wait_for_condition.
- Linux AT-SPI element listing is verified live with a GTK dialog:
  tree, roles, names, sizes, and positions are correct, and a click
  on the listed OK button dismissed the dialog.
  `fill_field` clicks the field to the right of the label (30px gap
  by default), falling back to below the label when there is no room
  to the right. The accessibility path (macOS) clicks the real
  field element.
- Passing `confidence` to `wait_for_image` without OpenCV raises
  `ProviderNotInstalledError("OpenCV", ...)` with the install hint,
  instead of a raw NotImplementedError.

NOT verified here, needs the owner's Mac or a Windows machine:

- The macOS element listing (Accessibility API, Retina scaling) is
  implemented from the API specification and marked UNVERIFIED in
  the code. It has never run on a Mac.
- The Windows UI Automation provider is implemented from the API
  specification and marked UNVERIFIED in the code. It has never run
  on Windows.

Verify macOS with `scripts/mac_live_test.py`. It prints the
element list, one `observe()` call, and a dry-run action, and it
never clicks anything real. Only after that run passes should V1 be
called done.

## Limits

- Coordinates are top-left origin, primary display only. That is a
  PyAutoGUI limit.
- Image matching is slow (1 to 2 seconds per locate call) and breaks
  on scaling or theme changes. Prefer the element list or OCR text.
  Without OpenCV, `confidence` is not available; install
  `opencv-python` for fuzzy matching.
- OCR text clicking upscales the screenshot 2x and uses Tesseract
  psm 11, so each OCR pass takes about 2 seconds on a 1920x1080
  screen.
- Element listing has three providers: macOS (Accessibility),
  Linux (AT-SPI, verified live), Windows (UI Automation,
  unverified). The macOS provider lists the focused application
  only; Linux lists the whole desktop.

## Relationship to upstream

Small, general improvements (wait primitives, richer errors, agent
docs) can be proposed to upstream PyAutoGUI as PRs later. The agent
layer itself stays in this package, under the owner's control, so it
can move fast without waiting on upstream. The design and the deep
dive behind this package are in `ANALYSIS.md`.
