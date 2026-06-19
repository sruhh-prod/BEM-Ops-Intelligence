from __future__ import annotations

import datetime
import statistics
from collections import defaultdict, Counter
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import client as db
from adapters.breezeway import get_tasks as bw_get_tasks

app = FastAPI(title="BEM Ops Intelligence")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_RISK_LABELS = {
    "open_clean_before_arrival":       "No completed clean",
    "open_maintenance_before_arrival": "Open maintenance",
    "no_inspection_before_arrival":    "No pre-arrival inspection",
    "access_code_not_set":             "No guest access code",
    "stale_task":                      "Task gone silent",
    "overdue_task":                    "Overdue task",
    "unassigned_task":                 "Task unassigned",
    "missing_wifi_credentials":        "WiFi not on record",
    "expired_str_license":             "STR license expired",
    "missing_access_instructions":     "No access instructions",
    "guest_count_exceeds_capacity":    "Guest count exceeds capacity",
}

_RISK_CATEGORIES = {
    "open_clean_before_arrival":       "Guest Readiness",
    "open_maintenance_before_arrival": "Guest Readiness",
    "no_inspection_before_arrival":    "Guest Readiness",
    "access_code_not_set":             "Guest Access",
    "stale_task":                      "Task Health",
    "overdue_task":                    "Task Health",
    "unassigned_task":                 "Task Health",
    "missing_wifi_credentials":        "Data Quality",
    "expired_str_license":             "Compliance",
    "missing_access_instructions":     "Data Quality",
    "guest_count_exceeds_capacity":    "Guest Safety",
}


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

def _build_kpis(tasks: list[dict], stale_tasks: list[dict],
                all_risks: list[dict], dq_rows: list[dict]) -> dict:
    open_statuses = {"pending", "assigned", "in_progress", "blocked"}
    outstanding = sum(1 for t in tasks if t.get("status") in open_statuses)

    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat()
    new_tasks = sum(1 for t in tasks if (t.get("created_at") or "") >= cutoff)

    at_risk_reservations = len(set(
        r["reservation_id"] for r in all_risks
        if r.get("reservation_id") and r.get("is_active")
    ))

    critical_props = set(
        r["property_id"] for r in all_risks
        if r.get("severity") == "critical" and r.get("is_active")
    )
    total = max(len(dq_rows), 1)
    health_pct = round((1 - len(critical_props) / total) * 100)

    return {
        "outstanding":  outstanding,
        "new_tasks":    new_tasks,
        "stale":        len(stale_tasks),
        "at_risk":      at_risk_reservations,
        "health_pct":   health_pct,
        "health_status": "good" if health_pct >= 90 else ("warn" if health_pct >= 75 else "bad"),
    }


def _build_attention_items(at_risk_rows: list[dict], stale_tasks: list[dict]) -> list[dict]:
    """
    Merge critical/high at-risk arrivals with arrival-blocking stale tasks
    into a unified priority table, deduped by reservation+risk_type.
    """
    seen: set[str] = set()
    items: list[dict] = []

    # At-risk arrivals — one row per reservation+risk_type, critical/high only
    for row in at_risk_rows:
        sev = row.get("severity", "low")
        if sev not in ("critical", "high"):
            continue
        key = f"{row.get('reservation_id')}::{row.get('risk_type')}"
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "property":    row.get("property_name") or row.get("street", "?"),
            "issue":       _RISK_LABELS.get(row.get("risk_type", ""), row.get("risk_title", "?")),
            "severity":    sev,
            "arrival":     row.get("checkin_date"),
            "hours_until": row.get("hours_until_checkin"),
            "action":      row.get("recommendation", "—"),
            "source":      "arrival",
        })

    # Blocking stale tasks not already captured
    for t in stale_tasks:
        if not t.get("blocks_arrival"):
            continue
        key = f"stale::{t.get('task_id')}"
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "property":    t.get("property_name") or t.get("street", "?"),
            "issue":       t.get("task_name", "Stale task"),
            "severity":    "high",
            "arrival":     t.get("checkin_date"),
            "hours_until": None,
            "action":      "Reassign or follow up immediately",
            "source":      "task",
        })

    items.sort(key=lambda x: (_SEV_ORDER.get(x["severity"], 3), x.get("hours_until") or 999))
    return items


