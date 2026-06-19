"""
Operations Dashboard.

Reads only from Supabase views and tables. Has no knowledge of any source
adapter, sync pipeline, or risk engine internals.

When Breezeway replaces the stub, this file does not change.
"""

from __future__ import annotations


import datetime
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich         import box

from db import client as db

console = Console()

_SEVERITY_COLOR = {
    "critical": "bold red",
    "high":     "bold yellow",
    "medium":   "bold cyan",
    "low":      "dim white",
}
_SEVERITY_ICON = {
    "critical": "🔴",
    "high":     "🟡",
    "medium":   "🔵",
    "low":      "⚪",
}
_STATUS_COLOR = {
    "open":      "yellow",
    "discussed": "cyan",
    "actioned":  "green",
    "deferred":  "dim",
    "closed":    "dim",
}


# ---------------------------------------------------------------------------
# Panel 1 — At-Risk Arrivals
# ---------------------------------------------------------------------------

def render_at_risk_arrivals() -> None:
    rows = db.select_view("v_at_risk_arrivals")

    title = Text("AT-RISK ARRIVALS", style="bold red")
    subtitle = "Confirmed reservations arriving in the next 72 hours with open risks"

    if not rows:
        console.print(Panel(
            "[dim]No at-risk arrivals in the next 72 hours.[/dim]",
            title=title, subtitle=subtitle, border_style="red"
        ))
        return

    t = Table(box=box.ROUNDED, show_header=True, header_style="bold",
              border_style="red", min_width=120)
    t.add_column("Sev",         width=4,  no_wrap=True)
    t.add_column("Property",    width=32, no_wrap=True)
    t.add_column("Guest",       width=18)
    t.add_column("Check-in",    width=12)
    t.add_column("Risk",        width=30)
    t.add_column("Action",      width=36)

    for r in rows:
        sev   = r.get("severity", "low")
        icon  = _SEVERITY_ICON.get(sev, "⚪")
        color = _SEVERITY_COLOR.get(sev, "white")
        t.add_row(
            f"[{color}]{icon}[/{color}]",
            _trunc(r.get("property_name") or r.get("street", "?"), 32),
            _trunc(r.get("guest_name") or "—", 18),
            str(r.get("checkin_date") or "—"),
            f"[{color}]{_trunc(r.get('risk_title',''), 30)}[/{color}]",
            _trunc(r.get("recommendation") or "—", 36),
        )

    console.print(Panel(t, title=title, subtitle=f"{len(rows)} active risks", border_style="red"))


# ---------------------------------------------------------------------------
# Panel 2 — Stale Tasks
# ---------------------------------------------------------------------------

def render_stale_tasks() -> None:
    rows = db.select_view("v_stale_tasks")

    title    = Text("STALE TASKS", style="bold yellow")
    subtitle = "Overdue, stale, or arrival-blocking tasks requiring immediate attention"

    if not rows:
        console.print(Panel(
            "[dim]No stale or overdue tasks.[/dim]",
            title=title, subtitle=subtitle, border_style="yellow"
        ))
        return

    t = Table(box=box.ROUNDED, show_header=True, header_style="bold",
              border_style="yellow", min_width=120)
    t.add_column("🚨",          width=4, no_wrap=True)
    t.add_column("Property",    width=28, no_wrap=True)
    t.add_column("Task",        width=30)
    t.add_column("Dept",        width=12)
    t.add_column("Priority",    width=8)
    t.add_column("Scheduled",   width=12)
    t.add_column("Assignees",   width=20)
    t.add_column("Status",      width=10)

    for r in rows:
        flags = []
        if r.get("blocks_arrival"):
            flags.append("[bold red]BLOCKS[/bold red]")
        if r.get("is_overdue"):
            flags.append("[yellow]OVERDUE[/yellow]")
        if r.get("is_stale"):
            flags.append("[cyan]STALE[/cyan]")

        assignees = r.get("assignees") or []
        if isinstance(assignees, list):
            assignee_str = ", ".join(assignees) if assignees else "[dim]Unassigned[/dim]"
        else:
            assignee_str = str(assignees)

        t.add_row(
            " ".join(flags) or "—",
            _trunc(r.get("property_name") or r.get("street", "?"), 28),
            _trunc(r.get("task_name", "?"), 30),
            r.get("department", "?"),
            _priority_label(r.get("priority")),
            str(r.get("scheduled_date") or "—"),
            _trunc(assignee_str, 20),
            r.get("status", "?"),
        )

    console.print(Panel(t, title=title, subtitle=f"{len(rows)} tasks", border_style="yellow"))


