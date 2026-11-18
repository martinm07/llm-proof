# Self-update targets the release build; integrity is TLS-only

The installed single-file executable updates itself by downloading the matching release artifact from the project's GitHub Releases and swapping it into place. Integrity of the downloaded bytes relies on **TLS alone** — no signing, checksum, or third-party verifier (packslip was evaluated and rejected). The TLS trust store is pinned to `certifi` (a data-only dependency: a bundle of CA certificates), so verification works even on systems where the bundled Python cannot find the system CA store.

Chosen so the updater stays a minimal part of the existing bundle: no key material to distribute, and no trust anchor a user must provision. GitHub Releases over HTTPS is the same surface users already download from manually.

## Consequences

- A compromised GitHub (or a MITM that defeats TLS) could ship a poisoned binary. Accepted under the deliberate-obscurity threat model (ADR-0001): this tool defends against naive ingestion, not a determined attacker with a network position.
- `certifi` is a runtime dependency (added in 0.3.1) but is data only — no TLS logic. It guarantees a CA store is present in the bundle, so the updater does not depend on the host's certificate-store state.
- Adding signing later is additive: newer updaters can verify a signature while older ones ignore it, so the channel need not change.
- The update protocol (asset names `llm-proof-{os}-{arch}`, the `releases/latest` endpoint, the swap mechanic) is baked into every shipped binary; changing it later only affects versions released after the change.
- Only the frozen (single-file) build self-updates. Source / `uv tool` installs are updated manually (`uv tool install --force llm-proof`).
