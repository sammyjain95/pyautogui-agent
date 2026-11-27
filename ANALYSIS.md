# PyAutoGUI deep dive: what it is, where agents struggle, and the companion package design

Date: 2026-11-27. Sources read: `pyautogui/__init__.py` (2,171 lines),
`pyautogui/_pyautogui_osx.py` (448 lines), `pyscreeze/__init__.py`
(789 lines), the PyAutoGUI quickstart, and the upstream repo page
(github.com/asweigart/pyautogui: public, BSD 3-Clause, master branch,
12,771 stars, 1,442 forks).

## 1. What PyAutoGUI actually is

A thin, cross-platform wrapper over three different OS input systems,
plus two helper libraries it depends on.

- **Input (mouse and keyboard):** `pyautogui/__init__.py` holds the
  public API and dispatches to a platform module. On macOS that module
  is `_pyautogui_osx.py`, which uses AppKit/pyobjc and Quartz Core
  Graphics events to synthesize mouse and keyboard input. On Linux it
  uses Xlib, on Windows the Win32 API through `ctypes`. The public
  functions are all low-level verbs: `moveTo`, `moveRel`, `dragTo`,
  `dragRel`, `click`, `leftClick`, `rightClick`, `middleClick`,
  `doubleClick`, `tripleClick`, `scroll`, `hscroll`, `vscroll`,
  `mouseDown`, `mouseUp`, `typewrite`, `press`, `hotkey`, `keyDown`,
  `keyUp`, `hold`, `position`, `size`, `onScreen`.
- **Screenshots and image search:** these do not live in PyAutoGUI
  itself. They live in **PyScreeze** (`pyscreeze/__init__.py`), which
  PyAutoGUI re-exports. `screenshot`, `locateOnScreen`,
  `locateAllOnScreen`, `locateCenterOnScreen`, `locateOnScreenNear`,
  `locateOnWindow`, `pixel`, `pixelMatchesColor`, `center`. Two locate
  backends exist: OpenCV (`_locateAll_opencv`, confidence 0.999 by
  default) and Pillow (`_locateAll_pillow`, exact match, Knuth-Morris-
  Pratt search over pixel data, which is why it is slow).
- **Message boxes:** these live in **PyMsgBox** (`alert`, `confirm`,
  `prompt`, `password`).
- **Tweening:** mouse movement easing lives in **PyTweening**.
- **Safety:** `FAILSAFE = True` by default (mouse to a corner raises
  `FailSafeException`), `PAUSE = 0.1` seconds after every call,
  `MINIMUM_DURATION = 0.1`, `MINIMUM_SLEEP = 0.05`. A decorator
  (`_genericPyAutoGUIChecks`) enforces the fail-safe and the pause on
  every public call. There is already an `ImageNotFoundException` and a
  `useImageNotFoundException()` toggle to raise it instead of returning
  `None`, and a `run(commandStr)` mini command language for scripted
  command lists.
- **Limits stated in the README itself:** it only works reliably on the
  primary monitor, not on second monitors. Coordinates are top-left
  origin, pixels, primary display only.

So the library is a human-scripting tool: the human knows what is on
screen, writes coordinates or a reference image, and the library
replays the motions. Nothing in it understands the screen.

## 2. Where agents struggle with it

Each gap is tied to a concrete fact in the source above.

1. **No structured view of the screen.** The agent gets pixels. To
   click a button it must either guess coordinates or supply a reference
   image for template matching. There is no way to ask "what buttons
   exist, what are they called, and where are they". The macOS backend
   synthesizes Quartz events and never touches the Accessibility API,
   so this capability does not exist anywhere in the stack. This is the
   biggest gap.
2. **Locating is slow and brittle.** The Pillow backend is an exact
   pixel search (KMP), one to two seconds per call, and it breaks on
   scaling, theme, or layout changes. The OpenCV backend has a
   confidence parameter, but it needs OpenCV installed and the
   quickstart never mentions it. There is no region-limited search by
   default, no caching, and no multi-scale matching.
3. **No waiting.** There is no `wait_for_image` or `wait_for_condition`.
   `locateOnScreen` has a `minSearchTime` parameter, which is polling
   with a different name, but no agent-facing wait primitive with a
   timeout exists. Agents sleep blindly or poll locate in a loop.
4. **No task-level actions.** Everything is a low-level verb. Agents
   think in tasks ("click Submit", "fill in Email"), and every task
   currently has to be decomposed by hand into moves, clicks, and keys.
   There is no OCR-based text clicking anywhere in the stack.
5. **Failures carry no information.** `locateOnScreen` returns `None`
   with no reason. Was the image wrong, the region wrong, the scale
   wrong? The agent cannot tell, so it cannot self-correct. The
   `ImageNotFoundException` toggle exists but carries no context either.
