"""
Sync pipeline.

Pulls data from adapters and writes to Supabase.
The pipeline owns all foreign-key resolution and upsert logic.
Adapters return normalized dicts; the pipeline cleans _private keys before insert.

Adapter-agnostic: the pipeline does not care whether data came from
Hostaway, Breezeway, or mock data. The adapters speak the same interface.
"""

from __future__ import annotations


import datetime
import logging

from adapters.base import BaseAdapter
from db import client as db

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_private(record: dict) -> dict:
    """Remove _ prefixed meta-keys before inserting into Supabase."""
    return {k: v for k, v in record.items() if not k.startswith("_")}


def _log_sync(source: str, entity: str, sync_type: str, started: datetime.datetime,
              fetched=0, created=0, updated=0, failed=0, error: str | None = None) -> None:
    completed   = datetime.datetime.utcnow()
    duration    = int((completed - started).total_seconds() * 1000)
    status      = "failed" if error else ("partial" if failed else "success")
    # sync_source enum only accepts 'breezeway' / 'hostaway' — normalise mock prefix
    log_source  = "breezeway" if source.startswith("mock_") else source
    try:
        db.upsert("sync_log", [{
            "source":          log_source,
            "entity_type":     entity,
            "sync_type":       sync_type,
            "status":          status,
            "records_fetched": fetched,
            "records_created": created,
            "records_updated": updated,
            "records_failed":  failed,
            "error_message":   error,
            "duration_ms":     duration,
            "started_at":      started.isoformat(),
            "completed_at":    completed.isoformat(),
        }], on_conflict="id")  # sync_log uses insert not upsert; id is generated
    except Exception as e:
        log.warning(f"Could not write sync_log: {e}")


def _upsert_with_log(table: str, records: list[dict], on_conflict: str,
                     source: str, entity: str, started: datetime.datetime) -> int:
    if not records:
        _log_sync(source, entity, "incremental", started, fetched=0)
        return 0
    try:
        clean  = [_strip_private(r) for r in records]
        result = db.upsert(table, clean, on_conflict=on_conflict)
        n      = len(result)
        _log_sync(source, entity, "full", started, fetched=len(records), created=n, updated=n)
        return n
    except Exception as e:
        _log_sync(source, entity, "full", started, fetched=len(records), failed=len(records), error=str(e))
        raise


# ---------------------------------------------------------------------------
# sync_properties
# ---------------------------------------------------------------------------

def sync_properties(adapter: BaseAdapter) -> int:
    """
    Sync properties from the given adapter into Supabase.

    Upserts on hostaway_id (Hostaway adapter) or breezeway_id (Breezeway adapter).
    When Breezeway is the source, it will also populate breezeway_id on existing rows.
    """
    log.info(f"[sync_properties] source={adapter.source_name()}")
    started = datetime.datetime.utcnow()

    properties = adapter.get_properties()
    log.info(f"[sync_properties] fetched {len(properties)} records")

    if not properties:
        _log_sync(adapter.source_name(), "properties", "full", started, fetched=0)
        return 0

    # Determine conflict key from source
    if adapter.source_name() in ("hostaway",):
        on_conflict = "hostaway_id"
    else:
        on_conflict = "breezeway_id"

    return _upsert_with_log("properties", properties, on_conflict,
                            adapter.source_name(), "properties", started)


# ---------------------------------------------------------------------------
# sync_reservations
# ---------------------------------------------------------------------------

def sync_reservations(adapter: BaseAdapter) -> int:
    """
    Sync reservations, resolving _property_ref to property UUID.
    """
    log.info(f"[sync_reservations] source={adapter.source_name()}")
    started      = datetime.datetime.utcnow()
    reservations = adapter.get_reservations()
    log.info(f"[sync_reservations] fetched {len(reservations)} records")

    if not reservations:
        _log_sync(adapter.source_name(), "reservations", "full", started, fetched=0)
        return 0

    # Build hostaway_id → property UUID lookup
    prop_map = _build_property_map()
    resolved, failed = [], 0

    for r in reservations:
        ref = r.get("_property_ref", {})
        prop_uuid = _resolve_property_uuid(ref, prop_map)
        if not prop_uuid:
            log.warning(f"[sync_reservations] cannot resolve property for ref={ref}, skipping")
            failed += 1
            continue
        r["property_id"] = prop_uuid
        resolved.append(r)

    if not resolved:
        _log_sync(adapter.source_name(), "reservations", "full", started,
                  fetched=len(reservations), failed=failed)
        return 0

    return _upsert_with_log("reservations", resolved, "hostaway_reservation_id",
                            adapter.source_name(), "reservations", started)


# ---------------------------------------------------------------------------
# sync_people
# ---------------------------------------------------------------------------

def sync_people(adapter: BaseAdapter) -> int:
    """Sync staff/people from Breezeway adapter."""
    log.info(f"[sync_people] source={adapter.source_name()}")
    started = datetime.datetime.utcnow()
    people  = adapter.get_people()
    log.info(f"[sync_people] fetched {len(people)} records")
    return _upsert_with_log("people", people, "breezeway_id",
                            adapter.source_name(), "people", started)


# ---------------------------------------------------------------------------
# sync_tasks
# ---------------------------------------------------------------------------

