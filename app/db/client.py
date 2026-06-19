from __future__ import annotations

import os
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client


def upsert(table: str, records: list[dict], on_conflict: str) -> list[dict]:
    if not records:
        return []
    result = get_client().table(table).upsert(records, on_conflict=on_conflict).execute()
    return result.data or []


def select(table: str, filters: dict | None = None) -> list[dict]:
    q = get_client().table(table).select("*")
    for col, val in (filters or {}).items():
        q = q.eq(col, val)
    return q.execute().data or []


def select_view(view: str) -> list[dict]:
    return get_client().table(view).select("*").execute().data or []


def delete_where(table: str, filters: dict) -> None:
    q = get_client().table(table).delete()
    for col, val in filters.items():
        q = q.eq(col, val)
    q.execute()


def update_where(table: str, updates: dict, filters: dict) -> None:
    q = get_client().table(table).update(updates)
    for col, val in filters.items():
        q = q.eq(col, val)
    q.execute()


def rpc(fn: str, params: dict) -> list[dict]:
    result = get_client().rpc(fn, params).execute()
    return result.data or []
