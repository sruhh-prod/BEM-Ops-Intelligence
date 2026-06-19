"""
Breezeway source adapter — STUB (mock data).

This stub implements the exact same interface as the future BreezewayAdapter.
All records are tagged source='mock_breezeway' so they are easy to identify
and purge once real Breezeway credentials are connected.

REPLACING THIS STUB:
  1. Create adapters/breezeway.py implementing BaseAdapter
  2. Change the import in pipeline/sync.py from:
       from adapters.breezeway_stub import BreezewayAdapterStub as BreezewayAdapter
     to:
       from adapters.breezeway import BreezewayAdapter
  3. Pass real client_id and client_secret in main.py
  4. Run: python main.py sync --source breezeway --purge-mock

The sync pipeline, risk engine, and dashboard do not change.

MOCK SCENARIOS (designed to trigger meaningful risk engine alerts):
  Scenario A — Overdue maintenance, unassigned
  Scenario B — Housekeeping task, stale (no activity in 3 days)
  Scenario C — Urgent clean scheduled today, assignee did not start
  Scenario D — Inspection overdue before arrival window
  Scenario E — Normal completed tasks (healthy baseline)
  Scenario F — Quick wins: easy tasks, assigned, due this week
"""

from __future__ import annotations


import datetime
import random

from .base import BaseAdapter

# Stable seed so mock data is deterministic across runs.
_RNG = random.Random(42)

# Mock staff — breezeway_ids in 9000 range (won't collide with real Breezeway IDs)
_MOCK_PEOPLE = [
    {"breezeway_id": 9001, "full_name": "Maria Santos",   "role": "housekeeper",  "subdepartment_name": "Housekeeping"},
    {"breezeway_id": 9002, "full_name": "James Williams",  "role": "housekeeper",  "subdepartment_name": "Housekeeping"},
    {"breezeway_id": 9003, "full_name": "Robert Chen",     "role": "maintenance",  "subdepartment_name": "Maintenance"},
    {"breezeway_id": 9004, "full_name": "Diana Torres",    "role": "inspector",    "subdepartment_name": "Inspections"},
    {"breezeway_id": 9005, "full_name": "Kevin Park",      "role": "manager",      "subdepartment_name": "Operations"},
]

_TODAY      = datetime.date.today()
_YESTERDAY  = _TODAY - datetime.timedelta(days=1)
_TOMORROW   = _TODAY + datetime.timedelta(days=1)
_IN_2_DAYS  = _TODAY + datetime.timedelta(days=2)
_IN_5_DAYS  = _TODAY + datetime.timedelta(days=5)
_3_DAYS_AGO = _TODAY - datetime.timedelta(days=3)
_4_DAYS_AGO = _TODAY - datetime.timedelta(days=4)

_STALE_UPDATED_AT = (
    datetime.datetime.utcnow() - datetime.timedelta(hours=72)
).isoformat() + "Z"

_OLD_UPDATED_AT = (
    datetime.datetime.utcnow() - datetime.timedelta(hours=96)
).isoformat() + "Z"


def _dt(d: datetime.date) -> str:
    return d.isoformat()


