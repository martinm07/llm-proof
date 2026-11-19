"""Tests for canary spec parsing and canary insertion."""

import pymupdf as fitz
import pytest

from llm_proof.canaries import insert_all_canaries, parse_canary_spec


@pytest.fixture
def text_pdf(tmp_path):
    """A two-page PDF: page 1 carries text, page 2 is blank."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=400)
    page.insert_text((72, 100), "Some anchor text for the canaries.", fontsize=11)
    doc.new_page(width=595, height=400)
    path = tmp_path / "two-page.pdf"
    doc.save(str(path))
    doc.close()
    return path


# --- spec parsing -----------------------------------------------------------


def test_parse_plain_blocks():
    canaries = parse_canary_spec("First.\n---\nSecond.\n")
    assert [t for t, _ in canaries] == ["First.", "Second."]
    assert all(p == {} for _, p in canaries)


def test_parse_page_directive():
    canaries = parse_canary_spec("--- page: 5\nTargeted.\n")
    assert canaries == [("Targeted.", {"page": 5})]


def test_parse_position_keywords_exact():
    for keyword in ("after-text", "top", "centre", "bottom"):
        canaries = parse_canary_spec(f"--- {keyword}\nCanary.\n")
        assert canaries == [("Canary.", {"position": keyword})], keyword


def test_parse_position_prefix_matching():
    for token, mode in [
        ("c", "centre"),
        ("cen", "centre"),
        ("C", "centre"),
        ("t", "top"),
        ("to", "top"),
        ("b", "bottom"),
        ("bo", "bottom"),
        ("a", "after-text"),
        ("af", "after-text"),
        ("after", "after-text"),
    ]:
        canaries = parse_canary_spec(f"--- {token}\nCanary.\n")
        assert canaries == [("Canary.", {"position": mode})], token


def test_parse_center_alias_and_case():
    for token in ("center", "CENTER", "Centre", "cent"):
        canaries = parse_canary_spec(f"--- {token}\nCanary.\n")
        assert canaries == [("Canary.", {"position": "centre"})], token


def test_parse_unknown_directive_warns(capsys):
    canaries = parse_canary_spec("--- left\nCanary.\n")
    assert canaries == [("Canary.", {})]
    assert "left" in capsys.readouterr().err


def test_parse_malformed_page_warns(capsys):
    canaries = parse_canary_spec("--- page: abc\nCanary.\n")
    assert canaries == [("Canary.", {})]
    assert "page: abc" in capsys.readouterr().err


def test_parse_combined_page_and_position():
    canaries = parse_canary_spec("--- page: 11, centre\nCanary.\n")
    assert canaries == [("Canary.", {"page": 11, "position": "centre"})]


def test_parse_leading_separator_no_phantom():
    """A file starting with a directive separator yields no empty canary."""
    spec = "--- page: 11\nThis is the first canary.\n---\nsecond\n---\nthird"
    canaries = parse_canary_spec(spec)
    assert canaries == [
        ("This is the first canary.", {"page": 11}),
        ("second", {}),
        ("third", {}),
    ]


def test_parse_duplicate_mode_keeps_first(capsys):
    canaries = parse_canary_spec("--- top, bottom\nCanary.\n")
    assert canaries == [("Canary.", {"position": "top"})]
    assert "bottom" in capsys.readouterr().err


# --- insertion ---------------------------------------------------------------


def test_geometric_canary_on_text_free_page(text_pdf):
    """Geometric placement is inserted even when the page has no text."""
    doc = fitz.open(str(text_pdf))
    canaries = parse_canary_spec("--- page: 2, top\nTrusted canary.\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 1
    assert "Trusted canary." in doc[1].get_text()
    doc.close()


def test_geometric_positions(text_pdf):
    """top/centre/bottom land at their positions of the page."""
    doc = fitz.open(str(text_pdf))
    canaries = parse_canary_spec(
        "--- page: 1, top\ntop canary\n"
        "--- page: 1, centre\ncentre canary\n"
        "--- page: 1, bottom\nbottom canary\n"
    )
    insert_all_canaries(doc, canaries)
    words = {w[4]: w for w in doc[0].get_text("words")}
    height = float(doc[0].rect.height)
    assert float(words["top"][1]) < 40
    assert abs(float(words["centre"][1]) - height / 2) < 15
    assert float(words["bottom"][1]) > height - 50
    doc.close()


def test_first_canary_defaults_to_centre_on_blank_page():
    """The first canary is embedded at the centre of a text-free page; a
    later after-text canary then anchors on the first canary's text and is
    embedded too (canary text counts as page text)."""
    doc = fitz.open()
    doc.new_page(width=595, height=400)
    canaries = parse_canary_spec("First canary.\n---\nSecond canary.\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 2
    text = doc[0].get_text()
    assert "First canary." in text
    assert "Second canary." in text
    doc.close()


def test_first_canary_page_directive_gets_centre(text_pdf):
    """A page directive on the first canary selects the page; centre applies."""
    doc = fitz.open(str(text_pdf))
    canaries = parse_canary_spec("--- page: 2\nFirst canary.\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 1
    words = [w for w in doc[1].get_text("words") if w[4] == "First"]
    assert abs(float(words[0][1]) - float(doc[1].rect.height) / 2) < 15
    doc.close()


def test_first_canary_explicit_after_text():
    """An explicit after-text opts the first canary out of the centre default."""
    doc = fitz.open()
    doc.new_page(width=595, height=400)  # blank page
    canaries = parse_canary_spec("--- after-text\nFirst canary.\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 0
    doc.close()


def test_after_text_mode_unchanged(text_pdf):
    """after-text still anchors in the page's text."""
    doc = fitz.open(str(text_pdf))
    canaries = parse_canary_spec("--- page: 1, after-text\nAnchored canary.\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 1
    assert "Anchored canary." in doc[0].get_text()
    doc.close()


def test_out_of_range_page_warns_and_skips(text_pdf, capsys):
    doc = fitz.open(str(text_pdf))
    canaries = parse_canary_spec("--- page: 99\nLost canary.\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 0
    assert "99" in capsys.readouterr().err
    doc.close()


def test_long_canary_truncated_with_warning(text_pdf, capsys):
    """A canary longer than 3 lines is cut to 3 lines with a warning."""
    doc = fitz.open(str(text_pdf))
    long_canary = "\n".join(f"line number {i}" for i in range(1, 6))
    canaries = parse_canary_spec(f"--- page: 2, centre\n{long_canary}\n")
    inserted = insert_all_canaries(doc, canaries)
    assert inserted == 1
    assert "truncat" in capsys.readouterr().err.lower()
    text = doc[1].get_text()
    for i in (1, 2, 3):
        assert f"line number {i}" in text
    assert "line number 4" not in text
    doc.close()
