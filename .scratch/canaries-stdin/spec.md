# Spec: interactive canary entry for `llm-proof protect`

Status: done
Design: agreed 2026-11-18 — see ADR-0009 (accepted)

## 1. Goal

Canaries can be entered directly at the prompt during a `protect` run, without staging a canary spec file on disk. `--canaries` becomes a value-less flag that reads the canary spec from stdin; `--canaries-file` is the flag for the file form.

User story:

```bash
llm-proof protect report.pdf --canaries
# Enter canaries (one per ---separated block). End with Ctrl+D.
# Alice's canary text
# ---
# page: 7
# Bob's canary text
# <Ctrl+D>
Protected: report.protected.pdf
Canaries inserted: 2
Password used: ...
```

Acceptance:

- `--canaries` (short `-c`) takes no value, reads the canary spec from stdin until EOF, and parses it with the standard spec format (`---`-separated blocks, optional placement directives).
- `--canaries-file` takes a path to a canary spec file and behaves as today's `--canaries`.
- Before reading stdin, the entry instruction is printed to stderr — and only when stdin is a TTY (`sys.stdin.isatty()`): `Ctrl+D` on Linux/macOS, `Ctrl+Z` followed by `Enter` on Windows (detected via `sys.platform == "win32"`). Piped stdin gets no instruction.
- An empty or whitespace-only spec from stdin exits with a hard error (e.g. `Error: no canaries provided via stdin`).
- Combining `--canaries` and `--canaries-file` is a hard error.
- A run with a missing/invalid salt or marker fails before stdin is consumed.

## 2. Current state (what you are changing)

- `src/llm_proof/cli.py` — argparse; `protect` has `--canaries`/`-c` taking a file path; `protect_pdf` is called with `args.canaries`.
- `src/llm_proof/protect.py` — `protect_pdf(input_path, output_path, salt, canaries_file, marker)` opens the canaries file itself, then calls `parse_canary_spec`.
- `src/llm_proof/canaries.py` — `parse_canary_spec(spec_text)` already takes text; unchanged.
- `tests/test_core.py` — existing CLI/protect coverage to extend.

## 3. Design decisions (agreed — do not revisit)

1. **Flag layout**: `--canaries` (short `-c`) is value-less and reads the spec from stdin; `--canaries-file` takes a path. (ADR-0009)
2. **No value-optional flag**: a `nargs="?"` form was rejected — with it, `llm-proof protect --canaries input.pdf` silently consumes the positional `input` as the flag's value. (ADR-0009)
3. **Instruction**: one line to stderr before reading stdin, gated on `sys.stdin.isatty()`, platform-specific EOF key. (ADR-0009)
4. **Empty stdin**: whitespace-only spec is a hard error. (ADR-0009)
5. **Conflict**: `--canaries` + `--canaries-file` is a hard error. (ADR-0009)
6. **Seam**: the CLI owns source acquisition (reads the file, or `sys.stdin.read()`) and passes the spec _text_ to `protect_pdf`, whose signature changes from `canaries_file: str | None` to `canaries: str | None`. Salt/marker validation already precedes the `protect_pdf` call, so stdin is never consumed by a failing run.
7. **Glossary**: "Canary spec" is the text; "Canary spec file" is the carrier read by `--canaries-file`. `CONTEXT.md` is already updated.

## 4. Files

- `src/llm_proof/cli.py` — flag layout, stdin read, TTY-gated instruction, conflict + empty-spec handling.
- `src/llm_proof/protect.py` — `protect_pdf` takes spec text.
- `tests/test_core.py` — coverage for stdin path, TTY suppression, empty-spec error, flag conflict.
- `README.md` — usage and examples for both flag forms.
- `docs/adr/0009-canaries-via-stdin.md` — done.
- `CONTEXT.md` — done.
