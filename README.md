⚠ DISCLAIMER: This project (including the below README) was created using LLMs (specifically Qwen3.8 27B).

# llm-proof

Turn a plain PDF into a protected document: password-protected so naive LLM ingestion fails, and carrying canaries so unauthorised extraction can be identified.

## How it works

`llm-proof` derives a per-document **seed** from the document's content, carries it in the PDF's file ID under a **marker**, and derives a password from the seed and a user-held salt. The resulting PDF is AES-256 encrypted with that password, and invisible canary text is embedded throughout. If someone dumps the document into an LLM, the canaries identify who leaked it.

- **Canonical content**: The document's body text in reading order, whitespace-normalised, excluding text inside FreeText annotation boxes (so annotations don't change the password).
- **Seed**: The first 16 bytes of `sha256(canonical content)`, as 32 lowercase hex characters. It is carried in the protected PDF's (unencrypted) file ID, prefixed by the marker: `(LLMPROOF-<seed>)`. The seed is public — anyone holding the file can read it — and it identifies the document.
- **Derived password**: `sha256(salt ‖ seed)` truncated to 24 lowercase hex characters.
- **Canaries**: User-supplied text (from a canary spec file) planted invisibly as white text throughout the document. Canaries do not contribute to the password; they exist purely for attribution.

The salt is the sole secret. Because the seed travels with the document, the password is re-derivable from the protected file and the salt alone — no original document, no canaries file, nothing to store.

## Threat model

`llm-proof` is designed to stop **naive** LLM ingestion (someone dumping a PDF into a chat window). It is **not** a cryptographic security system. A determined attacker can recover the password or bypass it (e.g. print-to-PDF).

The seed travels with the document in the clear, in the file ID. That is deliberate: it makes the password recoverable without storing it. It also means a wrong salt (or marker) produces a password that simply won't open the file — llm-proof never verifies a derived password, so a wrong salt is undetectable until someone tries to open the document.

Canaries are the enforcement mechanism: they make it possible to identify who leaked the content, even if the password protection is defeated.

See [CONTEXT.md](CONTEXT.md) for the complete terminology and [docs/adr/](docs/adr/) for design decisions.

## Installation

Requires Python 3.13+. Uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone and install dependencies
git clone <repo>
cd llm_proof_pdf
uv sync

# Or install the CLI tool globally
uv tool install .
```

## Usage

### Salt configuration

A user-held salt is required for both `protect` and `password`. The salt can be provided in three ways (highest priority first):

1. **CLI flag**: `--salt "my-secret-salt"`
2. **Environment variable**: `LLM_PROOF_SALT=my-secret-salt`
3. **Config file**: `~/.config/llm-proof/config.toml` (Linux), `%APPDATA%\llm-proof\config.toml` (Windows), or `~/Library/Application Support/llm-proof/config.toml` (macOS):
   ```toml
   salt = "my-secret-salt"
   ```

Generate a strong salt with:

```bash
openssl rand -hex 32
# or
python -c "import secrets; print(secrets.token_hex(32))"
```

### Marker

The **marker** is the label prefixing the seed in the PDF's file ID, so llm-proof can find the seed again when re-deriving the password. It can be provided in two ways (highest priority first):

1. **CLI flag**: `--marker "ACME"`
2. **Config file**: `marker = "ACME"` in the same `config.toml` as the salt

The default is `LLMPROOF`. A valid marker starts with a letter or digit and contains only letters, digits, dashes and underscores (`[A-Za-z0-9][A-Za-z0-9_-]*`). Markers are case-sensitive.

Like the salt, the marker is held by the user and never stored by llm-proof: a file protected under one marker re-derives only under the same marker.

### Protecting a PDF

```bash
llm-proof protect input.pdf -o output.pdf
```

With canaries:

```bash
llm-proof protect input.pdf --canaries canaries.txt -o output.pdf
```

If `-o` is omitted, the output is written to `<input-stem>.protected.pdf` (with an incremental suffix if that already exists).

### Canary spec format

The canary spec file uses `---` separators between canary blocks. Directives go on the separator line **before** the canary they apply to (front-matter style):

```
Default canary goes to round-robin.
--- page: 7
This canary goes specifically to page 7.
---
Back to round-robin for this one.
```

**Placement options:**

- No directive: canary is round-robined across pages starting from page 1
- `page: N`: canary is placed on page N (1-indexed)

Canaries are inserted as invisible white text at sentence/paragraph boundaries, evenly distributed across the page.

### Re-deriving the password

```bash
llm-proof password report.protected.pdf
```

This prints only the 24-character password to stdout. The marked seed is read from the protected PDF's file ID and combined with your salt — no original document or canaries file is needed. Use the same salt and marker as when the document was protected.

llm-proof does not verify the password it derives: a wrong salt or marker simply yields a password that won't open the file. If the file cannot be used for re-derivation at all, two distinct errors are reported:

- The file is not password-protected: `Error: not a password-protected PDF`
- The file is protected but its file ID carries no seed under the expected marker: `Error: no "LLMPROOF" seed in the PDF's file ID: the file was not created by llm-proof protect, or it was protected with a different marker`

## Examples

```bash
# Protect without canaries (password only)
llm-proof protect report.pdf -o report-protected.pdf

# Protect with canaries
llm-proof protect report.pdf --canaries recipient-canaries.txt -o report-protected.pdf

# Re-derive the password from the protected file
llm-proof password report-protected.pdf
```

## Limitations

- Annotations change the PDF file but should not change the password (FreeText annotation text is excluded from canonical content).
- The password is stable across annotation round-trips.
- Canaries are invisible to the reader but are extractable via text extraction (the whole point).
- Bumping the pinned PyMuPDF version is a breaking change: the seed is derived from PyMuPDF's text extraction, so a different extraction result at protect-time yields a different password.
- Re-saving a protected file (with its password) does not change its password: the seed travels in the file ID and is not recomputed from the content, so as long as the file ID survives the re-save, the same password is re-derived.

## Development

```bash
# Run the CLI from source
uv run llm-proof help

# Add a new dependency
uv add <package>
```
