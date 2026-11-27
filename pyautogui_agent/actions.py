"""Task-level actions: what an agent means, not the raw mouse verbs.

- ``click_text(text)``: find text on screen with OCR and click it.
- ``fill_field(text, value)``: click a field by its label, then type.
- ``click_image(image)``: wait for an image, then click its center.
- ``click_point(x, y)``: click a point, through the safety layer.

Every action goes through a safety Session (dry-run, action log,
confirmation hook). OCR is an optional dependency: Tesseract is never
required to import this package, and ``click_text`` fails with a clear
install message when it is absent.
"""

from __future__ import annotations

import difflib
import shutil
import time

from .elements import click_element, find_element
from .errors import (
    ElementNotFoundError,
    NotSupportedError,
    ProviderNotInstalledError,
)
from .safety import get_default_session
from .wait import wait_for_image
from ._util import get_pyautogui, save_screenshot

_OCR_INSTALL_HINT = (
    "Install the Python wrapper with: pip install pytesseract "
    "and install the Tesseract binary itself "
    "(macOS: brew install tesseract; "
    "Ubuntu/Debian: sudo apt install tesseract-ocr)."
)


def _get_ocr():
    """Return the pytesseract module, or raise a clear install error."""
    try:
        import pytesseract
    except ImportError as exc:
        raise ProviderNotInstalledError(
            "pytesseract / Tesseract", _OCR_INSTALL_HINT) from exc
    if shutil.which("tesseract") is None:
        raise ProviderNotInstalledError(
            "Tesseract binary",
            "pytesseract is installed but the tesseract binary was not "
            "found on PATH. " + _OCR_INSTALL_HINT)
    return pytesseract


def _ocr_words(ocr, image, language):
    """Run OCR and return a list of word dicts with boxes and confidence.

    Words with no text or a negative confidence (pytesseract marks
    non-word entries with -1) are dropped. Two choices matter for
    UI text and were found by live testing (see TESTING.md):

    - ``--psm 11`` (sparse text): the default page segmentation
      (psm 3) missed small labels such as a 16pt "Name:" next to an
      entry field, while psm 11, which looks for scattered text,
      found it.
    - a 2x upscale before OCR: at 1x, psm 11 read the label as
      "Name" (the colon was dropped); at 2x it read "Name:".
      Coordinates from the upscaled image are divided back by the
      scale so boxes are in screen pixels.
    """
    from PIL import Image as _Image

    scale = 2
    big = image.resize((image.width * scale, image.height * scale),
                       _Image.LANCZOS)
    data = ocr.image_to_data(big, lang=language, config="--psm 11",
                             output_type=ocr.Output.DICT)
    words = []
    count = len(data.get("text", []))
    for i in range(count):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not text or conf < 0:
            continue
        words.append({
            "text": text,
            "left": int(data["left"][i]) // scale,
            "top": int(data["top"][i]) // scale,
            "width": int(data["width"][i]) // scale,
            "height": int(data["height"][i]) // scale,
            "conf": conf,
        })
    return words


def _find_text_match(words, phrase):
    """Find a phrase across OCR words, in reading order.

    Returns a dict with center, box, and confidence (0.0 to 1.0), or
    None when the phrase is not on screen. Multi-word phrases are
    matched across consecutive words; the box is the union of the
    words involved.
    """
    if not words:
        return None
    full_parts = []
    spans = []
    offset = 0
    for i, word in enumerate(words):
        if full_parts:
            offset += 1
        start = offset
        offset += len(word["text"])
        spans.append((start, offset, i))
        full_parts.append(word["text"])
    full = " ".join(full_parts)
    at = full.lower().find(phrase.lower())
    if at < 0:
        return None
    end = at + len(phrase)
    involved = [words[i] for (start, stop, i) in spans
                if start < end and stop > at]
    if not involved:
        return None
    left = min(w["left"] for w in involved)
    top = min(w["top"] for w in involved)
    right = max(w["left"] + w["width"] for w in involved)
    bottom = max(w["top"] + w["height"] for w in involved)
    mean_conf = sum(w["conf"] for w in involved) / len(involved) / 100.0
    return {
        "center": ((left + right) / 2.0, (top + bottom) / 2.0),
        "box": (left, top, right - left, bottom - top),
        "confidence": mean_conf,
    }


