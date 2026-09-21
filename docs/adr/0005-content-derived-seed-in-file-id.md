---
status: accepted
---

# The seed is derived from the document's content and carried in the file ID

`llm-proof password` must recover the lock password from the protected PDF plus the user's salt alone — no original file, no canary spec. The password is therefore not a function of extracted content alone (its inputs sit inside the encryption): `protect` computes a per-document **seed** from the canonical content of the plain document *before* canary insertion, and writes it as a literal string — prefixed by the user-configurable **marker** (default `LLMPROOF`) — into the PDF's unencrypted file ID (`/ID[0]`). The password itself is unchanged in form: `sha256(salt ‖ seed)` truncated to 24 lowercase hex characters.

## Considered options

- **Random per-document seed**: rejected — re-protecting the same document would yield a different password; the design requires the same input to give the same password (deterministic and testable).
- **Storing the password in the clear in the file**: rejected — anyone with the file could then read the password; the salt must remain the sole secret.
- **PDF metadata / Info dictionary**: rejected — it is encrypted with the document (`EncryptMetadata`), so it is not a clear channel.
- **Hex-encoded ID with a magic prefix**: rejected — the marker must be human-readable and user-customisable, which hex cannot carry.

## Consequences

- Canaries no longer affect the password (supersedes ADR-0003): they are inserted *after* the seed is computed and exist purely for leak attribution.
- The seed is public — readable from the file without the password. The salt is the sole secret. A wrong salt yields a wrong password with no way to detect it until someone tries to open the PDF, so `password` deliberately does not authenticate.
- Re-saving the file does not change the password: PyMuPDF preserves `/ID[0]` across saves and recomputes only `/ID[1]`.
- The marker is user state like the salt: a document protected under marker `ACME` re-derives only under `ACME`.
- Bumping the PyMuPDF pin remains a breaking change (ADR-0002): canonical content is the basis of the seed.
