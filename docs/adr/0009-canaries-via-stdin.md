# Canaries are entered interactively via stdin

Canaries reach `protect` as a canary spec — text, not necessarily a file. `--canaries` (short `-c`) takes no value and reads the spec from stdin; `--canaries-file` takes a path to a canary spec file. Chosen so canaries can be entered directly at the prompt for a one-off protection run, without staging a spec file on disk.

## Considered options

- A value-optional `--canaries` (`nargs="?"`, absent value → stdin) was rejected: with it, `llm-proof protect --canaries input.pdf` parses `input.pdf` as the flag's value and the positional `input` is missing, failing with an unhelpful `the following arguments are required: input` — the flag silently swallows the positional.

## Consequences

- Before reading stdin, an entry instruction is printed to stderr, and only when stdin is a TTY: `Ctrl+D` on Linux/macOS, `Ctrl+Z` followed by `Enter` on Windows (detected via `sys.platform == "win32"`). Piped stdin gets no instruction — the pipe ends at EOF.
- An empty or whitespace-only spec from stdin is a hard error: a run that asked for interactive canaries must not silently produce a document with no canaries.
- Combining `--canaries` with `--canaries-file` is a hard error.
- The CLI owns source acquisition and passes the spec text to `protect_pdf`. Salt and marker validation runs before stdin is consumed, so a failing run never eats interactive input.
