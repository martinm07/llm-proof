# Spec: `llm-proof password` from the protected PDF alone

Status: ready-for-agent
Design: agreed 2026-09-21 — see ADR-0005 (accepted), ADR-0003 (superseded), ADR-0001/0002/0004 (still in force)

## 1. Goal

Today `llm-proof password` requires the **original plain PDF plus the canary spec file** to re-derive the lock password. It must instead work from the **protected PDF plus the user's salt only** — no canaries file, no original document.

User story:

```bash
llm-proof protect report.pdf --canaries canaries.txt -o report.protected.pdf
# ... months later, canaries file lost, original no longer at hand
llm-proof password report.protected.pdf   # prints the 24-char password
```

Acceptance:

- Same plain document + same salt → identical password, every run, **regardless of canaries**.
- A protected PDF that was not created by `llm-proof protect` (or was created with a different marker) is clearly reported as unrecognised, with a distinct message from "input isn't even encrypted".
- stdout of `password` is the password and nothing else.

## 2. Current state (what you are changing)

- `src/llm_proof/protect.py` — `protect_pdf(input_path, output_path, salt, canaries_file=None) -> (path, inserted, password)`: open plain PDF (error if `needs_pass`) → **insert canaries** → `canonical = extract_canonical_content(doc)` (**after** canaries) → `password = derive_password(salt, canonical)` → save AES-256 (`user_pw == owner_pw`).
- `src/llm_proof/password_cmd.py` — `get_password(input_path, salt, canaries_file=None)`: open (error if `needs_pass` — i.e. it today _requires an unencrypted input_) → insert canaries in memory → canonical → `derive_password`. This module is rewritten around the protected file.
- `src/llm_proof/identity.py` — `extract_canonical_content(doc) -> str` (per-page `get_text("words")`, excluding words whose centre falls inside a FreeText annotation rect, words space-joined per page, pages newline-joined) and `derive_identity(canonical) -> str` (full 64-hex sha256 — **dead code, imported nowhere**; it is replaced by `derive_seed`).
- `src/llm_proof/password.py` — `derive_password(salt, content) -> str`: `sha256(salt.encode() + content.encode()).hexdigest()[:24]`. **Unchanged.**
- `src/llm_proof/config.py` — `get_config_dir()` (platform config dir) and `get_salt(flag_value)`: flag > `LLM_PROOF_SALT` env > `salt` key in `config.toml`; returns `None` when absent.
- `src/llm_proof/cli.py` — argparse; `protect` and `password` subcommands; both take `--salt`; `password` also takes `--canaries`. Salt resolution at top of `main()` (error + exit 1 when unresolvable), then per-command `try/except ValueError/Exception` → `Error: ...` on stderr, exit 1.
- `src/llm_proof/canaries.py` — canary spec parsing + white-text insertion (round-robin or `page: N` directives). **Unchanged.**
- `tests/test_core.py` — protects with canaries, re-derives from plain+canaries, canary parsing/placement/FreeText-exclusion tests.
- `pyproject.toml` — PyMuPDF pinned exactly (`==1.28.2`). **No new dependencies for this feature.**
- Repo-root fixtures: `test.pdf` (plain PDF), `canaries.txt` (sample spec).

## 3. Design decisions (agreed — do not revisit)

1. **Seed** = `sha256(canonical).digest()[:16].hex()` — 32 **lowercase** hex chars. Canonical content is `extract_canonical_content` of the plain document **before** canary insertion. Deterministic: same input → same seed → same password.
2. **Canaries never contribute to the password.** They are still inserted and remain extractable after unlock (that is their only purpose: leak attribution).
3. The **salt is the sole secret** (hash-scheme details are also secret, immaterial).
4. `protect` order: open → canonical (pre-canary) → seed → password → set `/ID` → insert canaries → save.
5. **Marker** — user-chosen label prefixing the seed. Resolution: `--marker` flag > `marker` key in `config.toml` > default `LLMPROOF`. No env var. Markers are case-sensitive. Validated against `^[A-Za-z0-9][A-Za-z0-9_-]*$`; invalid markers are a clear user-friendly error, checked in **both** subcommands.
6. **On-disk form**: `/ID[0]` = PDF **literal string** `(<MARKER>-<seed>)`; `/ID[1]` set to the same literal at write time and left to PyMuPDF, which recomputes it to 16-byte uppercase hex on every save (verified — see §4).
7. `password`: open **without** password → read `/ID` → first element must be a literal starting with `<marker>-` followed by exactly 32 hex chars (case-insensitive; canonicalise to lowercase) → `derive_password(salt, seed)` → print. **No authentication** step.
8. `password` error stages (stderr via the existing `Error: ...` wrapper, exit 1), in detection order:
   1. no salt resolvable — existing message, unchanged.
   2. invalid marker (bad charset) — see decision 5.
   3. input not password-protected — `not a password-protected PDF`.
   4. protected, but no `<marker>` seed in `/ID[0]` — `no "<MARKER>" seed in the PDF's file ID: the file was not created by llm-proof protect, or it was protected with a different marker` (interpolate the marker actually looked for; enumerate both causes).
