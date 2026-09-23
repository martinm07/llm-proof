"""Tests for llm-proof core functionality."""

import hashlib
import re
from pathlib import Path

import pymupdf as fitz
import pytest

from llm_proof.canaries import insert_all_canaries, parse_canary_spec
from llm_proof.password_cmd import get_password
from llm_proof.protect import protect_pdf
from llm_proof.seed import (
    MARKER_DEFAULT,
    derive_seed,
    extract_canonical_content,
    parse_seed,
    validate_marker,
)


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a simple test PDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This is a test document for llm-proof.", fontsize=12)
    path = tmp_path / "sample.pdf"
    doc.save(str(path))
    doc.close()
    return path


# Repo fixture: a real-world PDF 1.7 file whose trailer is a cross-reference
# stream (classic-xref files are what every other test exercises).
TEST_PDF = Path(__file__).parent.parent / "test.pdf"


@pytest.fixture
def canary_spec(tmp_path):
    """Create a canary spec file."""
    path = tmp_path / "canaries.txt"
    path.write_text("Canary A.\n---\nCanary B.\n")
    return path


def test_protect_creates_encrypted_pdf(sample_pdf, tmp_path):
    """Protection should produce an encrypted PDF."""
    output = tmp_path / "protected.pdf"
    protect_pdf(str(sample_pdf), str(output), "test-salt")

    doc = fitz.open(str(output))
    assert doc.needs_pass == 1
    doc.close()


def test_password_re_derivation_from_protected_file(sample_pdf, canary_spec, tmp_path):
    """The password should be re-derivable from the protected file + salt alone."""
    output = tmp_path / "protected.pdf"
    result_path, inserted, password, _ = protect_pdf(
        str(sample_pdf), str(output), "test-salt", str(canary_spec)
    )
    assert inserted == 2

    re_derived = get_password(str(result_path), "test-salt")
    assert re_derived == password
    assert len(re_derived) == 24
    assert all(c in "0123456789abcdef" for c in re_derived)

    # Verify authentication works
    doc = fitz.open(str(result_path))
    assert doc.authenticate(password) != 0
    doc.close()


def test_determinism(sample_pdf, tmp_path):
    """Same plain document + same salt -> identical password and stable ID."""
    out1 = tmp_path / "p1.pdf"
    out2 = tmp_path / "p2.pdf"
    _, _, pw1, _ = protect_pdf(str(sample_pdf), str(out1), "test-salt")
    _, _, pw2, _ = protect_pdf(str(sample_pdf), str(out2), "test-salt")
    assert pw1 == pw2

    doc = fitz.open(str(sample_pdf))
    canonical = extract_canonical_content(doc)
    doc.close()
    expected_seed = hashlib.sha256(canonical.encode("utf-8")).digest()[:16].hex()

    doc = fitz.open(str(out1))
    _t, id_value = doc.xref_get_key(-1, "ID")
    doc.close()
    assert id_value.startswith(f"[({MARKER_DEFAULT}-{expected_seed})")


def test_protect_xref_stream_input(tmp_path):
    """Regression: inputs whose trailer is a cross-reference stream.

    PyMuPDF silently drops xref_set_key(-1, "ID", ...) on xref-stream
    trailers; protect_pdf must verify by read-back and round-trip through a
    plain save so the seed survives into the encrypted output.
    """
    # Sanity: the fixture must actually use an xref stream for this test to
    # exercise the bug path.
    assert b"/XRef" in TEST_PDF.read_bytes()

    out = tmp_path / "protected.pdf"
    _, _, password, _ = protect_pdf(str(TEST_PDF), str(out), "test-salt")

    doc = fitz.open(str(out))
    assert doc.authenticate(password) != 0
    _t, id_value = doc.xref_get_key(-1, "ID")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    doc.close()
    assert id_value.startswith(f"[({MARKER_DEFAULT}-")

    assert get_password(str(out), "test-salt") == password


def test_canary_independence(sample_pdf, tmp_path):
    """Canaries never contribute to the password; they stay extractable."""
    spec_a = tmp_path / "a.txt"
    spec_a.write_text("Alpha canary.\n---\nBeta canary.\n")
    spec_b = tmp_path / "b.txt"
    spec_b.write_text("Gamma canary.\n")

    out_a = tmp_path / "pa.pdf"
    out_b = tmp_path / "pb.pdf"
    out_none = tmp_path / "pnone.pdf"

    _, _, pw_a, _ = protect_pdf(str(sample_pdf), str(out_a), "test-salt", str(spec_a))
    _, _, pw_b, _ = protect_pdf(str(sample_pdf), str(out_b), "test-salt", str(spec_b))
    _, _, pw_none, _ = protect_pdf(str(sample_pdf), str(out_none), "test-salt")

    assert pw_a == pw_b == pw_none

    doc = fitz.open(str(out_a))
    assert doc.authenticate(pw_a) != 0
    extracted = extract_canonical_content(doc)
    doc.close()
    assert "Alpha canary." in extracted
    assert "Beta canary." in extracted

    doc = fitz.open(str(out_b))
    assert doc.authenticate(pw_b) != 0
    extracted = extract_canonical_content(doc)
    doc.close()
    assert "Gamma canary." in extracted


