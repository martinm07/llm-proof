"""Canary spec parsing and canary insertion."""

import math
import sys
from typing import Any

import pymupdf as fitz

# Placement modes. A separator token resolves to a mode when it is a
# case-insensitive prefix of the mode name; ``center`` is an accepted
# spelling of ``centre``. The modes start with distinct letters, so a
# token can match at most one.
POSITION_MODES = ("after-text", "top", "centre", "bottom")
_POSITION_ALIASES = {"center": "centre"}

CANARY_FONT_SIZE = 12.0
GEOMETRIC_INSET = 24.0  # points from the page edge for top/centre/bottom
MAX_CANARY_LINES = 3
# Measured insert_textbox line costs at CANARY_FONT_SIZE: a box needs
# ~20pt for its first line and ~16.5pt per further line.
_LINE_HEIGHT = 18.5
_FIRST_LINE_EXTRA = 3.0


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _match_position(token: str) -> str | None:
    """Resolve a separator token to a placement mode.

    Matching is case-insensitive by prefix: ``c``, ``cen`` and ``CENTER``
    all resolve to ``centre``. Returns None when the token matches no mode.
    """
    token = token.strip().lower()
    if not token:
        return None
    matches = {mode for mode in POSITION_MODES if mode.startswith(token)}
    if token in _POSITION_ALIASES:
        matches.add(_POSITION_ALIASES[token])
    return matches.pop() if len(matches) == 1 else None


def _parse_page(part: str, placement: dict[str, Any]) -> None:
    try:
        page_num = int(part.split(":", 1)[1].strip())
    except ValueError:
        _warn(f"ignoring malformed page directive: {part!r}")
        return
    if page_num <= 0:
        _warn(f"ignoring page directive outside range: {part!r}")
        return
    if "page" in placement:
        _warn(f"multiple page directives on one separator; using page {page_num}")
    placement["page"] = page_num


def _parse_directive(directive: str) -> dict[str, Any]:
    """Parse the comma-separated directives on one separator line."""
    placement: dict[str, Any] = {}
    for part in directive.split(","):
        part = part.strip()
        if not part:
            continue
        if part.lower().startswith("page:"):
            _parse_page(part, placement)
        else:
            mode = _match_position(part)
            if mode is None:
                _warn(f"ignoring unrecognised placement directive: {part!r}")
            elif "position" in placement:
                _warn(
                    f"multiple placement modes on one separator; "
                    f"keeping {placement['position']!r}, ignoring {part!r}"
                )
            else:
                placement["position"] = mode
    return placement


