---
status: superseded by ADR-0005
---

# Canaries are part of the document identity

Canonical content — and therefore the derived password — includes the canary text: identity = f(canaries + content). This keeps the identity well-defined both before protection (content plus the canaries from the spec file) and after it (extraction of the protected document, where white canary text is extractable), so `llm-proof password` re-derives the same password from the original file, the same canaries, and the same salt.

## Considered options

- Identity over the original content only: rejected — canary text is extractable from the protected document, so the pre- and post-protection definitions of identity would disagree.