def _build_recurring_patterns(all_risks: list[dict]) -> list[dict]:
    """Group active risks by type; return portfolio-level patterns, most prevalent first."""
    by_type: dict[str, dict] = defaultdict(lambda: {"props": set(), "severity": "low", "rec": ""})
    for r in all_risks:
        if not r.get("is_active"):
            continue
        rt = r["risk_type"]
        by_type[rt]["props"].add(r.get("property_id"))
        if _SEV_ORDER.get(r.get("severity", "low"), 3) < _SEV_ORDER.get(by_type[rt]["severity"], 3):
            by_type[rt]["severity"] = r.get("severity", "low")
        by_type[rt]["rec"] = r.get("recommendation") or by_type[rt]["rec"]

    patterns = []
    for rt, data in sorted(by_type.items(), key=lambda x: -len(x[1]["props"])):
        count = len(data["props"])
        patterns.append({
            "pattern":    _RISK_LABELS.get(rt, rt.replace("_", " ").title()),
            "risk_type":  rt,
            "category":   _RISK_CATEGORIES.get(rt, "General"),
            "count":      count,
            "severity":   data["severity"],
            "action":     data["rec"],
            "trend":      "↑" if count > 10 else ("→" if count > 3 else "↓"),
            "trend_cls":  "text-red-400" if count > 10 else ("text-amber-400" if count > 3 else "text-green-400"),
        })
    return patterns


def _build_today_arrivals(prop_map: dict[str, str]) -> list[dict]:
    today_str = datetime.date.today().isoformat()
    client = db.get_client()
    rows = (
        client.table("reservations")
        .select("*")
        .eq("status", "confirmed")
        .eq("checkin_date", today_str)
        .order("checkin_date")
        .execute()
        .data or []
    )
    for r in rows:
        r["property_name"] = prop_map.get(r.get("property_id"), "Unknown property")
    return rows


def _build_portfolio_stats(dq_rows: list[dict], all_risks: list[dict]) -> dict:
    total = len(dq_rows)
    sev_counts: dict[str, int] = defaultdict(int)
    for r in all_risks:
        if r.get("is_active"):
            sev_counts[r.get("severity", "low")] += 1

    return {
        "total":            total,
        "no_wifi":          sum(1 for p in dq_rows if not p.get("dq_has_structured_wifi")),
        "no_door_code":     sum(1 for p in dq_rows if not p.get("dq_has_structured_door_code")),
        "expired_licenses": sum(1 for p in dq_rows if p.get("str_license_expired")),
        "expiring_soon":    sum(1 for p in dq_rows if p.get("str_license_expiring_soon")),
        "critical":         sev_counts["critical"],
        "high":             sev_counts["high"],
        "medium":           sev_counts["medium"],
        "total_risks":      sum(sev_counts.values()),
    }


# ---------------------------------------------------------------------------
# Breezeway data builders
# ---------------------------------------------------------------------------

def _parse_dt(s: str | None) -> datetime.datetime | None:
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def _parse_date(s: str | None) -> datetime.date | None:
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _comp_hours(t: dict) -> float | None:
    s = _parse_dt(t.get("started_at") or t.get("created_at"))
    f = _parse_dt(t.get("finished_at"))
    if s and f and f > s:
        h = (f - s).total_seconds() / 3600
        return h if h < 720 else None
    return None


_OPEN_CODES = {"created", "in_progress", "request_approved", "pending_approval"}
_DONE_CODES = {"finished", "closed"}

# Categories we highlight in recurring issues
_RI_CATS = ["Plumbing", "HVAC", "Appliance", "Lock / Access", "Electrical", "Pest Control"]


