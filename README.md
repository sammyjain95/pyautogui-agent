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
pip install "pyautogui-agent[dev]"     # running the tests (pytest)
```

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
| `elements.py` | `list_elements()`, `find_element()`, `find_all()`, `click_element()`. macOS Accessibility tree first; other platforms return an explicit "not supported yet" result. |
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

Verified on this Linux VM, no display, with mocks (see `tests/`):

- Imports, unit tests, and a dry-run end-to-end pass all pass here.
- Waits (including timeout with a saved screenshot), structured
  errors, dry-run mode, the action log, the confirmation hook, and
  the `observe()` structure are covered by tests.
- `click_text` raises the clear Tesseract install error when Tesseract
  is absent (verified: this VM has no Tesseract).
- `list_elements()` on Linux returns the explicit "not supported yet"
  result, never a silent empty list (verified).

NOT verified here, needs the owner's Mac:

- The macOS element listing (Accessibility API, Retina scaling) is
  implemented from the API specification and marked UNVERIFIED in the
  code. It has never run on a Mac.
- OCR clicking against a real screen has never run.
- Live `observe()` against a real screen has never run.

Verify on the Mac with `scripts/mac_live_test.py`. It prints the
element list, one `observe()` call, and a dry-run action, and it
never clicks anything real. Only after that run passes should V1 be
called done.

## Limits

- Coordinates are top-left origin, primary display only. That is a
  PyAutoGUI limit.
- Image matching is slow (1 to 2 seconds per locate call) and breaks
  on scaling or theme changes. Prefer the element list or OCR text.
- Element listing is macOS only in V1. Windows (UI Automation) and
  Linux (AT-SPI) are defined to plug in later.

## Relationship to upstream

Small, general improvements (wait primitives, richer errors, agent
docs) can be proposed to upstream PyAutoGUI as PRs later. The agent
layer itself stays in this package, under the owner's control, so it
can move fast without waiting on upstream. The design and the deep
dive behind this package are in `ANALYSIS.md`.