def parse_canary_spec(spec_text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse a canary spec file.

    Format: blocks separated by '---', with optional placement directives
    on the separator, in front-matter style (before the canary they apply
    to). Directives are comma-separated:

    - ``page: N`` selects the page (1-indexed, exact key-value).
    - A placement mode keyword (``after-text``, ``top``, ``centre``,
      ``bottom``; matched case-insensitively by prefix, with ``center``
      accepted as a spelling of ``centre``) selects where on the page the
      canary is anchored.

    Unrecognised directives are ignored with a warning. Returns a list of
    (canary_text, placement) tuples; placement carries a ``page`` key and/or
    a ``position`` key, each absent when not given.
    """
    lines = spec_text.split("\n")
    canaries: list[tuple[str, dict[str, Any]]] = []
    current_text: list[str] = []
    next_placement: dict[str, Any] = {}

    for line in lines:
        if line.startswith("---"):
            # Previous block is complete; emit it with its placement
            if current_text:
                block_text = "\n".join(current_text).strip()
                if block_text:
                    canaries.append((block_text, dict(next_placement)))
                current_text = []

            # Parse directives on the separator for the NEXT block
            next_placement = _parse_directive(line[3:])
        else:
            current_text.append(line)

    # Final block
    if current_text:
        block_text = "\n".join(current_text).strip()
        if block_text:
            canaries.append((block_text, dict(next_placement)))

    return canaries


def get_page_sentences(page) -> list[list[Any]]:
    """Extract sentences (word sequences) from a page with coordinates."""
    words = page.get_text("words")
    sentences = []
    current_sentence = []
    prev_word = None

    for w in words:
        _, y0, _, _, _, _, _, _ = w
        if prev_word and y0 > prev_word[3] + 5:
            # New paragraph/line
            if current_sentence:
                sentences.append(current_sentence)
            current_sentence = [w]
        else:
            current_sentence.append(w)
        prev_word = w

    if current_sentence:
        sentences.append(current_sentence)

    return sentences


def _insert_after_text(page, canary_text: str) -> bool:
    """Insert a canary after a word of the page's text.

    Returns False when the page carries no text; the canary is skipped.
    """
    sentences = get_page_sentences(page)
    if not sentences:
        return False

    # Find insertion point (sentence index)
    insert_idx = int(len(sentences) * 0.5)
    if insert_idx >= len(sentences):
        insert_idx = len(sentences) - 1

    sentence = sentences[insert_idx]
    if not sentence:
        return False

    # Insert after first word of the target sentence
    word = sentence[0]
    insert_x = word[2] + 2
    insert_y = word[1]

    page.insert_text(
        (insert_x, insert_y), canary_text, color=(1, 1, 1), fontsize=CANARY_FONT_SIZE
    )
    return True


def _rendered_line_count(text: str, box_width: float) -> int:
    """Count the lines text occupies when wrapped to box_width."""
    count = 0
    for line in text.split("\n"):
        if line.strip():
            width = fitz.get_text_length(line, fontsize=CANARY_FONT_SIZE)
            count += max(1, math.ceil(width / box_width))
        else:
            count += 1
    return count


def _truncate_to_max_lines(text: str, box_width: float) -> str:
    """Cut text down to the first MAX_CANARY_LINES rendered lines."""
    kept: list[str] = []
    count = 0
    for line in text.split("\n"):
        if line.strip():
            width = fitz.get_text_length(line, fontsize=CANARY_FONT_SIZE)
            needed = max(1, math.ceil(width / box_width))
        else:
            needed = 1
        if count + needed > MAX_CANARY_LINES:
            return "\n".join(kept)
        kept.append(line)
        count += needed
    return text


def _insert_geometric(page, canary_text: str, position: str) -> bool:
    """Insert a canary at a fixed position of the page (top, centre or
    bottom), independent of the page's text. Always succeeds.
    """
    rect = page.rect
    box_width = rect.width - 2 * GEOMETRIC_INSET
    text = canary_text
    if _rendered_line_count(text, box_width) > MAX_CANARY_LINES:
        _warn(
            f"canary exceeds {MAX_CANARY_LINES} lines; truncating: {canary_text[:40]!r}"
        )
        text = _truncate_to_max_lines(text, box_width)
    lines = min(_rendered_line_count(text, box_width), MAX_CANARY_LINES)
    box_height = lines * _LINE_HEIGHT + _FIRST_LINE_EXTRA
    x0 = GEOMETRIC_INSET
    x1 = rect.width - GEOMETRIC_INSET
    if position == "top":
        y0 = GEOMETRIC_INSET
    elif position == "bottom":
        y0 = rect.height - GEOMETRIC_INSET - box_height
    else:  # centre
        y0 = (rect.height - box_height) / 2
    box = fitz.Rect(x0, y0, x1, y0 + box_height)
    unused = page.insert_textbox(
        box,
        text,
        fontsize=CANARY_FONT_SIZE,
        color=(1, 1, 1),
        align=fitz.TEXT_ALIGN_CENTER,
    )
    if unused < 0:
        _warn(f"canary did not fit its box: {canary_text[:40]!r}")
    return True


def insert_canary(page, canary_text: str, placement: dict[str, Any]) -> bool:
    """Insert one canary on a page according to its placement.

    Geometric modes (top/centre/bottom) always insert; ``after-text``
    anchors after a word of the page's text and is skipped when the page
    has no text.
    """
    position = placement.get("position", "after-text")
    if position in ("top", "centre", "bottom"):
        return _insert_geometric(page, canary_text, position)
    return _insert_after_text(page, canary_text)


def insert_all_canaries(doc, canaries: list[tuple[str, dict[str, Any]]]) -> int:
    """Insert all canaries into the document.

    Page selection: canaries with a ``page`` key go to that page; the rest
    are round-robined across all pages starting from page 1. Placement
    mode: every canary defaults to ``after-text`` except the first canary,
    which defaults to ``centre`` — the first canary is the one the user has
    most thought through, and it must be embedded even in text-poor PDFs,
    where ``after-text`` would silently drop it.

    Returns the count of successfully inserted canaries.
    """
    total_pages = len(doc)
    if total_pages == 0:
        _warn("document has no pages; no canaries inserted")
        return 0

    inserted = 0
    unplaced_idx = 0
    for i, (text, placement) in enumerate(canaries):
        page_num = placement.get("page")
        if page_num is None:
            page_idx = unplaced_idx % total_pages
            unplaced_idx += 1
        elif 1 <= page_num <= total_pages:
            page_idx = page_num - 1
        else:
            _warn(
                f"canary {i + 1}: page {page_num} is outside the "
                f"document (1-{total_pages}); skipping"
            )
            continue

        effective = placement
        if i == 0 and "position" not in placement:
            effective = {**placement, "position": "centre"}

        if insert_canary(doc[page_idx], text, effective):
            inserted += 1

    return inserted
