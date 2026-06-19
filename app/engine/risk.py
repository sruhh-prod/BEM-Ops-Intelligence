"""
Risk engine.

Reads exclusively from Supabase tables. Has no knowledge of Hostaway,
Breezeway, or mock data — it operates on whatever is in the database.

Rules produce records for `operational_risks` and update:
  - tasks.is_stale
  - tasks.blocks_arrival
  - reservations.risk_level  (highest severity across that reservation's active risks)

Each rule is a standalone function that returns a list of risk dicts.
Adding a new rule means adding one function and one entry in RISK_RULES.
"""

from __future__ import annotations


import datetime
import logging

from db import client as db

log = logging.getLogger(__name__)

_TODAY = datetime.date.today()
_NOW   = datetime.datetime.utcnow()

# Thresholds
_STALE_HOURS           = 48
_AT_RISK_WINDOW_HOURS  = 72
_EXPIRING_LICENSE_DAYS = 90
_UNASSIGNED_HOURS      = 24   # flag unassigned task within this many hours of schedule


# ---------------------------------------------------------------------------
# Risk record builder
# ---------------------------------------------------------------------------

def _risk(property_id, severity, risk_type, title, detail, recommendation,
          reservation_id=None, task_id=None, hours_until_checkin=None,
          checkin_date=None) -> dict:
    return {
        "property_id":        property_id,
        "reservation_id":     reservation_id,
        "task_id":            task_id,
        "risk_type":          risk_type,
        "severity":           severity,
        "title":              title,
        "detail":             detail,
        "recommendation":     recommendation,
        "hours_until_checkin": hours_until_checkin,
        "checkin_date":       checkin_date.isoformat() if checkin_date else None,
        "is_active":          True,
        "detected_by":        "risk_engine",
        "computed_at":        _NOW.isoformat(),
    }


# ---------------------------------------------------------------------------
# Rule 1: Open clean before arrival
# ---------------------------------------------------------------------------

def check_open_clean_before_arrival(properties, reservations, tasks) -> list[dict]:
    """
    A confirmed reservation is arriving within 72 hours and no housekeeping
    task for that property is in a completed/approved state today.
    """
    risks = []
    prop_map = {p["id"]: p for p in properties}

    # Upcoming reservations
    upcoming = [
        r for r in reservations
        if r.get("status") == "confirmed"
        and r.get("checkin_date")
        and _date(r["checkin_date"]) >= _TODAY
        and _date(r["checkin_date"]) <= _TODAY + datetime.timedelta(hours=_AT_RISK_WINDOW_HOURS / 24 + 1)
    ]

    # Build: property_id → set of completed housekeeping task dates
    clean_map: dict[str, set] = {}
    for t in tasks:
        if t.get("department") == "housekeeping" and t.get("status") in ("completed", "approved"):
            pid = t.get("property_id")
            if pid:
                clean_map.setdefault(pid, set()).add(t.get("scheduled_date") or t.get("due_date"))

    for r in upcoming:
        pid = r.get("property_id")
        checkin = _date(r["checkin_date"])
        hours   = _hours_until(checkin)

        completed_dates = clean_map.get(pid, set())
        if checkin.isoformat() not in completed_dates:
            severity = "critical" if hours <= 12 else "high" if hours <= 24 else "medium"
            risks.append(_risk(
                property_id      = pid,
                reservation_id   = r["id"],
                severity         = severity,
                risk_type        = "open_clean_before_arrival",
                title            = f"No completed clean — guest arrives in {_fmt_hours(hours)}",
                detail           = f"No housekeeping task is completed or approved for {checkin.isoformat()}. Guest: {r.get('guest_name','Unknown')} ({r.get('guest_count',1)} guests).",
                recommendation   = "Assign and confirm a housekeeper immediately. Check task list for pending clean.",
                hours_until_checkin = hours,
                checkin_date     = checkin,
            ))
    return risks


# ---------------------------------------------------------------------------
# Rule 2: Open maintenance before arrival
# ---------------------------------------------------------------------------