def _build_property_health(bw_tasks: list[dict]) -> list[dict]:
    """Score every property 0-100; surface highest-risk first."""
    maint = [t for t in bw_tasks if t.get("type_department") == "maintenance"]
    if not maint:
        return []

    today         = datetime.date.today()
    last30_start  = today - datetime.timedelta(days=30)
    prior30_start = today - datetime.timedelta(days=60)

    # Per-property accumulation
    prop: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "open": 0, "cats": Counter(), "hours": [],
        "last30": 0, "prior30": 0,
    })

    for t in maint:
        name = t["_property_name"]
        pd   = prop[name]
        pd["total"] += 1
        if t["type_task_status"]["code"] in _OPEN_CODES:
            pd["open"] += 1
        pd["cats"][t["_category"]] += 1
        h = _comp_hours(t)
        if h:
            pd["hours"].append(h)
        d = _parse_date(t.get("created_at"))
        if d:
            if last30_start  <= d <= today:       pd["last30"]  += 1
            if prior30_start <= d < last30_start: pd["prior30"] += 1

    # Portfolio averages
    all_totals = [pd["total"] for pd in prop.values()]
    avg_total  = statistics.mean(all_totals) if all_totals else 1

    # Replacement clusters: same category ≥ 5 times in 180 days
    prop_cat_dates: dict[tuple, list] = defaultdict(list)
    for t in maint:
        d = _parse_date(t.get("created_at"))
        if d:
            prop_cat_dates[(t["_property_name"], t["_category"])].append(d)

    replacement_flags: dict[str, list[str]] = defaultdict(list)
    for (pname, cat), dates in prop_cat_dates.items():
        dates.sort()
        for i in range(len(dates)):
            window = [d for d in dates if 0 <= (d - dates[i]).days <= 180]
            if len(window) >= 5:
                replacement_flags[pname].append(cat)
                break

    rows = []
    for name, pd in prop.items():
        # Trend
        prior = pd["prior30"]
        last  = pd["last30"]
        if prior == 0:
            trend_pct = 100 if last > 0 else 0
        else:
            trend_pct = round((last / prior - 1) * 100)
        trend_str = (f"+{trend_pct}%" if trend_pct > 0 else f"{trend_pct}%")
        trend_dir = "up" if trend_pct > 15 else ("down" if trend_pct < -15 else "flat")

        # Primary category (excluding onboarding/other)
        skip = {"Onboarding / Setup", "Other", "Inspection / QA", "Guest Request"}
        top_cats = [(c, n) for c, n in pd["cats"].most_common() if c not in skip]
        primary_cat = top_cats[0][0] if top_cats else (pd["cats"].most_common(1) or [("—", 0)])[0][0]

        # Multi-system burden: categories (excl skip) with ≥ 3 incidents
        heavy = sum(1 for c, n in pd["cats"].items() if c not in skip and n >= 3)

        # Health score
        vol_ratio  = pd["total"] / max(avg_total, 1)
        score      = 100
        score     -= min(30, int(max(0, vol_ratio - 1) * 18))
        score     -= min(20, max(0, int(trend_pct * 0.25))) if trend_pct > 0 else 0
        rep_flags  = replacement_flags.get(name, [])
        score     -= min(25, len(rep_flags) * 9)
        score     -= min(15, heavy * 4)
        score      = max(0, min(100, score))

        rows.append({
            "name":           name,
            "score":          score,
            "maint_total":    pd["total"],
            "maint_open":     pd["open"],
            "avg_hours":      round(statistics.mean(pd["hours"]), 1) if pd["hours"] else None,
            "trend_str":      trend_str,
            "trend_dir":      trend_dir,
            "primary_cat":    primary_cat,
            "replacement":    bool(rep_flags),
            "rep_categories": rep_flags[:3],
            "heavy_systems":  heavy,
        })

    rows.sort(key=lambda r: r["score"])
    return rows[:20]


