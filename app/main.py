"""
BEM Operations Intelligence Center — CLI entry point.

Usage:
  python main.py sync       — pull from all sources, write to Supabase
  python main.py risks      — run the risk engine against current DB state
  python main.py dashboard  — render the terminal dashboard
  python main.py run        — full pipeline: sync → risks → dashboard

Environment variables (required):
  HOSTAWAY_CLIENT_ID
  HOSTAWAY_CLIENT_SECRET
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY

Optional:
  RESERVATION_WINDOW_DAYS_BACK    (default: 30)
  RESERVATION_WINDOW_DAYS_FORWARD (default: 90)
  STALE_TASK_THRESHOLD_HOURS      (default: 48)
  AT_RISK_ARRIVAL_WINDOW_HOURS    (default: 72)
  EXPIRING_LICENSE_WARNING_DAYS   (default: 90)
"""

from __future__ import annotations


import argparse
import logging
import sys
import os

# Load .env before any other imports that may read env vars
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bem")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_sync(args) -> None:
    from adapters.hostaway          import HostawayAdapter
    from adapters.breezeway_stub    import BreezewayAdapterStub
    from pipeline.sync              import run_full_sync
    from db                         import client as db

    console.rule("[bold cyan]SYNC[/bold cyan]")
    hostaway  = HostawayAdapter()

    # Pass Hostaway property IDs to the stub so mock tasks link to real properties
    prop_rows = db.select("properties", {})
    ha_ids    = [r["hostaway_id"] for r in prop_rows if r.get("hostaway_id")]
    if not ha_ids:
        log.info("No properties in DB yet — stub will use built-in fallback IDs")

    breezeway = BreezewayAdapterStub(property_hostaway_ids=ha_ids or None)

    results = run_full_sync(hostaway, breezeway)
    console.print("\n[bold green]Sync complete[/bold green]")
    for entity, count in results.items():
        console.print(f"  {entity:<20} {count} records")


def cmd_risks(args) -> None:
    from engine.risk import run_risk_engine

    console.rule("[bold yellow]RISK ENGINE[/bold yellow]")
    summary = run_risk_engine()
    console.print("\n[bold green]Risk engine complete[/bold green]")
    for key, val in summary.items():
        console.print(f"  {key:<30} {val}")


def cmd_dashboard(args) -> None:
    from dashboard.views import render_dashboard
    render_dashboard()


def cmd_run(args) -> None:
    """Full pipeline: sync → risks → dashboard."""
    cmd_sync(args)
    console.print()
    cmd_risks(args)
    console.print()
    cmd_dashboard(args)


def cmd_web(args) -> None:
    import uvicorn
    port = getattr(args, "port", 8000)
    console.print(f"[bold green]Starting BEM Ops web server[/bold green] → [cyan]http://localhost:{port}[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    uvicorn.run(
        "web.server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="warning",
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_REQUIRED_ENV = ["HOSTAWAY_CLIENT_ID", "HOSTAWAY_CLIENT_SECRET",
                 "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]


def _check_env() -> bool:
    missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
    if missing:
        console.print(f"[bold red]Missing required environment variables:[/bold red]")
        for k in missing:
            console.print(f"  [red]{k}[/red]")
        console.print("\nCopy [cyan]app/.env.example[/cyan] to [cyan]app/.env[/cyan] and fill in values.")
        return False
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bem",
        description="BEM Operations Intelligence Center",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync",      help="Pull from Hostaway + Breezeway, write to Supabase")
    sub.add_parser("risks",     help="Run risk engine against current Supabase state")
    sub.add_parser("dashboard", help="Render the terminal operations dashboard")
    sub.add_parser("run",       help="Full pipeline: sync → risks → dashboard")

    web_p = sub.add_parser("web", help="Start the browser-based operations dashboard")
    web_p.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")

    args = parser.parse_args()

    # Dashboard and web don't need Hostaway creds — they only read from Supabase
    if args.command not in ("dashboard", "web") and not _check_env():
        sys.exit(1)

    dispatch = {
        "sync":      cmd_sync,
        "risks":     cmd_risks,
        "dashboard": cmd_dashboard,
        "run":       cmd_run,
        "web":       cmd_web,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