def check_open_maintenance_before_arrival(properties, reservations, tasks) -> list[dict]:
    """
    An open (non-complete) maintenance task exists at a property with
    a confirmed arrival within 48 hours.
    """
    risks = []

    upcoming_by_prop: dict[str, list] = {}
    for r in reservations:
        if r.get("status") == "confirmed" and r.get("checkin_date"):
            checkin = _date(r["checkin_date"])
            if _TODAY <= checkin <= _TODAY + datetime.timedelta(days=2):
                upcoming_by_prop.setdefault(r["property_id"], []).append(r)

    open_maint: dict[str, list] = {}
    for t in tasks:
        if t.get("department") == "maintenance" and t.get("status") not in ("completed", "approved", "closed"):
            if not t.get("deleted_at"):
                open_maint.setdefault(t["property_id"], []).append(t)

    for pid, res_list in upcoming_by_prop.items():
        maint_tasks = open_maint.get(pid, [])
        if not maint_tasks:
            continue
        for r in res_list:
            checkin = _date(r["checkin_date"])
            hours   = _hours_until(checkin)
            for t in maint_tasks:
                risks.append(_risk(
                    property_id      = pid,
                    reservation_id   = r["id"],
                    task_id          = t["id"],
                    severity         = "high",
                    risk_type        = "open_maintenance_before_arrival",
                    title            = f"Open maintenance — '{t['task_name']}' — guest in {_fmt_hours(hours)}",
                    detail           = f"Maintenance task '{t['task_name']}' (priority: {t.get('priority')}) is not resolved before arrival of {r.get('guest_name','guest')} on {checkin}.",
                    recommendation   = f"Resolve or defer task '{t['task_name']}'. If guest-impacting, notify guest proactively.",
                    hours_until_checkin = hours,
                    checkin_date     = checkin,
                ))
    return risks


# ---------------------------------------------------------------------------
# Rule 3: Stale tasks
# ---------------------------------------------------------------------------

def check_stale_tasks(tasks) -> tuple[list[dict], list[str]]:
    """
    Tasks that have not been updated in more than STALE_HOURS and are
    not in a terminal state, scheduled within the next 7 days.
    Returns (risks, stale_task_ids_to_flag).
    """
    risks      = []
    stale_ids  = []
    cutoff     = _NOW - datetime.timedelta(hours=_STALE_HOURS)
    window_end = _TODAY + datetime.timedelta(days=7)

    for t in tasks:
        if t.get("status") in ("completed", "approved", "closed"):
            continue
        if t.get("deleted_at"):
            continue
        updated = _parse_dt(t.get("updated_at"))
        if not updated:
            continue
        sched = _date_or_none(t.get("scheduled_date") or t.get("due_date"))
        if sched and sched > window_end:
            continue
        if updated < cutoff:
            hours_stale = int((_NOW - updated).total_seconds() / 3600)
            stale_ids.append(t["id"])
            risks.append(_risk(
                property_id    = t["property_id"],
                task_id        = t["id"],
                severity       = "medium",
                risk_type      = "stale_task",
                title          = f"Stale task — no activity in {hours_stale}h — '{t['task_name']}'",
                detail         = f"Task '{t['task_name']}' ({t.get('department')}, {t.get('status')}) has not been updated since {updated.date()}.",
                recommendation = "Contact assignee for status update. If blocked, reassign or escalate.",
            ))
    return risks, stale_ids


# ---------------------------------------------------------------------------
# Rule 4: Overdue tasks
# ---------------------------------------------------------------------------

def check_overdue_tasks(tasks) -> list[dict]:
    risks = []
    for t in tasks:
        if not t.get("is_overdue"):
            continue
        due = _date_or_none(t.get("due_date"))
        days_overdue = (_TODAY - due).days if due else 0
        severity = "high" if days_overdue >= 3 else "medium"
        risks.append(_risk(
            property_id    = t["property_id"],
            task_id        = t["id"],
            severity       = severity,
            risk_type      = "overdue_task",
            title          = f"Overdue {days_overdue}d — '{t['task_name']}'",
            detail         = f"Task '{t['task_name']}' ({t.get('department')}) was due {due} and is still '{t.get('status')}'.",
            recommendation = "Reassign, reschedule, or close if no longer applicable. Update status.",
        ))
    return risks


# ---------------------------------------------------------------------------
# Rule 5: Unassigned urgent/high priority tasks within 24h
# ---------------------------------------------------------------------------

