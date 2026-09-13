"""`python -m study.metabase <command>` — the developer entry for the Metabase
demonstration (9g).

  export            build the gitignored SQLite file Metabase reads (offline;
                    `make publish [ROWS=]` since Phase 10a — the DAG's last task)
  apply             provision the dashboard from config.yaml (developer-run,
                    credentials from the environment, talks to localhost Metabase)
  apply --dry-run   print the request bodies apply would send (offline, no
                    credentials) — the CI-checkable half

Network and credential use is developer-run, never an agent's (CLAUDE.md →
paid/network commands)."""

from __future__ import annotations

import argparse
import sys

from pipeline.build import INPUTS
from pipeline.cli import Refused, _refuse_corpus_on_cloud, resolve_choice
from pipeline.warehouse import LOCAL, WIRED, DriverError, location_for
from study.metabase.apply import (
    Credentials,
    MetabaseError,
    UrllibClient,
    apply,
    dry_run_text,
    load_config,
)
from study.metabase.export import ExportError, build_sqlite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m study.metabase")
    sub = parser.add_subparsers(dest="command", required=True)
    export_parser = sub.add_parser(
        "export", help="build the SQLite file Metabase reads (offline)"
    )
    export_parser.add_argument(
        "--rows",
        default="",
        help="which rebuild input to export (default: captured — the real corpus); "
        "validated against the closed set in Python, so `make publish ROWS=` from "
        "either origin is refused by name, never a shell word",
    )
    export_parser.add_argument(
        "--target",
        default="",
        help="which engine to read the marts from (default: duckdb — the laptop "
        "file); validated against the seam's WIRED set, so `make publish TARGET=` "
        "from either origin is refused by name; a corpus input on the cloud "
        "target is refused (fixture inputs only)",
    )
    apply_parser = sub.add_parser("apply", help="provision the dashboard (config.yaml)")
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the request bodies without a network call or credentials",
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "export":
            rows = resolve_choice(args.rows, INPUTS, "captured")
            target = resolve_choice(args.target, WIRED, LOCAL)
            _refuse_corpus_on_cloud(target, rows)
            path = build_sqlite(target, location_for(target, rows))
            print(f"wrote {path} (from ROWS={rows} on TARGET={target})")
            return 0
        config = load_config()
        if args.dry_run:
            print(dry_run_text(config))
            return 0
        client = UrllibClient(Credentials.from_env())
        ids = apply(config, client)
        print(f"provisioned: {ids}")
        return 0
    except (MetabaseError, ExportError, Refused, DriverError) as error:
        print(f"study.metabase: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
