"""CLI interface for llm-proof."""

import argparse
import os
import sys

from .config import get_config_dir, get_marker, get_salt, get_url_template
from .password_cmd import get_password
from .protect import protect_pdf


def default_output_name(input_path):
    """Generate default output name: input-stem.protected.pdf (increment if exists)."""
    base, ext = os.path.splitext(input_path)
    candidate = f"{base}.protected{ext}"
    counter = 2
    while os.path.exists(candidate):
        candidate = f"{base}-{counter}.protected{ext}"
        counter += 1
    return candidate


def main():
    parser = argparse.ArgumentParser(
        prog="llm-proof", description="Protect PDFs from naive LLM ingestion"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # protect subcommand
    protect_parser = subparsers.add_parser(
        "protect", help="Protect a PDF with a derived password and canaries"
    )
    protect_parser.add_argument("input", help="Input PDF path")
    protect_parser.add_argument("--canaries", "-c", help="Path to canary spec file")
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

    args = parser.parse_args()

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

            result_path, inserted, password, seed = protect_pdf(
                input_path, output_path, salt, args.canaries, marker=marker
            )
            print(f"Protected: {result_path}")
            if inserted > 0:
                print(f"Canaries inserted: {inserted}")
            print("Password used: " + password)

            if url_template:
                print("\nGenerated URL: ", url_template.replace("<SEED>", seed))
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