def check_unassigned_tasks(tasks, assignments) -> list[dict]:
    """
    Tasks scheduled within the next UNASSIGNED_HOURS with no assigned person.
    """
    risks = []
    assigned_task_ids = {a["task_id"] for a in assignments}
    cutoff_date = _TODAY + datetime.timedelta(hours=_UNASSIGNED_HOURS / 24 + 1)

    for t in tasks:
        if t.get("status") in ("completed", "approved", "closed"):
            continue
        if t.get("deleted_at"):
            continue
        if t["id"] in assigned_task_ids:
            continue
        sched = _date_or_none(t.get("scheduled_date"))
        if not sched or sched > cutoff_date:
            continue
        hours = _hours_until(sched)
        risks.append(_risk(
            property_id    = t["property_id"],
            task_id        = t["id"],
            severity       = "high" if t.get("priority") in ("urgent", "high") else "medium",
            risk_type      = "unassigned_task",
            title          = f"Unassigned — '{t['task_name']}' — scheduled in {_fmt_hours(hours)}",
            detail         = f"No one is assigned to '{t['task_name']}' ({t.get('department')}, priority: {t.get('priority')}) scheduled for {sched}.",
            recommendation = "Assign immediately. Check staff availability and subdepartment.",
        ))
    return risks


# ---------------------------------------------------------------------------
# Rule 6: Missing access instructions
# ---------------------------------------------------------------------------

def check_missing_access_instructions(properties) -> list[dict]:
    risks = []
    for p in properties:
        if not p.get("access_instructions") and not p.get("door_code"):
            risks.append(_risk(
                property_id    = p["id"],
                severity       = "low",
                risk_type      = "missing_access_instructions",
                title          = f"No access instructions — {p.get('internal_name','?')[:50]}",
                detail         = "Neither access_instructions nor door_code is populated. Guests cannot receive entry information.",
                recommendation = "Add entry method and door code to property record. Check airbnbAccess field in Hostaway.",
            ))
    return risks


# ---------------------------------------------------------------------------
# Rule 7: Missing WiFi credentials
# ---------------------------------------------------------------------------

def check_missing_wifi(properties) -> list[dict]:
    risks = []
    for p in properties:
        if not p.get("wifi_network") or not p.get("wifi_password"):
            risks.append(_risk(
                property_id    = p["id"],
                severity       = "low",
                risk_type      = "missing_wifi_credentials",
                title          = f"WiFi not on record — {p.get('internal_name','?')[:50]}",
                detail         = "WiFi network name and/or password are not in the property record.",
                recommendation = "Extract WiFi credentials from access_instructions/airbnbNotes or enter manually.",
            ))
    return risks


# ---------------------------------------------------------------------------
# Rule 8: Expired STR license
# ---------------------------------------------------------------------------

def check_expired_str_license(properties) -> list[dict]:
    risks = []
    for p in properties:
        if p.get("str_license_expired") or (
            p.get("str_license_expires") and
            _date(p["str_license_expires"]) < _TODAY
        ):
            risks.append(_risk(
                property_id    = p["id"],
                severity       = "high",
                risk_type      = "expired_str_license",
                title          = f"STR license EXPIRED — {p.get('internal_name','?')[:50]}",
                detail         = f"License #{p.get('str_license_number')} expired {p.get('str_license_expires')}.",
                recommendation = "Contact owner immediately. Do not accept new bookings until renewed.",
            ))
    return risks


# ---------------------------------------------------------------------------
# Rule 9: Expiring STR license (within 90 days)
# ---------------------------------------------------------------------------

def check_expiring_str_license(properties) -> list[dict]:
    risks = []
    window = _TODAY + datetime.timedelta(days=_EXPIRING_LICENSE_DAYS)
    for p in properties:
        expires = _date_or_none(p.get("str_license_expires"))
        if expires and _TODAY <= expires <= window:
            days_left = (expires - _TODAY).days
            risks.append(_risk(
                property_id    = p["id"],
                severity       = "medium",
                risk_type      = "expiring_str_license",
                title          = f"STR license expires in {days_left}d — {p.get('internal_name','?')[:50]}",
                detail         = f"License #{p.get('str_license_number')} expires {expires}.",
                recommendation = f"Initiate renewal process. Owner must file {days_left} days before expiry.",
            ))
    return risks


# ---------------------------------------------------------------------------
# Rule 10: Guest access code not set for arriving reservation
# ---------------------------------------------------------------------------