# ---------------------------------------------------------------------------
# Panel 3 — Quick Wins
# ---------------------------------------------------------------------------

def render_quick_wins() -> None:
    rows = db.select_view("v_quick_wins")

    title    = Text("QUICK WINS", style="bold green")
    subtitle = "Low-effort tasks that can be closed this week"

    if not rows:
        console.print(Panel(
            "[dim]No quick wins identified.[/dim]",
            title=title, subtitle=subtitle, border_style="green"
        ))
        return

    t = Table(box=box.ROUNDED, show_header=True, header_style="bold",
              border_style="green", min_width=100)
    t.add_column("Property",   width=30, no_wrap=True)
    t.add_column("Task",       width=34)
    t.add_column("Dept",       width=12)
    t.add_column("Est. hrs",   width=8)
    t.add_column("Scheduled",  width=12)
    t.add_column("Assignees",  width=20)

    for r in rows:
        assignees    = r.get("assignees") or []
        assignee_str = ", ".join(assignees) if assignees else "[dim]Unassigned[/dim]"
        est          = r.get("estimated_hours")
        t.add_row(
            _trunc(r.get("property_name") or r.get("street", "?"), 30),
            _trunc(r.get("task_name", "?"), 34),
            r.get("department", "?"),
            f"{est:.1f}h" if est else "—",
            str(r.get("scheduled_date") or "—"),
            _trunc(assignee_str, 20),
        )

    console.print(Panel(t, title=title, subtitle=f"{len(rows)} tasks", border_style="green"))


# ---------------------------------------------------------------------------
# Panel 4 — Thursday Call Intelligence
# ---------------------------------------------------------------------------

def render_thursday_call() -> None:
    rows = db.select_view("v_thursday_call")

    thursday = _next_thursday()
    title    = Text(f"THURSDAY CALL — {thursday}", style="bold magenta")
    subtitle = "Auto-generated + curated items for leadership review"

    if not rows:
        console.print(Panel(
            "[dim]No items for this Thursday's call yet.[/dim]\n"
            "[dim]Run the risk engine to auto-generate items.[/dim]",
            title=title, subtitle=subtitle, border_style="magenta"
        ))
        return

    t = Table(box=box.ROUNDED, show_header=True, header_style="bold",
              border_style="magenta", min_width=130)
    t.add_column("#",           width=3)
    t.add_column("Category",    width=18)
    t.add_column("Title",       width=40)
    t.add_column("Summary",     width=36)
    t.add_column("Action",      width=28)
    t.add_column("Status",      width=10)
    t.add_column("Source",      width=8)

    for i, r in enumerate(rows, 1):
        status    = r.get("status", "open")
        status_c  = _STATUS_COLOR.get(status, "white")
        category  = r.get("category", "general")
        cat_c     = _category_color(category)

        t.add_row(
            str(i),
            f"[{cat_c}]{category.replace('_', ' ').title()}[/{cat_c}]",
            _trunc(r.get("title", "?"), 40),
            _trunc(r.get("summary") or "—", 36),
            _trunc(r.get("recommendation") or "—", 28),
            f"[{status_c}]{status}[/{status_c}]",
            r.get("source", "?")[:6],
        )

    open_count = sum(1 for r in rows if r.get("status") == "open")
    console.print(Panel(t, title=title,
                        subtitle=f"{len(rows)} items — {open_count} open",
                        border_style="magenta"))


# ---------------------------------------------------------------------------
# Portfolio health summary (property-level alerts, no reservation needed)
# ---------------------------------------------------------------------------