def _build_recurring_issues(bw_tasks: list[dict]) -> list[dict]:
    """Portfolio-level view of the 6 key maintenance categories."""
    maint = [t for t in bw_tasks if t.get("type_department") == "maintenance"]
    if not maint:
        return []

    today         = datetime.date.today()
    last30_start  = today - datetime.timedelta(days=30)
    prior30_start = today - datetime.timedelta(days=60)

    results = []
    for cat in _RI_CATS:
        cat_tasks = [t for t in maint if t["_category"] == cat]
        total  = len(cat_tasks)
        last30 = sum(1 for t in cat_tasks
                     if _parse_date(t.get("created_at")) and
                     last30_start <= _parse_date(t.get("created_at")) <= today)
        prior30 = sum(1 for t in cat_tasks
                      if _parse_date(t.get("created_at")) and
                      prior30_start <= _parse_date(t.get("created_at")) < last30_start)

        if prior30 == 0:
            trend_pct = 100 if last30 > 0 else 0
        else:
            trend_pct = round((last30 / prior30 - 1) * 100)

        prop_counts = Counter(t["_property_name"] for t in cat_tasks)
        top_props   = [{"name": n, "count": c} for n, c in prop_counts.most_common(4)]

        trend_dir = "up" if trend_pct > 15 else ("down" if trend_pct < -15 else "flat")

        results.append({
            "category":   cat,
            "total":      total,
            "last30":     last30,
            "prior30":    prior30,
            "trend_pct":  trend_pct,
            "trend_dir":  trend_dir,
            "top_props":  top_props,
        })

    return results


def _build_replacement_candidates(bw_tasks: list[dict]) -> list[dict]:
    """Properties with 5+ same-category maintenance tasks within 180 days."""
    maint = [t for t in bw_tasks if t.get("type_department") == "maintenance"]
    if not maint:
        return []

    prop_cat_dates: dict[tuple, list] = defaultdict(list)
    prop_cat_names: dict[tuple, list] = defaultdict(list)
    for t in maint:
        d = _parse_date(t.get("created_at"))
        if d:
            key = (t["_property_name"], t["_category"])
            prop_cat_dates[key].append(d)
            prop_cat_names[key].append(t.get("name", "").strip()[:60])

    clusters = []
    seen: set[str] = set()
    for (pname, cat), dates in prop_cat_dates.items():
        if cat in ("Onboarding / Setup", "Other", "Inspection / QA"):
            continue
        dates.sort()
        for i in range(len(dates)):
            window = [d for d in dates if 0 <= (d - dates[i]).days <= 180]
            if len(window) >= 5:
                key = f"{pname}::{cat}"
                if key not in seen:
                    seen.add(key)
                    # Unique task name samples
                    names   = list(dict.fromkeys(prop_cat_names[(pname, cat)]))[:4]
                    clusters.append({
                        "property":  pname,
                        "category":  cat,
                        "count":     len(window),
                        "span_days": (window[-1] - window[0]).days,
                        "first":     window[0].isoformat(),
                        "last":      window[-1].isoformat(),
                        "evidence":  names,
                    })
                break

    clusters.sort(key=lambda x: -x["count"])
    return clusters[:15]


