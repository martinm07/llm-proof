# Threat model: deliberate obscurity

`llm-proof` exists to stop _naive_ ingestion — a person dumping a PDF into an LLM — not to stop a determined attacker. The password (AES-256) is the gate: anyone with the password, or a workaround such as print-to-PDF, gets the content; the canaries then identify who leaked it.

## Consequences

- Being defeated by page reorder/delete/duplicate, redaction, and print-to-PDF is explicitly accepted.
- The tool creates protected documents only: no ToS enforcement, no password-retrieval service. The canaries are the enforcement/attribution mechanism.