class BreezewayAdapterStub(BaseAdapter):
    """
    Mock Breezeway adapter.

    Pass a list of hostaway_ids available in the database so that mock tasks
    can be linked to real properties.
    """

    def __init__(self, property_hostaway_ids: list[int] | None = None):
        # Use whatever real property IDs were synced from Hostaway.
        # Fall back to known IDs from the BEM account if none provided.
        self._prop_ids = property_hostaway_ids or [
            102965, 102967, 102969, 102983, 107021,
            107022, 109923, 111954, 112191, 112192,
        ]

    def source_name(self) -> str:
        return "mock_breezeway"

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------

    def get_people(self) -> list[dict]:
        return [
            {**p, "is_active": True, "breezeway_synced_at": datetime.datetime.utcnow().isoformat()}
            for p in _MOCK_PEOPLE
        ]

    # ------------------------------------------------------------------
    # Properties (Breezeway stub does not own property records)
    # ------------------------------------------------------------------

    def get_properties(self) -> list[dict]:
        # When the real Breezeway adapter ships, it will return property
        # records enriched with ops data (access codes, notes, etc.).
        # The stub returns nothing — Hostaway is the properties source for now.
        return []

    # ------------------------------------------------------------------
    # Reservations (Breezeway stub does not own reservations)
    # ------------------------------------------------------------------

    def get_reservations(self) -> list[dict]:
        # Reservations come from Hostaway. Return nothing here.
        return []

    # ------------------------------------------------------------------
    # Tasks — the core Breezeway data
    # ------------------------------------------------------------------

    def get_tasks(self) -> list[dict]:
        ids = self._prop_ids
        n   = len(ids)

        tasks = [
            # ---- Scenario A: Overdue maintenance, unassigned ----------------
            {
                "breezeway_task_id":  9001001,
                "department":         "maintenance",
                "task_name":          "HVAC not cooling — unit 1",
                "description":        "Guest complaint: AC stopped working. Needs inspection and repair.",
                "priority":           "urgent",
                "status":             "pending",
                "scheduled_date":     _dt(_YESTERDAY),
                "due_date":           _dt(_YESTERDAY),
                "updated_at":         _OLD_UPDATED_AT,
                "_property_ref":      {"hostaway_id": ids[0 % n]},
                "_assignee_ids":      [],   # intentionally unassigned
            },

            # ---- Scenario B: Stale housekeeping (no activity in 72h) --------
            {
                "breezeway_task_id":  9001002,
                "department":         "housekeeping",
                "task_name":          "Full clean — 3BR/2BA turnover",
                "description":        "Full turnover clean. Previous guests checked out this morning.",
                "priority":           "high",
                "status":             "assigned",
                "scheduled_date":     _dt(_TODAY),
                "due_date":           _dt(_TODAY),
                "updated_at":         _STALE_UPDATED_AT,
                "estimated_hours":    3.0,
                "_property_ref":      {"hostaway_id": ids[1 % n]},
                "_assignee_ids":      [9001],
            },

            # ---- Scenario C: Urgent clean today, not started ----------------
            {
                "breezeway_task_id":  9001003,
                "department":         "housekeeping",
                "task_name":          "Pre-arrival clean — guests arrive 3 PM",
                "description":        "Standard clean. Linen change, restock amenities, verify access code.",
                "priority":           "urgent",
                "status":             "assigned",
                "scheduled_date":     _dt(_TODAY),
                "due_date":           _dt(_TODAY),
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "estimated_hours":    2.0,
                "_property_ref":      {"hostaway_id": ids[2 % n]},
                "_assignee_ids":      [9002],
            },

            # ---- Scenario D: Inspection overdue — arrival tomorrow ----------
            {
                "breezeway_task_id":  9001004,
                "department":         "inspection",
                "task_name":          "Pre-arrival property inspection",
                "description":        "Check all appliances, HVAC, plumbing, and verify access code before guest arrival.",
                "priority":           "high",
                "status":             "pending",
                "scheduled_date":     _dt(_YESTERDAY),
                "due_date":           _dt(_TODAY),
                "updated_at":         _OLD_UPDATED_AT,
                "estimated_hours":    1.0,
                "_property_ref":      {"hostaway_id": ids[3 % n]},
                "_assignee_ids":      [9004],
            },

            # ---- Scenario E: Completed tasks (healthy — no alerts) ----------
            {
                "breezeway_task_id":  9001005,
                "department":         "housekeeping",
                "task_name":          "Full clean — 2BR/1BA",
                "priority":           "normal",
                "status":             "completed",
                "scheduled_date":     _dt(_TODAY),
                "due_date":           _dt(_TODAY),
                "finished_at":        datetime.datetime.utcnow().isoformat(),
                "actual_hours":       2.5,
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[4 % n]},
                "_assignee_ids":      [9001],
            },
            {
                "breezeway_task_id":  9001006,
                "department":         "inspection",
                "task_name":          "Post-clean inspection",
                "priority":           "normal",
                "status":             "approved",
                "scheduled_date":     _dt(_TODAY),
                "due_date":           _dt(_TODAY),
                "finished_at":        datetime.datetime.utcnow().isoformat(),
                "actual_hours":       0.5,
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[4 % n]},
                "_assignee_ids":      [9004],
            },

            # ---- Scenario F: Quick wins (easy, assigned, this week) ---------
            {
                "breezeway_task_id":  9001007,
                "department":         "maintenance",
                "task_name":          "Replace burnt-out lightbulbs — kitchen",
                "description":        "3 bulbs out in kitchen. Replacements in supply closet, shelf 2.",
                "priority":           "low",
                "status":             "assigned",
                "scheduled_date":     _dt(_TOMORROW),
                "due_date":           _dt(_TOMORROW),
                "estimated_hours":    0.5,
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[5 % n]},
                "_assignee_ids":      [9003],
            },
            {
                "breezeway_task_id":  9001008,
                "department":         "housekeeping",
                "task_name":          "Restock guest amenities — shampoo, conditioner",
                "description":        "Running low on shampoo and conditioner. Restock from supply room.",
                "priority":           "normal",
                "status":             "pending",
                "scheduled_date":     _dt(_IN_2_DAYS),
                "due_date":           _dt(_IN_2_DAYS),
                "estimated_hours":    0.25,
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[6 % n]},
                "_assignee_ids":      [9002],
            },
            {
                "breezeway_task_id":  9001009,
                "department":         "maintenance",
                "task_name":          "Test smoke detectors — quarterly check",
                "description":        "Quarterly safety check. Test all smoke and CO detectors.",
                "priority":           "normal",
                "status":             "assigned",
                "scheduled_date":     _dt(_IN_5_DAYS),
                "due_date":           _dt(_IN_5_DAYS),
                "estimated_hours":    0.5,
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[7 % n]},
                "_assignee_ids":      [9003],
            },
            {
                "breezeway_task_id":  9001010,
                "department":         "housekeeping",
                "task_name":          "Deep clean — refrigerator and oven",
                "description":        "Monthly deep clean of appliances. Previous guest reported sticky oven.",
                "priority":           "normal",
                "status":             "pending",
                "scheduled_date":     _dt(_IN_5_DAYS),
                "due_date":           _dt(_IN_5_DAYS),
                "estimated_hours":    1.5,
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[8 % n]},
                "_assignee_ids":      [9001],
            },

            # ---- Extra: Safety task, urgent, unassigned --------------------
            {
                "breezeway_task_id":  9001011,
                "department":         "safety",
                "task_name":          "Loose handrail on front steps — hazard",
                "description":        "Guest reported wobbly handrail on exterior front steps. Repair before next arrival.",
                "priority":           "urgent",
                "status":             "pending",
                "scheduled_date":     _dt(_TOMORROW),
                "due_date":           _dt(_TOMORROW),
                "updated_at":         datetime.datetime.utcnow().isoformat(),
                "_property_ref":      {"hostaway_id": ids[9 % n]},
                "_assignee_ids":      [],  # unassigned — triggers risk
            },
        ]

        # Add standard metadata to every task
        now = datetime.datetime.utcnow().isoformat()
        for t in tasks:
            t.setdefault("created_at", now)
            t.setdefault("description", None)
            t.setdefault("priority", "normal")
            t.setdefault("estimated_hours", None)
            t.setdefault("actual_hours", None)
            t.setdefault("finished_at", None)
            t.setdefault("started_at", None)
            t.setdefault("is_stale", False)
            t.setdefault("blocks_arrival", False)
            t["breezeway_synced_at"] = now

        return tasks

    # ------------------------------------------------------------------
    # Task comments
    # ------------------------------------------------------------------

    def get_task_comments(self) -> list[dict]:
        now = datetime.datetime.utcnow()

        return [
            {
                "breezeway_comment_id": 9901001,
                "comment_text":         "Checked the unit — compressor is completely dead. Need to order replacement. Part # CR-4400B.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=48)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001001},
                "_person_ref":          {"breezeway_id": 9003},
            },
            {
                "breezeway_comment_id": 9901002,
                "comment_text":         "Part ordered. ETA 3 business days. Owner notified.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=46)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001001},
                "_person_ref":          {"breezeway_id": 9005},
            },
            {
                "breezeway_comment_id": 9901003,
                "comment_text":         "Arrived at property. Previous guest left a mess — extra trash bags needed. Starting now.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=73)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001002},
                "_person_ref":          {"breezeway_id": 9001},
            },
            {
                "breezeway_comment_id": 9901004,
                "comment_text":         "Had to leave mid-clean — family emergency. Will return tomorrow morning.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=72)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001002},
                "_person_ref":          {"breezeway_id": 9001},
            },
            {
                "breezeway_comment_id": 9901005,
                "comment_text":         "Access code on the door is not working — tried 4 times. Calling office.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=2)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001003},
                "_person_ref":          {"breezeway_id": 9002},
            },
            {
                "breezeway_comment_id": 9901006,
                "comment_text":         "Arrived to inspect. Property looks clean. One issue: garbage disposal not working.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=96)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001004},
                "_person_ref":          {"breezeway_id": 9004},
            },
            {
                "breezeway_comment_id": 9901007,
                "comment_text":         "Clean complete. All rooms done. Left fresh flowers on table. ✓",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(hours=1)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001005},
                "_person_ref":          {"breezeway_id": 9001},
            },
            {
                "breezeway_comment_id": 9901008,
                "comment_text":         "Handrail is definitely a liability. Three screws stripped. Needs full replacement not patch.",
                "is_system_generated":  False,
                "breezeway_created_at": (now - datetime.timedelta(minutes=30)).isoformat(),
                "_task_ref":            {"breezeway_task_id": 9001011},
                "_person_ref":          {"breezeway_id": 9005},
            },
        ]