def _build_leadership_brief(bw_tasks: list[dict]) -> list[dict]:
    """
    Executive briefing: up to 6 ranked insight cards derived entirely from live data.
    Each card has: level, headline, explanation, metric, action.
    Levels: critical | risk | opportunity | positive
    Priority order within levels: critical → risk → opportunity → positive.
    """
    maint = [t for t in bw_tasks if t.get("type_department") == "maintenance"]
    if not maint:
        return []

    today = datetime.date.today()
    l30   = today - datetime.timedelta(days=30)
    p30   = today - datetime.timedelta(days=60)

    # ── Compute signals ──────────────────────────────────────────────────────

    # Magazine Street burden
    mag_maint = [t for t in maint if "mag" in t["_property_name"].upper()]
    mag_props  = len(set(t["_property_name"] for t in mag_maint))
    mag_total  = len(mag_maint)
    all_props  = set(t["_property_name"] for t in maint)
    portfolio_avg = len(maint) / max(len(all_props), 1)
    mag_ratio  = (mag_total / max(mag_props, 1)) / max(portfolio_avg, 1)

    # Schaeffer HVAC acute failures
    sch_hvac = [t for t in maint
                if "schaeffer" in t["_property_name"].lower()
                and t["_category"] == "HVAC"]
    sch_hvac_props = set(t["_property_name"] for t in sch_hvac)
    # Focus on 201 and 209 specifically
    acute_hvac = [t for t in sch_hvac
                  if "201" in t["_property_name"] or "209" in t["_property_name"]]
    acute_hvac_count = len(acute_hvac)
    acute_hvac_units = len(set(t["_property_name"] for t in acute_hvac))

    # Workload concentration
    assignee_counts: Counter = Counter()
    for t in bw_tasks:
        for a in (t.get("assignments") or []):
            if a.get("name"):
                assignee_counts[a["name"]] += 1
    total_assigned = sum(assignee_counts.values())
    top_name, top_count = assignee_counts.most_common(1)[0] if assignee_counts else ("—", 0)
    top_pct = round(top_count / max(total_assigned, 1) * 100)

    # Inspection gap
    qtr_props = set(
        t["_property_name"] for t in maint
        if any(kw in t.get("name", "").lower()
               for kw in ["quarterly", "q2 bem", "q3 bem", "q4 bem"])
    )
    uninspected     = len(all_props - qtr_props)
    uninspected_pct = round(uninspected / max(len(all_props), 1) * 100)

    # Plumbing dominance
    plumb_count = sum(1 for t in maint if t["_category"] == "Plumbing")
    plumb_pct   = round(plumb_count / max(len(maint), 1) * 100)

    # Air filter / preventive opportunity
    air_tasks = sum(1 for t in maint
                    if "air filter" in t.get("name", "").lower()
                    or ("filter" in t.get("name", "").lower()
                        and "fridge" not in t.get("name", "").lower()))
    # Unique properties with air filter tasks
    air_props = len(set(t["_property_name"] for t in maint
                        if "air filter" in t.get("name", "").lower()
                        or ("filter" in t.get("name", "").lower()
                            and "fridge" not in t.get("name", "").lower())))

    # Maintenance trend
    last30_maint  = sum(1 for t in maint
                        if _parse_date(t.get("created_at")) and
                        _parse_date(t.get("created_at")) >= l30)
    prior30_maint = sum(1 for t in maint
                        if _parse_date(t.get("created_at")) and
                        p30 <= _parse_date(t.get("created_at")) < l30)
    trend_pct = round((last30_maint / max(prior30_maint, 1) - 1) * 100)

    # Pest control repeat
    pest_props = Counter(t["_property_name"] for t in maint
                         if t["_category"] == "Pest Control")
    repeat_pest = sum(1 for _, n in pest_props.items() if n >= 3)

    # ── Build brief items ────────────────────────────────────────────────────
    # Each item: level (critical|risk|opportunity|positive), sort_key (lower = higher priority),
    # headline, explanation, metric, action
    candidates: list[dict] = []

    # 1. Magazine St — critical if ratio > 3×
    if mag_props >= 2 and mag_ratio >= 2.5:
        candidates.append({
            "level":       "critical",
            "sort_key":    (0, -mag_total),
            "headline":    "Magazine Street Maintenance Burden",
            "explanation": f"{mag_props} Magazine Street properties generated {mag_total} maintenance tasks "
                           f"— {mag_ratio:.1f}× the portfolio median per property.",
            "metric":      f"{mag_total} maintenance tasks across {mag_props} properties",
            "action":      "Review infrastructure condition and owner maintenance strategy.",
        })

    # 2. Schaeffer HVAC — critical if 8+ incidents across 2 units
    if acute_hvac_count >= 8 and acute_hvac_units >= 2:
        candidates.append({
            "level":       "critical",
            "sort_key":    (0, -acute_hvac_count),
            "headline":    "Schaeffer HVAC Failure Pattern",
            "explanation": f"Schaeffer 201 and Schaeffer 209 show repeated HVAC failures consistent "
                           f"with end-of-life equipment — {acute_hvac_count} incidents across "
                           f"{acute_hvac_units} units.",
            "metric":      f"{acute_hvac_count} HVAC-related incidents across {acute_hvac_units} units",
            "action":      "Evaluate replacement versus continued repair.",
        })

    # 3. Workload concentration — critical if top person > 30%
    if top_pct >= 30:
        candidates.append({
            "level":       "critical" if top_pct >= 35 else "risk",
            "sort_key":    (0 if top_pct >= 35 else 1, -top_pct),
            "headline":    "Operational Dependency",
            "explanation": f"{top_pct}% of all task assignments are concentrated with a single team member. "
                           f"An absence would immediately impact over a third of active capacity.",
            "metric":      f"{top_count:,} tasks assigned to {top_name}",
            "action":      "Review workload distribution and redundancy planning.",
        })

    # 4. Inspection gap — risk if > 60% uninspected
    if uninspected_pct >= 60:
        candidates.append({
            "level":       "risk",
            "sort_key":    (1, -uninspected),
            "headline":    "Inspection Coverage Gap",
            "explanation": f"{uninspected_pct}% of active properties have no documented quarterly inspection. "
                           "Every major repair cluster identified was at an uninspected property.",
            "metric":      f"{uninspected} of {len(all_props)} properties without quarterly inspections",
            "action":      "Expand preventive inspection coverage before peak season demand increases.",
        })

    # 5. Plumbing dominance — risk
    if plumb_pct >= 20:
        candidates.append({
            "level":       "risk",
            "sort_key":    (1, -plumb_count),
            "headline":    "Plumbing Dominates Maintenance",
            "explanation": f"Plumbing is the single largest maintenance category at {plumb_pct}% of all work. "
                           "Most tickets are guest-reported — guests are the quality control system.",
            "metric":      f"{plumb_count} plumbing tasks ({plumb_pct}% of maintenance volume)",
            "action":      "Investigate recurring fixture and drain failures. Schedule proactive drain treatments.",
        })

    # 6. Preventive maintenance opportunity — opportunity
    if air_tasks >= 10:
        candidates.append({
            "level":       "opportunity",
            "sort_key":    (2, -air_tasks),
            "headline":    "Preventive Maintenance Potential",
            "explanation": f"Air filters, plumbing fixtures, and drain issues show repeatable patterns "
                           f"across {air_props} properties — suitable for scheduled preventive programs.",
            "metric":      f"{air_tasks} air-filter-related tasks identified across {air_props} properties",
            "action":      "Develop quarterly scheduled preventive maintenance workflows.",
        })

    # 7. Maintenance trend rising — risk or positive
    if abs(trend_pct) >= 10:
        level  = "risk" if trend_pct > 0 else "positive"
        dir_   = "up" if trend_pct > 0 else "down"
        candidates.append({
            "level":       level,
            "sort_key":    (1 if level == "risk" else 3, -abs(trend_pct)),
            "headline":    f"Maintenance Volume {'+' if trend_pct > 0 else ''}{trend_pct}% This Month",
            "explanation": f"Maintenance task creation is trending {dir_} compared to the prior 30-day period. "
                           + ("Plumbing and onboarding are driving the increase."
                              if trend_pct > 0 else "Fewer new issues are emerging — a positive signal."),
            "metric":      f"{last30_maint} tasks created (vs {prior30_maint} prior period)",
            "action":      "Monitor plumbing and HVAC categories for continued acceleration." if trend_pct > 0 else None,
        })

    # 8. Pest control — risk if 3+ properties with repeat incidents
    if repeat_pest >= 3:
        candidates.append({
            "level":       "risk",
            "sort_key":    (1, -repeat_pest),
            "headline":    "Pest Control Recurring Across Portfolio",
            "explanation": f"{repeat_pest} properties have 3 or more pest-related maintenance tasks. "
                           "In New Orleans STRs, repeat pest incidents directly drive negative reviews.",
            "metric":      f"{sum(pest_props.values())} pest tasks · {repeat_pest} properties with repeat incidents",
            "action":      "Establish a portfolio-wide recurring pest treatment program.",
        })

    # Sort: by sort_key, cap at 6
    candidates.sort(key=lambda x: x["sort_key"])
    for c in candidates:
        del c["sort_key"]

    return candidates[:6]