def test_password_rejects_unencrypted(sample_pdf):
    """An unencrypted input is rejected with a distinct message."""
    with pytest.raises(ValueError, match="not a password-protected PDF"):
        get_password(str(sample_pdf), "test-salt")


def test_password_rejects_foreign_protected(sample_pdf, tmp_path):
    """A protected PDF whose file ID carries no marked seed is rejected."""
    doc = fitz.open(str(sample_pdf))
    doc.xref_set_key(
        -1,
        "ID",
        "[<00112233445566778899aabbccddeeff><00112233445566778899aabbccddeeff>]",
    )
    out = tmp_path / "foreign.pdf"
    doc.save(
        str(out),
        encryption=fitz.PDF_ENCRYPT_AES_256,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]
        user_pw="some-other-password",
        owner_pw="some-other-password",
    )
    doc.close()

    with pytest.raises(ValueError, match='no "LLMPROOF" seed'):
        get_password(str(out), "test-salt")


def test_custom_marker(sample_pdf, tmp_path):
    """A custom marker is written into the ID and required for re-derivation."""
    out = tmp_path / "acme.pdf"
    protect_pdf(str(sample_pdf), str(out), "test-salt", marker="ACME")

    assert b"(ACME-" in out.read_bytes()

    password = get_password(str(out), "test-salt", "ACME")
    assert len(password) == 24
    assert all(c in "0123456789abcdef" for c in password)

    with pytest.raises(ValueError, match='no "LLMPROOF" seed'):
        get_password(str(out), "test-salt")


def test_marker_validation():
    """Markers must start with a letter/digit and use only [A-Za-z0-9_-]."""
    for bad in ["(bad", "a b", "-dash", ""]:
        with pytest.raises(ValueError, match="must start with a letter or digit"):
            validate_marker(bad)

    for good in ["LLMPROOF", "ACME", "a-b_c9", "9"]:
        validate_marker(good)


def test_parse_seed():
    """parse_seed extracts the lowercase seed from a marked literal ID."""
    good = "[(LLMPROOF-f66fbc1333121d9b50ed64a4e8cc04a8)<8FF36D3E506326F95BCD86C9D7FEA758>]"
    assert parse_seed(good, "LLMPROOF") == "f66fbc1333121d9b50ed64a4e8cc04a8"

    # Hex in the seed is case-insensitive; the result is lowercased
    upper = "[(LLMPROOF-F66FBC1333121D9B50ED64A4E8CC04A8)<8FF36D3E506326F95BCD86C9D7FEA758>]"
    assert parse_seed(upper, "LLMPROOF") == "f66fbc1333121d9b50ed64a4e8cc04a8"

    # Wrong marker, hex first element, wrong tail length, malformed value
    assert parse_seed(good, "ACME") is None
    assert (
        parse_seed(
            "[<00112233445566778899AABBCCDDEEFF><00112233445566778899AABBCCDDEEFF>]",
            "LLMPROOF",
        )
        is None
    )
    assert (
        parse_seed("[(LLMPROOF-f66fbc1333121d9b50ed64a4e8cc04a)<x>]", "LLMPROOF")
        is None
    )
    assert (
        parse_seed("[(LLMPROOF-f66fbc1333121d9b50ed64a4e8cc04a8a)<x>]", "LLMPROOF")
        is None
    )
    assert parse_seed("garbage", "LLMPROOF") is None


def test_seed_shape():
    """derive_seed returns 32 lowercase hex characters."""
    assert re.fullmatch(r"[0-9a-f]{32}", derive_seed("some content"))


def test_canary_insertion(sample_pdf, tmp_path):
    """Canaries should be inserted and extractable."""
    doc = fitz.open(str(sample_pdf))
    canaries = parse_canary_spec("C1.\n---\nC2.\n")
    insert_all_canaries(doc, canaries)

    canonical = extract_canonical_content(doc)
    assert "C1." in canonical
    assert "C2." in canonical
    doc.close()


def test_canary_spec_parsing():
    """Canary spec parsing should handle multiple blocks and directives."""
    spec = "First canary.\n--- page: 5\nSecond canary.\n---\nThird canary.\n"
    canaries = parse_canary_spec(spec)

    assert len(canaries) == 3
    assert canaries[0][0] == "First canary."
    assert canaries[0][1] is None  # No placement
    assert canaries[1][0] == "Second canary."
    assert canaries[1][1] == {"page": 5}
    assert canaries[2][0] == "Third canary."
    assert canaries[2][1] is None  # No placement


def test_canary_placement_directive(sample_pdf, tmp_path):
    """Canaries with page placement directives should go to the correct page."""
    doc = fitz.open(str(sample_pdf))
    canaries = parse_canary_spec("--- page: 1\nTargeted canary.\n")
    insert_all_canaries(doc, canaries)

    canonical = extract_canonical_content(doc)
    assert "Targeted canary." in canonical
    doc.close()


def test_free_text_annotation_exclusion(tmp_path):
    """Words inside FreeText annotations should be excluded from canonical content."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Original text.", fontsize=12)

    # Add a FreeText annotation
    page.add_freetext_annot((100, 100, 200, 150), "Annotation text.")
    doc.save(str(tmp_path / "annotated.pdf"))
    doc.close()

    doc = fitz.open(str(tmp_path / "annotated.pdf"))
    canonical = extract_canonical_content(doc)
    assert "Original text." in canonical
    assert "Annotation text." not in canonical
    doc.close()
