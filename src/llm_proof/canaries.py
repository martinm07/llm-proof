"""Canary spec parsing and canary insertion."""

from typing import Any


def parse_canary_spec(spec_text: str) -> list[tuple[str, dict | None]]:
    """Parse a canary spec file.

    Format: blocks separated by '---', with optional placement directives.
    Directives are in front-matter style (before the canary they apply to).

    Returns list of (canary_text, placement) tuples, where placement is
    None for unplaced canaries or {'page': N} for placed ones.
    """
    lines = spec_text.split("\n")
    canaries = []
    current_text = []
    next_placement = None  # Placement for the next block

    for line in lines:
        if line.startswith("---"):
            # Previous block is complete; emit it with its placement
            if current_text:
                block_text = "\n".join(current_text).strip()
                if block_text:
                    canaries.append((block_text, next_placement))
            current_text = []

            # Parse directive on separator for the NEXT block
            directive = line[3:].strip()
            next_placement = None
            if directive:
                for part in directive.split(","):
                    part = part.strip()
                    if part.startswith("page:"):
                        try:
                            page_num = int(part.split(":")[1].strip())
                            if page_num > 0:
                                next_placement = {"page": page_num}
                        except ValueError:
                            pass  # Malformed page directive: warn later
        else:
            current_text.append(line)

    # Final block
    if current_text:
        block_text = "\n".join(current_text).strip()
        if block_text:
            canaries.append((block_text, next_placement))

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


def insert_canary(page, canary_text: str, position_fraction: float = 0.5) -> bool:
    """Insert a canary as white text at the specified position in the page.

    position_fraction: 0.0 = start, 0.5 = middle, 1.0 = end of page text.
    """
    sentences = get_page_sentences(page)
    if not sentences:
        return False

    # Find insertion point (sentence index)
    insert_idx = int(len(sentences) * position_fraction)
    if insert_idx >= len(sentences):
        insert_idx = len(sentences) - 1

    sentence = sentences[insert_idx]
    if not sentence:
        return False

    # Insert after first word of the target sentence
    word = sentence[0]
    insert_x = word[2] + 2
    insert_y = word[1]

    # Use insert_text with white color
    page.insert_text((insert_x, insert_y), canary_text, color=(1, 1, 1), fontsize=8)

    return True


def insert_all_canaries(doc, canaries: list[tuple[str, dict | None]]) -> int:
    """Insert all canaries into the document.

    Canaries with page placement go to that page. Unplaced canaries are
    round-robined across all pages. Multiple canaries on a page are
    evenly distributed.

    Returns count of successfully inserted canaries.
    """
    total_pages = len(doc)
    inserted = 0

    # Separate placed and unplaced
    placed_canaries = []
    unplaced_canaries = []
    for text, placement in canaries:
        if placement and placement.get("page"):
            placed_canaries.append((text, placement["page"]))
        else:
            unplaced_canaries.append(text)

    # Handle placed canaries
    for text, page_num in placed_canaries:
        if 1 <= page_num <= total_pages:
            success = insert_canary(doc[page_num - 1], text, 0.5)
            if success:
                inserted += 1

    # Handle unplaced canaries via round-robin
    if unplaced_canaries:
        for i, text in enumerate(unplaced_canaries):
            page_idx = i % total_pages
            success = insert_canary(doc[page_idx], text, 0.5)
            if success:
                inserted += 1

    return inserted