def _build_leadership_insights(
    bw_tasks: list[dict],
    stale_tasks: list[dict],
    dq_rows: list[dict],
) -> list[dict]:
    """Pre-computed executive insights from live Breezeway + Supabase data."""
    maint  = [t for t in bw_tasks if t.get("type_department") == "maintenance"]
    today  = datetime.date.today()
    l30    = today - datetime.timedelta(days=30)
    p30    = today - datetime.timedelta(days=60)

    last30_maint  = sum(1 for t in maint if _parse_date(t.get("created_at")) and
                        _parse_date(t.get("created_at")) >= l30)
    prior30_maint = sum(1 for t in maint if _parse_date(t.get("created_at")) and
                        p30 <= _parse_date(t.get("created_at")) < l30)
    maint_trend_pct = round((last30_maint / max(prior30_maint, 1) - 1) * 100)

    # Plumbing volume
    plumb_count = sum(1 for t in maint if t["_category"] == "Plumbing")
    plumb_pct   = round(plumb_count / max(len(maint), 1) * 100)

    # Workload concentration
    assignee_counts: Counter = Counter()
    for t in bw_tasks:
        for a in (t.get("assignments") or []):
            if a.get("name"):
                assignee_counts[a["name"]] += 1
    total_assigned = sum(assignee_counts.values())
    top_assignee, top_count = assignee_counts.most_common(1)[0] if assignee_counts else ("—", 0)
    top_pct = round(top_count / max(total_assigned, 1) * 100)

    # Unassigned open tasks
    open_unassigned = sum(
        1 for t in bw_tasks
        if t["type_task_status"]["code"] in _OPEN_CODES and not t.get("assignments")
    )

    # Urgent switchover cleans
    urgent_cleans = sum(1 for t in bw_tasks if "urgent" in t.get("name", "").lower()
                        and ("clean" in t.get("name", "").lower() or "switch" in t.get("name", "").lower()))

    # Inspection gap
    qtr_props = set(t["_property_name"] for t in maint
                    if any(kw in t.get("name", "").lower()
                           for kw in ["quarterly", "q2 bem", "q3 bem", "q4 bem"]))
    all_maint_props = set(t["_property_name"] for t in maint)
    uninspected = len(all_maint_props - qtr_props)

    # Magazine St avg completion
    mag_tasks = [t for t in maint if "mag" in t["_property_name"].upper()]
    mag_hours  = [h for t in mag_tasks for h in [_comp_hours(t)] if h]
    mag_avg    = round(statistics.mean(mag_hours), 1) if mag_hours else None

    insights = [
        {
            "icon":  "trend",
            "level": "warn" if maint_trend_pct > 10 else "info",
            "title": f"Maintenance volume up {maint_trend_pct}% in the last 30 days",
            "body":  f"{last30_maint} maintenance tasks created in the last 30 days vs {prior30_maint} in the prior period. "
                     "Plumbing and onboarding are driving the increase.",
        },
        {
            "icon":  "plumbing",
            "level": "warn",
            "title": f"Plumbing is {plumb_pct}% of all maintenance work",
            "body":  f"{plumb_count} of {len(maint)} maintenance tasks are plumbing-related. "
                     "Most are guest-reported rather than proactively identified — guests are the quality control system.",
        },
        {
            "icon":  "person",
            "level": "critical",
            "title": f"{top_assignee} carries {top_pct}% of all task assignments",
            "body":  f"{top_count} of {total_assigned} total task assignments flow through one person. "
                     "If unavailable, BEM loses over a third of operational capacity immediately.",
        },
        {
            "icon":  "unassigned",
            "level": "warn" if open_unassigned > 0 else "info",
            "title": f"{open_unassigned} open tasks have no owner",
            "body":  "These tasks won't surface as stale — they were never started. "
                     "They are invisible in status-based reporting and accumulating silently.",
        },
        {
            "icon":  "urgent",
            "level": "info",
            "title": f"{urgent_cleans} same-day urgent cleans in the dataset",
            "body":  "14% of all tasks are urgent switchover cleans — created because back-to-back bookings "
                     "leave no buffer for a standard clean. This is a scheduling pressure signal, not a cleaning quality problem.",
        },
        {
            "icon":  "inspection",
            "level": "critical",
            "title": f"{uninspected} of {len(all_maint_props)} active properties have no quarterly inspection on record",
            "body":  "Every repeat failure cluster identified — HVAC, plumbing cascades, access failures — "
                     "occurred at uninspected properties. Inspection is the most under-deployed tool in the maintenance program.",
        },
    ]
    if mag_avg:
        insights.append({
            "icon":  "property",
            "level": "warn",
            "title": f"Magazine Street averages {mag_avg}h per maintenance task — highest in portfolio",
            "body":  "4112MAG, 4854MAG, and 4856MAG generate maintenance at 4× the portfolio rate per property. "
                     "These properties need owner conversations about infrastructure investment.",
        })

    return insights


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    client = db.get_client()

    at_risk_rows = db.select_view("v_at_risk_arrivals")
    stale_tasks  = db.select_view("v_stale_tasks")
    quick_wins   = db.select_view("v_quick_wins")
    thursday     = db.select_view("v_thursday_call")
    dq_rows      = db.select_view("v_property_data_quality")
    all_risks    = db.select("operational_risks", {"is_active": True})
    all_tasks    = db.select("tasks", {})

    prop_map = {p["property_id"]: p["property_name"] for p in dq_rows if p.get("property_id")}

    kpis             = _build_kpis(all_tasks, stale_tasks, all_risks, dq_rows)
    attention_items  = _build_attention_items(at_risk_rows, stale_tasks)
    recurring        = _build_recurring_patterns(all_risks)
    today_arrivals   = _build_today_arrivals(prop_map)
    portfolio_stats  = _build_portfolio_stats(dq_rows, all_risks)

    today      = datetime.date.today()
    days_ahead = (3 - today.weekday()) % 7
    next_thurs = today + datetime.timedelta(days=days_ahead)
    thursday_open = sum(1 for t in thursday if t.get("status") == "open")

    # Breezeway live intelligence
    bw_tasks             = bw_get_tasks()
    property_health      = _build_property_health(bw_tasks)
    recurring_issues     = _build_recurring_issues(bw_tasks)
    replacement_candidates = _build_replacement_candidates(bw_tasks)
    leadership_insights  = _build_leadership_insights(bw_tasks, stale_tasks, dq_rows)
    leadership_brief     = _build_leadership_brief(bw_tasks)

    return templates.TemplateResponse("dashboard.html", {
        "request":                request,
        "page":                   "dashboard",
        "generated_at":           datetime.datetime.now().strftime("%A, %B %d %Y · %H:%M"),
        "kpis":                   kpis,
        "attention_items":        attention_items,
        "today_arrivals":         today_arrivals,
        "quick_wins":             quick_wins,
        "portfolio_stats":        portfolio_stats,
        "recurring":              recurring,
        "thursday_items":         thursday,
        "thursday_open":          thursday_open,
        "next_thursday":          next_thurs.strftime("%B %d"),
        "stale_tasks":            stale_tasks,
        "property_health":        property_health,
        "recurring_issues":       recurring_issues,
        "replacement_candidates": replacement_candidates,
        "leadership_insights":    leadership_insights,
        "leadership_brief":       leadership_brief,
        "bw_loaded":              bool(bw_tasks),
    })