def _closest_word(words, phrase):
    """Return (word, ratio) for the OCR word closest to the phrase."""
    best_word = None
    best_ratio = 0.0
    for word in words:
        ratio = difflib.SequenceMatcher(
            None, phrase.lower(), word["text"].lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_word = word["text"]
    if best_word is None:
        return None, None
    return best_word, best_ratio


def _find_text(text, timeout=10.0, interval=1.0, language="eng",
               screenshot_dir=None):
    """Find text on screen with OCR and return its match dict.

    Retries with fresh screenshots until the timeout expires. Returns
    a dict with center (x, y), box (left, top, width, height), and
    confidence (0.0 to 1.0). Raises ElementNotFoundError carrying the
    last screenshot path and the closest OCR word when the text never
    appears, and ProviderNotInstalledError when Tesseract is absent.
    Shared by click_text and fill_field so both see the same match.
    """
    pg = get_pyautogui()
    ocr = _get_ocr()
    deadline = time.monotonic() + timeout
    last_image = None
    closest = (None, None)
    while True:
        image = pg.screenshot()
        last_image = image
        words = _ocr_words(ocr, image, language)
        match = _find_text_match(words, text)
        if match is not None:
            return match
        closest = _closest_word(words, text)
        if time.monotonic() >= deadline:
            path = None
            if last_image is not None:
                try:
                    path = save_screenshot(last_image,
                                           directory=screenshot_dir)
                except Exception:
                    path = None
            raise ElementNotFoundError(
                text, screenshot_path=path,
                closest_match=closest[0], confidence=closest[1])
        time.sleep(interval)


def _field_point(box, screen_size, field_gap=30):
    """Return the point to click to focus the field for a label.

    The label's box is (left, top, width, height) and screen_size is
    (width, height). The field usually sits to the right of its label
    on the same row, so the point is just past the label's right edge,
    ``field_gap`` pixels over, at the label's vertical center.

    When the label spans nearly the full screen width there is no
    room for a field to its right (less than ``field_gap`` plus 20
    pixels of field to click into), so the point falls back to below
    the label: the label's horizontal center, ``field_gap`` pixels
    under its bottom edge. This happens with full-width headings and
    with labels stacked above their field.

    Returns ((x, y), placement) where placement is "right" or "below".
    """
    left, top, width, height = box
    screen_width, _screen_height = screen_size
    label_right = left + width
    label_center_y = top + height / 2.0
    label_center_x = left + width / 2.0
    label_bottom = top + height
    if label_right + field_gap + 20 <= screen_width:
        return (label_right + field_gap, label_center_y), "right"
    return (label_center_x, label_bottom + field_gap), "below"


def click_text(text, timeout=10.0, interval=1.0, session=None,
               language="eng", screenshot_dir=None):
    """Find text on screen with OCR and click its center.

    Retries with fresh screenshots until the timeout expires. Returns
    the (x, y) center clicked, or None in dry-run mode. Raises
    ElementNotFoundError carrying the last screenshot path and the
    closest OCR word when the text never appears, and
    ProviderNotInstalledError when Tesseract is absent.
    """
    session = session or get_default_session()
    pg = get_pyautogui()
    match = _find_text(text, timeout=timeout, interval=interval,
                       language=language, screenshot_dir=screenshot_dir)
    x, y = match["center"]
    session.execute(
        "click_text",
        {"text": text, "x": x, "y": y},
        lambda: pg.click(x, y),
        result_summary="clicked (%s, %s)" % (x, y))
    return (x, y) if not session.dry_run else None


def click_image(image, session=None, timeout=10.0, interval=0.5,
                confidence=None, region=None):
    """Wait for an image to appear, then click its center.

    Returns the (x, y) center clicked, or None in dry-run mode.
    Raises ActionTimeoutError (carrying the last screenshot path)
    when the image never appears.
    """
    session = session or get_default_session()
    pg = get_pyautogui()
    box = wait_for_image(image, timeout=timeout, interval=interval,
                         confidence=confidence, region=region)
    x = box[0] + box[2] / 2.0
    y = box[1] + box[3] / 2.0
    session.execute(
        "click_image",
        {"image": image, "x": x, "y": y},
        lambda: pg.click(x, y),
        result_summary="clicked (%s, %s)" % (x, y))
    return (x, y) if not session.dry_run else None


def click_point(x, y, button="left", session=None):
    """Click a point, through the safety layer.

    Returns None. Use observe() plus the element list to choose the
    point; prefer click_text, click_image, or click_element when a
    target can be named instead of guessed by coordinates.
    """
    session = session or get_default_session()
    pg = get_pyautogui()
    return session.execute(
        "click_point",
        {"x": x, "y": y, "button": button},
        lambda: pg.click(x, y, button=button),
        result_summary="clicked (%s, %s)" % (x, y))


def fill_field(text, value, session=None, timeout=10.0, interval=0.05,
               field_gap=30, language="eng", screenshot_dir=None):
    """Click a field by its label, then type a value into it.

    The label is matched first against the accessibility element list
    (macOS), which returns the real field element, then by OCR text.
    Raises ElementNotFoundError when the label cannot be found either
    way.

    On the OCR path the label itself is not clicked: clicking a label
    does not focus the field in most apps. Instead the click lands on
    the field, which usually sits to the right of its label on the
    same row. The point is ``field_gap`` pixels (default 30) past the
    label's right edge, at the label's vertical center. When the label
    spans nearly the full screen width, so there is no room for a
    field to its right, the click falls back to below the label: the
    label's horizontal center, ``field_gap`` pixels under its bottom
    edge. See ``_field_point`` for the exact rule.
    """
    session = session or get_default_session()
    pg = get_pyautogui()
    clicked = False
    try:
        element = (find_element(title=text)
                   or find_element(title_contains=text))
    except NotSupportedError:
        element = None
    if element is not None:
        click_element(element, session=session)
        clicked = True
    if not clicked:
        match = _find_text(text, timeout=timeout, interval=1.0,
                           language=language,
                           screenshot_dir=screenshot_dir)
        (x, y), placement = _field_point(match["box"], pg.size(),
                                         field_gap=field_gap)
        session.execute(
            "click_field",
            {"label": text, "x": x, "y": y, "placement": placement},
            lambda: pg.click(x, y),
            result_summary="clicked field %s of %r (%s, %s)"
                           % (placement, text, x, y))
    session.execute(
        "type",
        {"text": value},
        lambda: pg.typewrite(value, interval=interval),
        result_summary="typed %d chars" % (len(value),))
    return None