9. **CLI**: `password` **drops `--canaries`**, keeps `--salt`, **gains `--marker`**; stdout = password only. `protect` **gains `--marker`**, everything else unchanged.
10. **No backward compatibility** with the old scheme (no such PDFs exist). No marker versioning (if ever needed, introduce a new marker prefix and parse both — do not build for it now).
11. **Renaming**: `identity.py` → `seed.py`; `derive_identity` → `derive_seed` (new behaviour: 16-byte truncation, so it is a replacement, not a rename of the old function). `extract_canonical_content` moves to `seed.py` (same concern).

## 4. Verified facts (PyMuPDF 1.28.2, the exact pin)

All verified experimentally this session. Scripts: `.scratch/id-literal.py`, `.scratch/proto.py`; raw artifacts: `.scratch/exp-A-*.pdf` … `.scratch/exp-C-*.pdf` (A = two literals, B = literal+hex, C = two hex; `-2` = after re-save).

- `doc.xref_set_key(-1, "ID", ...)` / `doc.xref_get_key(-1, "ID")` operate on the trailer (xref `-1`).
- `/ID` is **not encrypted**: readable with no password on an AES-256 file (`fitz.open(path)` then `xref_get_key(-1, "ID")`).
- A literal ID[0] round-trips **byte-for-byte** through encrypted save and re-save. Raw trailer after re-save: `/ID[(LLMPROOF-f66fbc1333121d9b50ed64a4e8cc04a8)<8FF36D3E506326F95BCD86C9D7FEA758>]`.
- PyMuPDF **preserves `/ID[0]` across every save** and recomputes `/ID[1]` (16-byte **uppercase** hex) — the seed therefore survives pipeline re-saves.
- PyMuPDF **uppercases hex strings** in `/ID` but leaves **literal strings untouched** (case preserved).
- Quirk to avoid: setting `/ID` as `[<hex>(literal)]` (hex first, literal second) saved as a 3-element array `[<hex><recomputed>null]`. A literal at ID[0] is clean; never put a literal at ID[1]. Setting both elements to the same literal is the verified-safe write.
- The Info/metadata dictionary **is** encrypted (`EncryptMetadata true`) — not a viable clear channel.
- `.scratch/proto.py` is a working end-to-end prototype of the _mechanism_ (random seed, unmarked hex ID, re-derive from protected file + salt, `authenticate()` success, wrong-salt failure, canary extraction after unlock, re-save survival). The final design replaces the random/unmarked ID with the deterministic marked literal; the prototype's flow (open → ID → derive → authenticate) is the shape of the new `password_cmd`.

## 5. Target design (per file)

### `src/llm_proof/seed.py` (new; delete `identity.py`)

```python
"""Canonical content extraction, seed derivation, and marker handling."""

MARKER_DEFAULT = "LLMPROOF"
MARKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

def extract_canonical_content(doc) -> str: ...          # moved unchanged from identity.py
def derive_seed(canonical_content: str) -> str: ...     # sha256(...).digest()[:16].hex()
def validate_marker(marker: str) -> None: ...           # raise ValueError, user-friendly msg
def seed_literal(marker: str, seed: str) -> str: ...    # f"({marker}-{seed})"
def parse_seed(id_value: str, marker: str) -> str | None: ...
```

`parse_seed` receives the raw value string from `xref_get_key(-1, "ID")` (e.g.
`'[(LLMPROOF-f66f…cc04a8)<8FF36D3E…>]'`) and returns the lowercase 32-hex seed or `None`:

1. First element: literal via `re.match(r"\[\(([^)]*)\)", id_value)`, else hex via `re.match(r"\[<([^>]*)>", id_value)` (hex first element → return `None`), else malformed → `None`.
2. `prefix = f"{marker}-"`; `first.startswith(prefix)` required, else `None`.
3. `rest = first[len(prefix):]`; `re.fullmatch(r"[0-9a-fA-F]{32}", rest)` required, else `None`; return `rest.lower()`.

The marker-charset error message, e.g. for `(bad`:
`invalid marker "(bad": must start with a letter or digit and contain only letters, digits, dashes and underscores`.

### `src/llm_proof/config.py`