6. **No observation primitive.** An agent needs one call that returns
   the screenshot plus the screen state. Today it must call `screenshot`,
   `size`, `position`, and (if it had one) an element list separately
   and assemble them itself.
7. **No safety layer for autonomous use.** The fail-safe is a human
   emergency stop. There is no dry-run mode, no action log, and no
   confirmation hook, which is what an agent driving the desktop
   unsupervised actually needs.
8. **No agent-readable documentation.** The docs are written for humans
   reading a web page. There is no machine-readable API spec, so an
   agent has to guess signatures and semantics.

## 3. The companion package: design

Name (working): `pyautogui-agent`, importable as `pyautogui_agent`.
It sits **on top of** PyAutoGUI and PyScreeze and never modifies them.
It is additive and backwards compatible by construction. It lives in
its own repository so it can be published under its own name.

### 3.1 Modules

- `elements.py` — `list_elements()`, `find_element()`,
  `click_element()`. macOS first, via the Accessibility API
  (`ApplicationServices.AXUIElement`, pyobjc). Returns a list of
  `Element` records: role, title, description, position, size,
  center, enabled. Traversal is depth- and count-limited so a large
  window cannot produce a huge tree. Attribute access failures are
  skipped, not fatal. Other platforms return an explicit
  "not supported yet" result, not a silent empty list. Retina note:
  Accessibility positions are in points, PyAutoGUI coordinates are in
  pixels, so positions are scaled by the display backing scale factor
  (detected via `NSScreen.mainScreen().backingScaleFactor()`), with an
  explicit override. This path is implemented from the API spec and
  needs live verification on a Mac; it is marked as such in the code.
- `observe.py` — `observe()`. One call returning an `Observation`:
  screenshot (Pillow image), screen size, mouse position, and the
  element list when available. This is the agent observation primitive.
- `wait.py` — `wait_for_image(image, timeout, interval)`,
  `wait_for_condition(fn, timeout, interval)`. Polls with a deadline
  and raises `ActionTimeoutError` carrying the last screenshot path
  and the time waited, so the caller can see what the screen looked
  like when it gave up.
- `actions.py` — task-level actions. `click_text(text)` via OCR
  (optional dependency: Tesseract; if it is not installed the function
  raises a clear error saying how to install it). `fill_field(text,
  value)` (click the element or text, then type). `click_element()`
  from `elements.py`. All of them go through the safety layer.
- `errors.py` — structured exceptions. `AgentError` base.
  `ElementNotFoundError` carries the query, the screenshot path, and
  the closest match with its confidence when one exists.
  `ActionTimeoutError` carries the timeout and the last screenshot.
  `ProviderNotInstalledError` for optional dependencies.
- `safety.py` — `Session` config plus a dry-run mode (context manager
  and flag: log the action, do not execute it), an action log (every
  action recorded with timestamp, action, arguments, and result), and
  a confirmation hook (a callable the owner supplies, invoked before
  actions matching a predicate, for example destructive ones).
- `llms.txt` and `SKILL.md` — a machine-readable API spec shipped in
  the package, so an agent can use it correctly without guessing.

### 3.2 What is deliberately out of scope for V1

- No changes to PyAutoGUI or PyScreeze themselves.
- No Windows or Linux element listing in V1 (macOS first; the
  interfaces are defined so the other platforms plug in later).
- No always-on screen watching. `observe()` is called explicitly.
- No cloud service, no account, no network calls except the ones the
  owner already makes through their own agent.

### 3.3 Verification status (honest)

- Pure logic (waits, errors, safety, dry-run, action log) is unit
  tested here with mocks, no screen needed.
- Anything that touches a real screen (element listing, OCR clicking,
  live `observe()`) cannot be verified on this Linux VM. It is
  implemented from the API specifications and marked unverified in the
  code and docs. A live test script (`scripts/mac_live_test.py`) is
  included for the owner's Mac, and it prints what it finds so the
  result can be checked by eye.

## 4. How it would be built (process)

1. Scaffold the package (`pyproject.toml`, package layout, tests,
   docs) and implement the pure-logic modules first (errors, safety,
   wait), with unit tests.
2. Implement `observe()` and the macOS element listing, with the
   Retina scaling and the graceful fallbacks.
3. Implement task actions, with OCR as an optional dependency.
4. Ship the agent-readable spec (`llms.txt`, `SKILL.md`) and a README
   with a worked example.
5. Verify here: imports, unit tests, and a dry-run end-to-end pass.
6. Verify on the owner's Mac with `scripts/mac_live_test.py`, and fix
   what it finds. Only then call V1 done.

## 5. Relationship to upstream

Small, general improvements (wait primitives, richer errors, agent
docs) can be proposed to upstream PyAutoGUI as PRs later. The agent
layer itself stays in this package, under the owner's control, so it
can move fast without waiting on upstream. If a change to PyScreeze
itself is ever needed (for example locate speed), that is a separate
fork and PR, not part of this package.