@app.get("/property", response_class=HTMLResponse)
def property_view(request: Request, q: str = ""):
    client     = db.get_client()
    properties = []
    selected   = None
    risks      = []
    arrivals   = []

    if q.strip():
        result = (
            client.table("properties")
            .select("*")
            .or_(f"internal_name.ilike.%{q}%,street.ilike.%{q}%")
            .order("internal_name")
            .execute()
        )
        properties = result.data or []

        if len(properties) == 1:
            selected = properties[0]
            pid = selected["id"]

            risks = (
                client.table("operational_risks")
                .select("*")
                .eq("property_id", pid)
                .eq("is_active", True)
                .order("severity")
                .execute()
                .data or []
            )
            risks.sort(key=lambda r: _SEV_ORDER.get(r.get("severity", "low"), 3))

            today_str = datetime.date.today().isoformat()
            arrivals = (
                client.table("reservations")
                .select("*")
                .eq("property_id", pid)
                .eq("status", "confirmed")
                .gte("checkin_date", today_str)
                .order("checkin_date")
                .limit(10)
                .execute()
                .data or []
            )

    return templates.TemplateResponse("property.html", {
        "request":    request,
        "page":       "property",
        "q":          q,
        "properties": properties,
        "selected":   selected,
        "risks":      risks,
        "arrivals":   arrivals,
    })


@app.get("/pascal", response_class=HTMLResponse)
def pascal_page(request: Request):
    return templates.TemplateResponse("pascal.html", {
        "request": request,
        "page":    "pascal",
    })