def check_access_code_not_set(reservations) -> list[dict]:
    risks = []
    window = _TODAY + datetime.timedelta(days=2)
    for r in reservations:
        if r.get("status") != "confirmed":
            continue
        checkin = _date_or_none(r.get("checkin_date"))
        if not checkin or checkin > window:
            continue
        if not r.get("guest_access_code"):
            hours = _hours_until(checkin)
            risks.append(_risk(
                property_id         = r["property_id"],
                reservation_id      = r["id"],
                severity            = "high" if hours <= 24 else "medium",
                risk_type           = "access_code_not_set",
                title               = f"No guest access code — {r.get('guest_name','guest')} arrives in {_fmt_hours(hours)}",
                detail              = "No guest_access_code is set on this reservation. Guest cannot receive entry information.",
                recommendation      = "Generate or confirm access code in Breezeway / lock manager. Send to guest.",
                hours_until_checkin = hours,
                checkin_date        = checkin,
            ))
    return risks


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------

RISK_RULES = [
    "open_clean_before_arrival",
    "open_maintenance_before_arrival",
    "stale_tasks",
    "overdue_tasks",
    "unassigned_tasks",
    "missing_access_instructions",
    "missing_wifi_credentials",
    "expired_str_license",
    "expiring_str_license",
    "access_code_not_set",
]


def run_risk_engine() -> dict:
    """
    Execute all risk rules and write results to Supabase.
    Returns a summary of risks found per type.
    """
    log.info("[risk_engine] loading data from Supabase")

    properties  = db.select("properties", {})
    reservations = db.select("reservations", {})
    tasks       = db.select("tasks", {})
    assignments = db.select("task_assignments", {})

    log.info(f"[risk_engine] {len(properties)} properties, {len(reservations)} reservations, "
             f"{len(tasks)} tasks, {len(assignments)} assignments")

    all_risks: list[dict] = []

    # Compute risks
    all_risks += check_open_clean_before_arrival(properties, reservations, tasks)
    all_risks += check_open_maintenance_before_arrival(properties, reservations, tasks)

    stale_risks, stale_ids = check_stale_tasks(tasks)
    all_risks += stale_risks

    all_risks += check_overdue_tasks(tasks)
    all_risks += check_unassigned_tasks(tasks, assignments)
    all_risks += check_missing_access_instructions(properties)
    all_risks += check_missing_wifi(properties)
    all_risks += check_expired_str_license(properties)
    all_risks += check_expiring_str_license(properties)
    all_risks += check_access_code_not_set(reservations)

    # Deactivate all previous risks before writing fresh ones
    _deactivate_old_risks()

    # Mark stale tasks
    if stale_ids:
        _flag_stale_tasks(stale_ids)

    # Mark tasks that block arrivals
    blocks_ids = [r["task_id"] for r in all_risks
                  if r.get("task_id") and r["risk_type"] in (
                      "open_clean_before_arrival",
                      "open_maintenance_before_arrival",
                      "overdue_task",
                  )]
    if blocks_ids:
        _flag_blocking_tasks(blocks_ids)

    # Write new risks
    if all_risks:
        try:
            db.get_client().table("operational_risks").insert(all_risks).execute()
            log.info(f"[risk_engine] wrote {len(all_risks)} risk records")
        except Exception as e:
            log.error(f"[risk_engine] failed to write risks: {e}")

    # Update reservation risk_level (max severity per reservation)
    _update_reservation_risk_levels(all_risks)

    # Auto-generate Thursday Call items
    _generate_thursday_call_items(all_risks)

    summary = {}
    for r in all_risks:
        summary[r["risk_type"]] = summary.get(r["risk_type"], 0) + 1

    log.info(f"[risk_engine] summary: {summary}")
    return summary


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------

def _deactivate_old_risks() -> None:
    try:
        db.get_client().table("operational_risks").update(
            {"is_active": False}
        ).eq("is_active", True).execute()
    except Exception as e:
        log.warning(f"[risk_engine] could not deactivate old risks: {e}")


def _flag_stale_tasks(task_ids: list[str]) -> None:
    for tid in task_ids:
        try:
            db.get_client().table("tasks").update(
                {"is_stale": True, "stale_since": _NOW.isoformat()}
            ).eq("id", tid).execute()
        except Exception as e:
            log.warning(f"[risk_engine] could not flag stale task {tid}: {e}")


def _flag_blocking_tasks(task_ids: list[str]) -> None:
    for tid in task_ids:
        try:
            db.get_client().table("tasks").update(
                {"blocks_arrival": True}
            ).eq("id", tid).execute()
        except Exception as e:
            log.warning(f"[risk_engine] could not flag blocking task {tid}: {e}")


