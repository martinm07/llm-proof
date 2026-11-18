"""CLI interface for llm-proof."""

import argparse
import os
import sys

from .config import get_config_dir, get_marker, get_salt, get_url_template
from .password_cmd import get_password
from .protect import protect_pdf
from .update import check_for_update, notice_for, perform_update
from .version import get_version


def _run_update(args):
    """Handle the `update` subcommand (perform, or `--check` report-only)."""
    if args.check:
        _, latest = check_for_update(get_config_dir(), force=True)
        current = get_version()
        if latest is None:
            print(
                "Error: could not determine the latest version (offline?).",
                file=sys.stderr,
            )
            sys.exit(1)
        notice = notice_for(current, latest)
        if notice:
            print(notice)
        else:
            print(f"Already up to date ({current}).")
        return

    try:
        print(perform_update())
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 -- top-level CLI catch-all
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def default_output_name(input_path):
    """Generate default output name: input-stem.protected.pdf (increment if exists)."""
    base, ext = os.path.splitext(input_path)
    candidate = f"{base}.protected{ext}"
    counter = 2
    while os.path.exists(candidate):
        candidate = f"{base}-{counter}.protected{ext}"
        counter += 1
    return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-proof", description="Protect PDFs from naive LLM ingestion"
    )
    parser.add_argument(
        "--version", action="version", version=f"llm-proof {get_version()}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # protect subcommand
    protect_parser = subparsers.add_parser(
        "protect", help="Protect a PDF with a derived password and canaries"
    )
    protect_parser.add_argument("input", help="Input PDF path")
    canary_group = protect_parser.add_mutually_exclusive_group()
    canary_group.add_argument(
        "--canaries",
        "-c",
        action="store_true",
        help="Read the canary spec from stdin (interactive entry)",
    )
    canary_group.add_argument(
        "--canaries-file",
        help="Path to canary spec file",
    )
    protect_parser.add_argument(
        "--output", "-o", help="Output PDF path (default: <input>.protected.pdf)"
    )
    protect_parser.add_argument("--salt", help="Salt value (overrides env and config)")
    protect_parser.add_argument(
        "--marker",
        help="Marker label written into the PDF's file ID (default: LLMPROOF; overrides config)",
    )
    protect_parser.add_argument(
        "--url-template",
        help="Template string for automatically generating and printing URLs using the PDF's seed value (substituting <SEED>) when calling `llm-proof protect`.",
    )

    # password subcommand
    password_parser = subparsers.add_parser(
        "password", help="Re-derive the password for a protected PDF"
    )
    password_parser.add_argument("input", help="Protected PDF path")
    password_parser.add_argument("--salt", help="Salt value (overrides env and config)")
    password_parser.add_argument(
        "--marker",
        help="Marker label written into the PDF's file ID (default: LLMPROOF; overrides config)",
    )

    # update subcommand
    update_parser = subparsers.add_parser(
        "update", help="Update llm-proof to the latest release"
    )
    update_parser.add_argument(
        "--check",
        action="store_true",
        help="Only report whether a newer release is available; do not download",
    )

    return parser


def _read_canary_spec(args: argparse.Namespace) -> str | None:
    """Acquire the canary spec text for `protect`.

    `--canaries` reads the spec from stdin, printing an entry instruction
    first when stdin is an interactive terminal; `--canaries-file` reads a
    canary spec file. Returns None when no canaries are requested.
    """
    if args.canaries:
        if sys.stdin.isatty():
            end = (
                "End with Ctrl+Z followed by Enter."
                if sys.platform == "win32"
                else "End with Enter followed by Ctrl+D."
            )
            print(
                f"Enter canaries (one per ---separated block). {end}",
                file=sys.stderr,
            )
        spec_text = sys.stdin.read()
        print("\n")
        if not spec_text.strip():
            raise ValueError("no canaries provided via stdin")
        return spec_text

    if args.canaries_file:
        with open(args.canaries_file, "r") as f:
            return f.read()

    return None


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "update":
        _run_update(args)
        return

    # Auto update-check (TTL-cached, silent on failure); the notice is shown
    # by `protect` only (ADR-0008).
    notice = None
    if args.command in ("protect", "password"):
        notice = check_for_update(get_config_dir())[0]

    # Resolve salt
    salt = get_salt(args.salt)
    if not salt:
        config_dir = get_config_dir()
        print(
            f"Error: No salt found. Provide via --salt flag, LLM_PROOF_SALT env var, "
            f'or {os.path.join(config_dir, "config.toml")} (salt = "...").',
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve marker (after the salt check, which keeps precedence)
    try:
        marker = get_marker(args.marker)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "protect":
        input_path = args.input
        output_path = args.output or default_output_name(input_path)

        try:
            url_template = get_url_template(args.url_template)
            spec_text = _read_canary_spec(args)

            result_path, inserted, password, seed = protect_pdf(
                input_path, output_path, salt, spec_text, marker=marker
            )
            print(f"Protected: {result_path}")
            if inserted > 0:
                print(f"Canaries inserted: {inserted}")
            print("Password used: " + password)

            if url_template:
                print("\nGenerated URL: ", url_template.replace("<SEED>", seed))
            if notice:
                print(notice)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:  # noqa: BLE001 -- top-level CLI catch-all
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "password":
        try:
            password = get_password(args.input, salt, marker)
            print(password)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:  # noqa: BLE001 -- top-level CLI catch-all
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