def render_portfolio_health() -> None:
    """Show a concise summary of property-level data quality and compliance."""
    dq_rows   = db.select_view("v_property_data_quality")
    all_risks = db.select("operational_risks", {"is_active": True})

    # Property-level risk counts (no reservation linked)
    prop_risks = [r for r in all_risks if not r.get("reservation_id")]
    risk_summary: dict[str, int] = {}
    for r in prop_risks:
        risk_summary[r["risk_type"]] = risk_summary.get(r["risk_type"], 0) + 1

    # Data quality
    no_wifi    = sum(1 for p in dq_rows if not p.get("dq_has_structured_wifi"))
    no_code    = sum(1 for p in dq_rows if not p.get("dq_has_structured_door_code"))
    no_parking = sum(1 for p in dq_rows if not p.get("dq_has_parking_details"))
    expired    = sum(1 for p in dq_rows if p.get("str_license_expired"))
    expiring   = sum(1 for p in dq_rows if p.get("str_license_expiring_soon"))
    low_score  = sum(1 for p in dq_rows if (p.get("dq_completeness_score") or 0) < 50)
    total      = len(dq_rows)

    lines = []
    lines.append(f"[bold]Portfolio: {total} properties[/bold]")
    lines.append("")
    lines.append("[bold]Data Quality[/bold]")
    lines.append(f"  {'✗' if no_wifi    else '✓'}  WiFi not on record:             [{_pct_color(no_wifi, total)}]{no_wifi}/{total}[/]")
    lines.append(f"  {'✗' if no_code    else '✓'}  Door code not structured:       [{_pct_color(no_code, total)}]{no_code}/{total}[/]")
    lines.append(f"  {'✗' if no_parking else '✓'}  Parking details missing:        [{_pct_color(no_parking, total)}]{no_parking}/{total}[/]")
    lines.append(f"  {'✗' if low_score  else '✓'}  Completeness score < 50%:       [{_pct_color(low_score, total)}]{low_score}/{total}[/]")
    lines.append("")
    lines.append("[bold]Compliance[/bold]")
    lines.append(f"  {'🔴' if expired  else '✓'}  STR licenses EXPIRED:           [{'bold red' if expired else 'green'}]{expired}[/]")
    lines.append(f"  {'🟡' if expiring else '✓'}  STR licenses expiring < 90d:    [{'yellow' if expiring else 'green'}]{expiring}[/]")
    lines.append("")
    if risk_summary:
        lines.append("[bold]Active Property-Level Alerts[/bold]")
        for rtype, count in sorted(risk_summary.items(), key=lambda x: -x[1]):
            lines.append(f"  {count:3d}  {rtype.replace('_', ' ')}")

    console.print(Panel(
        "\n".join(lines),
        title=Text("PORTFOLIO HEALTH", style="bold blue"),
        border_style="blue",
    ))


# ---------------------------------------------------------------------------
# Full dashboard render
# ---------------------------------------------------------------------------

def render_dashboard() -> None:
    console.rule("[bold white]BEM OPERATIONS INTELLIGENCE CENTER[/bold white]")
    console.print(f"[dim]Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]\n")

    render_at_risk_arrivals()
    console.print()
    render_stale_tasks()
    console.print()
    render_quick_wins()
    console.print()
    render_thursday_call()
    console.print()
    render_portfolio_health()
    console.rule()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trunc(s: str, n: int) -> str:
    if not s:
        return "—"
    s = str(s)
    return s[:n - 1] + "…" if len(s) > n else s


def _priority_label(p: str | None) -> str:
    colors = {"urgent": "bold red", "high": "yellow", "normal": "white", "low": "dim", "watch": "cyan"}
    c = colors.get(p or "normal", "white")
    return f"[{c}]{p or '?'}[/{c}]"


def _category_color(category: str) -> str:
    return {
        "at_risk_arrival":   "red",
        "stale_task":        "yellow",
        "compliance_alert":  "magenta",
        "data_quality_gap":  "cyan",
        "quick_win":         "green",
        "recurring_issue":   "yellow",
        "general":           "white",
    }.get(category, "white")


def _pct_color(count: int, total: int) -> str:
    if total == 0:
        return "white"
    pct = count / total
    if pct > 0.5:
        return "bold red"
    if pct > 0.2:
        return "yellow"
    return "green"


def _next_thursday() -> datetime.date:
    today = datetime.date.today()
    # (3 - weekday) % 7: returns 0 on Thursday (stay today), 1-6 otherwise
    days  = (3 - today.weekday()) % 7
    return today + datetime.timedelta(days=days)
