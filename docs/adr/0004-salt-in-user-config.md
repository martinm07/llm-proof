# Salt is read from the user's per-user config

The salt — the user-held secret outside the document, mixed into password derivation — is read by default from the platform config directory (e.g. `~/.config/llm-proof/` on Linux, `%APPDATA%\llm-proof\` on Windows), overridable via environment and CLI. Chosen for convenience: the user should not have to supply the secret on every invocation of either `protect` or `password`.

## Consequences

- A secret at rest on the user's own machine. Acceptable under the deliberate-obscurity threat model (ADR-0001): the salt defends against third parties, not against the user's own machine.
- Both `protect` and `password` require a salt; neither works without one.