def sync_tasks(adapter: BaseAdapter) -> int:
    """
    Sync tasks from Breezeway adapter.
    Resolves _property_ref to property UUID.
    Resolves _assignee_ids to task_assignments rows.
    """
    log.info(f"[sync_tasks] source={adapter.source_name()}")
    started  = datetime.datetime.utcnow()
    tasks    = adapter.get_tasks()
    log.info(f"[sync_tasks] fetched {len(tasks)} records")

    if not tasks:
        _log_sync(adapter.source_name(), "tasks", "full", started, fetched=0)
        return 0

    prop_map    = _build_property_map()
    people_map  = _build_people_map()
    resolved, failed = [], 0

    for t in tasks:
        ref       = t.get("_property_ref", {})
        prop_uuid = _resolve_property_uuid(ref, prop_map)
        if not prop_uuid:
            log.warning(f"[sync_tasks] cannot resolve property for ref={ref}, skipping")
            failed += 1
            continue
        t["property_id"] = prop_uuid
        resolved.append(t)

    n = _upsert_with_log("tasks", resolved, "breezeway_task_id",
                         adapter.source_name(), "tasks", started)

    # After upsert, sync assignments
    _sync_task_assignments(resolved, people_map)
    return n


def _sync_task_assignments(tasks: list[dict], people_map: dict) -> None:
    """Resolve _assignee_ids and write task_assignments rows."""
    # Build task breezeway_id → uuid map from DB
    task_rows = db.select("tasks", {})
    task_map  = {r["breezeway_task_id"]: r["id"] for r in task_rows if r.get("breezeway_task_id")}

    assignments = []
    for t in tasks:
        task_uuid     = task_map.get(t.get("breezeway_task_id"))
        assignee_ids  = t.get("_assignee_ids", [])
        if not task_uuid or not assignee_ids:
            continue
        for bz_person_id in assignee_ids:
            person_uuid = people_map.get(bz_person_id)
            if not person_uuid:
                continue
            assignments.append({
                "task_id":   task_uuid,
                "person_id": person_uuid,
                "created_at": datetime.datetime.utcnow().isoformat(),
            })

    if assignments:
        try:
            db.get_client().table("task_assignments").upsert(
                assignments, on_conflict="task_id,person_id"
            ).execute()
            log.info(f"[sync_task_assignments] upserted {len(assignments)} assignment rows")
        except Exception as e:
            log.warning(f"[sync_task_assignments] failed: {e}")


# ---------------------------------------------------------------------------
# sync_task_comments
# ---------------------------------------------------------------------------

def sync_task_comments(adapter: BaseAdapter) -> int:
    """
    Sync task comments from Breezeway adapter.
    Resolves _task_ref and _person_ref to UUIDs.
    """
    log.info(f"[sync_task_comments] source={adapter.source_name()}")
    started  = datetime.datetime.utcnow()
    comments = adapter.get_task_comments()
    log.info(f"[sync_task_comments] fetched {len(comments)} records")

    if not comments:
        _log_sync(adapter.source_name(), "task_comments", "full", started, fetched=0)
        return 0

    # Build lookup maps
    task_rows   = db.select("tasks", {})
    task_map    = {r["breezeway_task_id"]: r["id"] for r in task_rows if r.get("breezeway_task_id")}
    people_map  = _build_people_map()

    resolved, failed = [], 0
    for c in comments:
        task_ref   = c.get("_task_ref", {})
        person_ref = c.get("_person_ref", {})

        bz_task_id = task_ref.get("breezeway_task_id")
        task_uuid  = task_map.get(bz_task_id)
        if not task_uuid:
            log.warning(f"[sync_task_comments] cannot resolve task {bz_task_id}, skipping")
            failed += 1
            continue

        bz_person_id = person_ref.get("breezeway_id")
        person_uuid  = people_map.get(bz_person_id)

        c["task_id"]   = task_uuid
        c["person_id"] = person_uuid  # allowed to be null
        resolved.append(c)

    return _upsert_with_log("task_comments", resolved, "breezeway_comment_id",
                            adapter.source_name(), "task_comments", started)


# ---------------------------------------------------------------------------
# Lookup map builders
# ---------------------------------------------------------------------------

def _build_property_map() -> dict:
    """Returns {hostaway_id: uuid, breezeway_id: uuid} lookup."""
    rows = db.select("properties", {})
    m = {}
    for r in rows:
        if r.get("hostaway_id"):
            m[("hostaway_id", r["hostaway_id"])] = r["id"]
        if r.get("breezeway_id"):
            m[("breezeway_id", r["breezeway_id"])] = r["id"]
    return m


def _resolve_property_uuid(ref: dict, prop_map: dict) -> str | None:
    if "hostaway_id" in ref:
        return prop_map.get(("hostaway_id", ref["hostaway_id"]))
    if "breezeway_id" in ref:
        return prop_map.get(("breezeway_id", ref["breezeway_id"]))
    return None


def _build_people_map() -> dict:
    """Returns {breezeway_id: uuid} lookup."""
    rows = db.select("people", {})
    return {r["breezeway_id"]: r["id"] for r in rows if r.get("breezeway_id")}


# ---------------------------------------------------------------------------
# Full sync orchestrator
# ---------------------------------------------------------------------------

def run_full_sync(hostaway_adapter: BaseAdapter, breezeway_adapter: BaseAdapter) -> dict:
    """
    Execute the complete sync pipeline in dependency order.
    Returns a summary dict of record counts.
    """
    results = {}

    log.info("=" * 60)
    log.info("SYNC PIPELINE START")
    log.info("=" * 60)

    # Layer 1: Properties (Hostaway is source)
    results["properties"]   = sync_properties(hostaway_adapter)

    # Layer 2: Reservations (Hostaway is source)
    results["reservations"] = sync_reservations(hostaway_adapter)

    # Layer 3: People (Breezeway is source)
    results["people"]       = sync_people(breezeway_adapter)

    # Layer 4: Tasks (Breezeway is source)
    results["tasks"]        = sync_tasks(breezeway_adapter)

    # Layer 5: Task comments (Breezeway is source)
    results["task_comments"] = sync_task_comments(breezeway_adapter)

    log.info("SYNC PIPELINE COMPLETE — %s", results)
    return results
