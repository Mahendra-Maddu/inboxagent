#!/usr/bin/env python3
"""inboxHero entry point — run capabilities via --cap."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path when run as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inboxhero.caps import CAP_RUNNERS  # noqa: E402
from inboxhero.store import MailStore  # noqa: E402
from inboxhero.trace import Trace  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="inboxHero — agentic inbox triage")
    parser.add_argument(
        "--cap",
        choices=sorted(CAP_RUNNERS.keys()),
        help="Run a single capability (R1–R6, X1–X4)",
    )
    parser.add_argument("--all", action="store_true", help="Run all capabilities in order")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Suppress irreversible actions (default: on)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Allow irreversible actions (still needs --approve for prompts)",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Interactive y/n approval for each irreversible action",
    )
    parser.add_argument("--msg", default="m008", help="Message id for R2")
    parser.add_argument("--from", dest="sender", default="priya@paperjet.io", help="Sender for X1")
    parser.add_argument("--fresh-trace", action="store_true", help="Wipe trace.jsonl before run")
    args = parser.parse_args(argv)

    if not args.cap and not args.all:
        parser.print_help()
        return 2

    dry_run = not args.no_dry_run
    store = MailStore()
    trace = Trace()
    if args.fresh_trace:
        trace.clear()

    caps = list(CAP_RUNNERS.keys()) if args.all else [args.cap]
    # Stable order
    order = ["R1", "R2", "R3", "R4", "R5", "R6", "X1", "X2", "X3", "X4"]
    caps = [c for c in order if c in caps]

    rc = 0
    for cap in caps:
        print(f"\n######## {cap} ########")
        runner = CAP_RUNNERS[cap]
        # R4 is intentionally two-process; when --all, run phase1 then phase2 in-process
        # by calling twice if needed would break the "exit" demo — for --all we
        # simulate: store prefs then apply in the same call sequence.
        if cap == "R4" and args.all:
            from inboxhero.memory import PreferenceStore

            PreferenceStore().clear()
            rc |= runner(store, trace, dry_run=dry_run, interactive=args.approve, msg=args.msg, sender=args.sender)
            # second pass
            print("\n######## R4 (pass 2 — fresh PreferenceStore load) ########")
            rc |= runner(store, trace, dry_run=dry_run, interactive=args.approve, msg=args.msg, sender=args.sender)
        else:
            rc |= runner(
                store,
                trace,
                dry_run=dry_run,
                interactive=args.approve,
                msg=args.msg,
                sender=args.sender,
            )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