def _update_reservation_risk_levels(risks: list[dict]) -> None:
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    res_max: dict[str, str] = {}
    for r in risks:
        rid = r.get("reservation_id")
        if not rid:
            continue
        current = severity_order.get(res_max.get(rid, "low"), 1)
        new     = severity_order.get(r["severity"], 1)
        if new > current:
            res_max[rid] = r["severity"]

    for rid, severity in res_max.items():
        try:
            db.get_client().table("reservations").update(
                {"risk_level": severity, "risk_computed_at": _NOW.isoformat()}
            ).eq("id", rid).execute()
        except Exception as e:
            log.warning(f"[risk_engine] could not update reservation risk_level for {rid}: {e}")


def _generate_thursday_call_items(risks: list[dict]) -> None:
    """
    Auto-generate thursday_call_items for the coming Thursday
    from active high/critical risks and other notable signals.
    """
    thursday = _next_thursday()
    items    = []

    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    seen_risk_types: dict[str, int] = {}
    for r in sorted(risks, key=lambda x: -severity_order.get(x["severity"], 0)):
        if r["severity"] not in ("critical", "high"):
            continue

        # Deduplicate by risk_type per property (one item per property+type)
        key = f"{r['property_id']}::{r['risk_type']}"
        if key in seen_risk_types:
            continue
        seen_risk_types[key] = 1

        category = _risk_type_to_thursday_category(r["risk_type"])
        priority = 1 if r["severity"] == "critical" else 2

        items.append({
            "call_date":          thursday.isoformat(),
            "property_id":        r.get("property_id"),
            "reservation_id":     r.get("reservation_id"),
            "task_id":            r.get("task_id"),
            "operational_risk_id": None,   # linked after risks are inserted
            "category":           category,
            "title":              r["title"],
            "summary":            r.get("detail"),
            "recommendation":     r.get("recommendation"),
            "priority":           priority,
            "source":             "auto",
            "generated_by":       "risk_engine",
            "status":             "open",
        })

    if items:
        # Clear existing auto-generated items for this Thursday
        try:
            db.get_client().table("thursday_call_items").delete().eq(
                "call_date", thursday.isoformat()
            ).eq("source", "auto").execute()
        except Exception:
            pass
        try:
            db.get_client().table("thursday_call_items").insert(items).execute()
            log.info(f"[risk_engine] generated {len(items)} thursday_call_items for {thursday}")
        except Exception as e:
            log.warning(f"[risk_engine] could not write thursday_call_items: {e}")


def _risk_type_to_thursday_category(risk_type: str) -> str:
    mapping = {
        "open_clean_before_arrival":          "at_risk_arrival",
        "open_maintenance_before_arrival":    "at_risk_arrival",
        "no_inspection_before_arrival":       "at_risk_arrival",
        "access_code_not_set":                "at_risk_arrival",
        "stale_task":                         "stale_task",
        "overdue_task":                       "stale_task",
        "unassigned_task":                    "stale_task",
        "missing_access_instructions":        "data_quality_gap",
        "missing_wifi_credentials":           "data_quality_gap",
        "expired_str_license":                "compliance_alert",
        "expiring_str_license":               "compliance_alert",
        "guest_count_exceeds_capacity":       "at_risk_arrival",
    }
    return mapping.get(risk_type, "general")


def _next_thursday() -> datetime.date:
    today = _TODAY
    # (3 - weekday) % 7: returns 0 on Thursday (stay today), 1-6 otherwise
    days_ahead = (3 - today.weekday()) % 7
    return today + datetime.timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

def _date(val: str | datetime.date) -> datetime.date:
    if isinstance(val, datetime.date):
        return val
    return datetime.date.fromisoformat(str(val)[:10])


def _date_or_none(val) -> datetime.date | None:
    if not val:
        return None
    try:
        return _date(val)
    except Exception:
        return None


def _parse_dt(val) -> datetime.datetime | None:
    if not val:
        return None
    try:
        s = str(val).replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(s).replace(tzinfo=None)
    except Exception:
        return None


def _hours_until(d: datetime.date) -> float:
    target = datetime.datetime.combine(d, datetime.time(15, 0))  # assume 3 PM checkin
    delta  = target - _NOW
    return round(delta.total_seconds() / 3600, 1)


def _fmt_hours(h: float) -> str:
    if h < 0:
        return f"{abs(h):.0f}h ago"
    if h < 24:
        return f"{h:.0f}h"
    return f"{h / 24:.1f} days"