- Extract a shared loader: `load_config(path: str) -> dict` (returns `{}` when file missing or unparseable — mirrors today's `load_salt_from_file` behaviour).
- `get_salt` keeps its exact behaviour (flag > `LLM_PROOF_SALT` env > `salt` key; `None` when absent).
- New: `get_marker(flag_value: str | None = None) -> str` — flag > `marker` config key > `MARKER_DEFAULT`; then `validate_marker` on the resolved value (a bad _config-file_ marker must also fail clearly).

### `src/llm_proof/protect.py`

`protect_pdf(input_path, output_path, salt, canaries_file=None, marker=MARKER_DEFAULT) -> (path, inserted, password)`:

1. Open; `needs_pass` → `ValueError("Input PDF is already password-protected.")` (unchanged).
2. `canonical = extract_canonical_content(doc)` — **before** canary insertion.
3. `seed = derive_seed(canonical)`; `password = derive_password(salt, seed)`.
4. `doc.xref_set_key(-1, "ID", f"[{seed_literal(marker, seed)}{seed_literal(marker, seed)}]")` (both elements the same literal — the verified-safe write).
5. Insert canaries if `canaries_file` given (existing logic unchanged).
6. Save AES-256, `user_pw = owner_pw = password` (existing call, keep the `# pyright: ignore` comment).

### `src/llm_proof/password_cmd.py` (rewritten)

```python
def get_password(input_path: str, salt: str, marker: str = MARKER_DEFAULT) -> str:
    doc = fitz.open(input_path)
    try:
        if not doc.needs_pass:
            raise ValueError("not a password-protected PDF")
        _t, id_value = doc.xref_get_key(-1, "ID")
        seed = parse_seed(id_value, marker)
        if seed is None:
            raise ValueError(
                f'no "{marker}" seed in the PDF\'s file ID: '
                "the file was not created by llm-proof protect, "
                "or it was protected with a different marker"
            )
        return derive_password(salt, seed)
    finally:
        doc.close()
```

No `authenticate()` call (decision 7). No canary logic.

### `src/llm_proof/cli.py`

- `protect` subparser: add `--marker` (help: `Marker label written into the PDF's file ID (default: LLMPROOF; overrides config)`).
- `password` subparser: **remove `--canaries`**; add `--marker` (same help).
- After the salt resolution at the top of `main()` (salt error keeps precedence), resolve the marker with explicit error handling (this code is outside the per-command try/except, so it needs its own):

```python
try:
    marker = get_marker(args.marker)
except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```

- `password` invocation becomes `get_password(args.input, salt, marker)`; `protect` passes `marker=marker`. Print behaviour unchanged (`password` prints the bare password; `protect` prints its three existing lines).

### `tests/test_core.py` (rewrite; keep the canary tests)

Keep as-is: `test_canary_spec_parsing`, `test_canary_placement_directive`, `test_free_text_annotation_exclusion`, and canary insertion/extractability (repoint imports to `llm_proof.seed`).

Replace/add (use the existing `sample_pdf`/`canary_spec` fixtures; build PDFs with the PyMuPDF API only):

1. `test_protect_creates_encrypted_pdf` — unchanged except imports.
2. `test_password_re_derivation_from_protected_file` — protect (with canaries) → `get_password(protected, salt)` with **no** canary argument → matches the password `protect_pdf` returned → `fitz.open(protected).authenticate(password) != 0`.
3. `test_determinism` — protect the same plain file twice (same salt) → identical passwords; and the ID literal equals `LLMPROOF-` + `sha256(extract_canonical_content(plain_doc).encode()).digest()[:16].hex()`, read back via `xref_get_key(-1, "ID")`.
4. `test_canary_independence` — protect the same plain file with two different canary specs (and once with none) → all three passwords identical; canaries still extractable from the unlocked protected file.
5. `test_password_rejects_unencrypted` — `get_password(sample_pdf, salt)` → `pytest.raises(ValueError, match="not a password-protected PDF")`.
6. `test_password_rejects_foreign_protected` — build a PDF with PyMuPDF, set a plain hex `/ID` (e.g. `[<00112233445566778899aabbccddeeff>...]`), save AES-256 with an arbitrary password → `get_password` → `ValueError` matching `no "LLMPROOF" seed`.
7. `test_custom_marker` — `protect_pdf(..., marker="ACME")` → raw file bytes contain `b"(ACME-`; `get_password(protected, salt, "ACME")` works; `get_password(protected, salt)` (default marker) → `ValueError` matching `no "LLMPROOF" seed`.
8. `test_marker_validation` — `validate_marker` (or `get_marker` with explicit bad values) rejects `(bad`, `a b`, `-dash`, empty-string-adjacent cases with the charset message.
9. `test_seed_shape` — `derive_seed` returns 32 lowercase hex chars for non-empty input.

### `README.md`

- **How it works** — rewrite: canonical content → seed (16-byte sha256, 32 hex) → carried under the marker in the PDF's file ID → password = `sha256(salt ‖ seed)[:24]`. Canaries no longer affect the password (they are attribution only). The seed is public; the salt is the sole secret.
- **Salt configuration** — add a **Marker** subsection: `--marker` flag, `marker` key in `config.toml`, default `LLMPROOF`, charset `[A-Za-z0-9][A-Za-z0-9_-]*`, case-sensitive, held like the salt (a file protected under one marker re-derives only under the same one).
- **Re-deriving the password** — new usage `llm-proof password report.protected.pdf` (no `--canaries`); note a wrong salt/marker yields a password that simply won't open the file (no verification is performed); note the two distinct error cases for unrecognised files.
- **Threat model** — add: the seed travels with the document in the clear; a wrong salt is undetectable until someone tries to open the file.
- **Examples** — update the re-derive example (drop `--canaries`).
- **Limitations** — a PyMuPDF pin bump is a breaking change (canonical content → seed); re-saving a protected file does not change its password.

## 6. Out of scope (explicitly rejected)

- Backward compatibility with the old (canonical+canaries) scheme — none of those files exist.
- Randomising canary placement (future work; the design already anticipates it — the seed is computed before insertion).
- An env var for the marker; marker versioning.
- Authentication/verification inside `password`.
- Accepting hex-encoded IDs or foreign/unknown markers.
- Any change to `canaries.py` or the canary spec format.

## 7. Environment & pitfalls

- Run code with `.venv/bin/python` (or `uv run`). If uv needs to resolve anything in a sandboxed shell: prefix `UV_CACHE_DIR=/tmp/uvcache` (the uv cache dir is read-only). **Do not add dependencies**; `uv.lock` stays untouched.
- PyMuPDF module is `pymupdf` (import `pymupdf as fitz`); it is untyped — existing code carries `# pyright: ignore[...]` comments on `fitz` calls; follow the pattern (`pyrightconfig.json` is active).
- **Do not hand-write PDF bytes** in code or tests — use the PyMuPDF API. (pikepdf exists in the venv as a dev scratch tool; do not import it or add it to `pyproject.toml`.)
- `/tmp` is cleared between terminal invocations — put any manual fixtures under `.scratch/` or use pytest `tmp_path`.
- PyMuPDF uppercases hex in `/ID` → parsing must be case-insensitive (canonicalise to lowercase). Literals are preserved as-is.
- Never put a literal string at `/ID[1]` (the 3-element `null` quirk); set both elements to the same literal.
- `xref_set_key`/`xref_get_key` take xref `-1` for trailer keys.
- Tests: `.venv/bin/python -m pytest tests/ -v`.
- Worth reading before implementing: `.scratch/proto.py` (end-to-end mechanism prototype), `.scratch/id-literal.py` + `.scratch/exp-*.pdf` (marker round-trip evidence), `docs/adr/0005-*.md`, `CONTEXT.md` (glossary: Seed, Marker, Canonical content, Salt, Derived password).

## 8. Definition of done

- `.venv/bin/python -m pytest tests/ -v` green; `identity.py` deleted, no remaining references to `derive_identity` or the old `password <plain> --canaries` flow (grep to confirm).
- Manual CLI check (repo-root fixtures):
  - `llm-proof protect test.pdf --canaries canaries.txt --salt dev-salt -o /tmp/p.pdf` → prints `Password used: <24hex>`;
  - `llm-proof password /tmp/p.pdf --salt dev-salt` → prints exactly that 24-hex string, nothing else on stdout;
  - `llm-proof password test.pdf --salt dev-salt` → exit 1, `Error: not a password-protected PDF`;
  - a foreign AES-256 PDF (any other tool's file, or one built with PyMuPDF and a plain hex ID) → exit 1, the `no "LLMPROOF" seed ...` message;
  - `llm-proof protect test.pdf --marker "bad marker" ...` → exit 1, the charset message;
  - `--help` output reflects the flag changes on both subcommands.
- Docs consistent: README as per §5, ADR-0005 in place, ADR-0003 marked superseded (both already done — verify only).

## 9. Tickets

Work in number order (02 and 03 both touch `cli.py`, in separate regions):

- `issues/01-seed-module-and-marker-config.md`
- `issues/02-protect-pipeline.md`
- `issues/03-password-command.md`
- `issues/04-tests.md`
- `issues/05-readme.md`
