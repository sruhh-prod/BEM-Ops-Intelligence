"""
Real Breezeway API adapter.
Fetches tasks across all linked properties; caches results for 1 hour.
"""
from __future__ import annotations

import os
import re
import time
import logging
import urllib.request
import json
from collections import defaultdict, Counter
from datetime import datetime, date, timedelta
from typing import Optional

log = logging.getLogger("bem.breezeway")

# ── Module-level cache ───────────────────────────────────────────────────────
_cache: dict = {"token": None, "token_ts": 0, "tasks": None, "tasks_ts": 0}
_TOKEN_TTL  = 23 * 3600   # refresh token every 23 h (API token expires in 24 h)
_TASKS_TTL  = 3600         # refresh task list every hour

BASE = "https://api.breezeway.io"


def _http_get(path: str, token: str) -> dict | list:
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={"Authorization": f"JWT {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _get_token() -> Optional[str]:
    client_id     = os.getenv("BREEZEWAY_CLIENT_ID")
    client_secret = os.getenv("BREEZEWAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        log.warning("BREEZEWAY_CLIENT_ID / BREEZEWAY_CLIENT_SECRET not set — skipping Breezeway")
        return None

    now = time.time()
    if _cache["token"] and (now - _cache["token_ts"]) < _TOKEN_TTL:
        return _cache["token"]

    log.info("Refreshing Breezeway access token")
    body = json.dumps({"client_id": client_id, "client_secret": client_secret}).encode()
    req  = urllib.request.Request(
        f"{BASE}/public/auth/v1/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())

    token = data.get("access_token")
    if token:
        _cache["token"]    = token
        _cache["token_ts"] = now
    return token


# ── Classification ───────────────────────────────────────────────────────────
_RULES = [
    ("Onboarding / Setup",    ["onboarding", "oboarding", "pre-launch", "post signage", "post evac",
                                "install tv", "install lock", "install schlage", "install new lockbox",
                                "grip tape", "hem tape", "place keys", "place owner ordered",
                                "verify airbnb", "count linens", "key copies", "install smoke",
                                "install carbon", "build bed", "bed frame install", "post unit signage"]),
    ("HVAC",                  ["hvac", r"a/c\b", "ac unit", "ac is", "air conditioner", "air condition",
                                "mini split", "freon", "air filter", "air return", "register",
                                "weatherstrip", "freeze prevention", "heat pump", "thermostat",
                                "ductwork", "furnace", r"\bcooling\b", r"\bheater\b", "attic fan",
                                r"ensure a/c", "routine hvac", "summer hvac", "air filter change",
                                "change air filter", "change: air filter", "clean air return",
                                "clean dirty registers", "bathroom vent", "dryer vent"]),
    ("Plumbing",              ["plumbing", "unclog", r"\bclog", r"\bdrain\b", "toilet", "faucet",
                                "shower", r"\bsink\b", r"\bpipe\b", r"\bleak\b", "leaking",
                                "water heater", "hot water", "sewage", "garbage disposal", "disposal",
                                "water quality", "check water", "water filter", "fridge filter",
                                "replace fridge filter", "pur pitcher", "filtered water pitcher",
                                "washer foul", "washing machine", "water damage", "standing water",
                                "burst", r"\bdrip\b", "caulk", "caulked"]),
    ("Electrical",            ["electrical", "electric", "outlet", "circuit", "breaker", "wiring",
                                "light bulb", r"\bbulb\b", "light not working", r"\blamp\b",
                                "light fixture", "ceiling fan", "ceiling light", "burning smell",
                                "smoke detector", "carbon monoxide", "fire alarm",
                                "battery in smoke", "change battery in smoke", "add bulbs"]),
    ("Appliance",             ["appliance", r"\bfridge\b", "refrigerator", "dishwasher",
                                "washing machine", r"\bdryer\b", r"\bwasher\b", r"\boven\b",
                                r"\bstove\b", "microwave", "ice maker", r"\brange\b", "broiler",
                                "broken washing", "broken fridge", "replace fridge", "refrigerator not"]),
    ("Lock / Access",         [r"\block\b", "lockbox", "schlage", "keypad", "access code", "door code",
                                "key copy", "key cut", "deadbolt", r"\blatch\b", r"\bgate\b", "hasp",
                                "door not opening", "door handle", "door knob", r"\bentry\b",
                                "door frame", "door sticks", "door hinge", "back door", "side gate",
                                "combination lock", "stiffen door"]),
    ("Internet / WiFi",       ["wifi", "wi-fi", "internet", "router", "network", "spotty",
                                "change internet account"]),
    ("Pest Control",          ["pest", "roach", "ant", "termite", r"\bbug\b", "insect", "rodent",
                                r"\brat\b", r"\bmouse\b", r"\bmice\b", "cockroach", "exterminator",
                                "spotted ants"]),
    ("Exterior / Grounds",    ["exterior", "lawn", "landscap", "bush", r"\btree\b", "gutter", "roof",
                                r"\bfence\b", "sidewalk", "driveway", "parking", "pool clean",
                                "pool noodle", "pool pump", "balcony", r"\bporch\b", r"\bstep\b",
                                r"\bstair\b", "handrail", r"\bturf\b"]),
    ("Safety",                ["safety", "smoke detector", "carbon monoxide", "fire extinguisher",
                                "fire alarm", "evacuation", "evac map", "grip tape", "trip hazard",
                                "unstable", "broken step", "safety grip"]),
    ("Furniture / Fixtures",  ["furniture", "sofa", "couch", r"\bchair\b", "wobbly chair", r"\btable\b",
                                "bed frame", "headboard", "mattress", "curtain", "curtain rod",
                                "blind", r"\bdrape\b", "shelving", "mirror", "closet door", "closet",
                                "armchair", "cushion", r"\bpillow\b", "throw pillow",
                                "repair: door frame", "door frame trim", "repair: closet",
                                "towel hook", "wall art", "fallen curtain"]),
    ("Cosmetic / Paint",      [r"\bpaint\b", r"\bpatch\b", "ceiling stain", r"\bstain\b", "peeling",
                                r"\bcrack\b", "touch up", "scuff", "scratch", "grout", r"\btile\b",
                                "floor damage", "flooring", "wall damage", "drywall"]),
    ("Supplies / Consumables",["consumable", "restock", "replenish", r"\bsupplies\b", "hand towel",
                                "kitchen utensil", "flatware", "wine glass", r"\bpot\b", r"\bpan\b",
                                "cookware", "first aid", "makeup towel", "batteries", "hair dryer",
                                r"\biron\b", "sound machine", "hangers", "replace missing",
                                "missing hair dryer", "missing iron", "broken wine glass"]),
    ("Inspection / QA",       ["inspection", "walkthrough", "quality control", r"\bqc\b",
                                "pre-inspection", "quarterly maintenance inspection",
                                "quarterly inspection", "q2 bem", "q3 bem", "q4 bem",
                                "audit", "appraisal", "annual.*inspection"]),
    ("Guest Request",         ["guest feedback", "guest request", "guest service", "emergency guest",
                                "owner request", "owner stay", "ready for dispatch"]),
    ("Other",                 []),
]


def _classify(name: str, description: str) -> str:
    text = f"{name} {description or ''}".lower()
    for cat, keywords in _RULES:
        for kw in keywords:
            try:
                if re.search(kw, text):
                    return cat
            except re.error:
                if kw in text:
                    return cat
    return "Other"


# ── Task fetching ────────────────────────────────────────────────────────────
def get_tasks() -> list[dict]:
    """Return classified maintenance tasks; uses 1-hour in-memory cache."""
    now = time.time()
    if _cache["tasks"] and (now - _cache["tasks_ts"]) < _TASKS_TTL:
        return _cache["tasks"]

    token = _get_token()
    if not token:
        return []

    try:
        log.info("Fetching Breezeway properties")
        prop_data = _http_get("public/inventory/v1/property", token)
        props = prop_data.get("results", [])
        linked = [p for p in props if p.get("reference_property_id")]
        log.info(f"Fetching tasks for {len(linked)} linked properties")

        all_tasks: list[dict] = []
        for p in linked:
            ref_id = p["reference_property_id"]
            try:
                data  = _http_get(
                    f"public/inventory/v1/task?reference_property_id={ref_id}&limit=100",
                    token,
                )
                for t in data.get("results", []):
                    t["_property_name"] = p["name"]
                    t["_bw_property_id"] = p["id"]
                    t["_category"] = _classify(
                        t.get("name", ""), t.get("description", "") or ""
                    )
                all_tasks.extend(data.get("results", []))
            except Exception as e:
                log.warning(f"Task fetch failed for {p['name']}: {e}")

        _cache["tasks"]    = all_tasks
        _cache["tasks_ts"] = now
        log.info(f"Breezeway: {len(all_tasks)} tasks cached")
        return all_tasks

    except Exception as e:
        log.error(f"Breezeway task fetch failed: {e}")
        return _cache["tasks"] or []
