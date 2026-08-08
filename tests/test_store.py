from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib
import sqlite3
import sys

import pytest


@pytest.fixture()
def store_module(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNI_DB_PATH", str(tmp_path / "store-test.db"))
    sys.modules.pop("omni_store", None)
    module = importlib.import_module("omni_store")
    monkeypatch.setattr(module, "LEGACY_VAULT_PATH", tmp_path / "missing-legacy-vault.json")
    module.init_db()
    return module


def test_newest_analysis_wins_when_timestamps_are_equal(store_module, monkeypatch):
    store = store_module
    client_id = "a" * 32
    fixed_timestamp = store.utc_now()
    monkeypatch.setattr(store, "utc_now", lambda: fixed_timestamp)

    store.save_analysis(
        client_id,
        None,
        "B2C",
        "instant",
        "same query",
        {},
        {"analysis_id": "first-analysis", "version": 1},
        {},
        "same-fingerprint",
    )
    store.save_analysis(
        client_id,
        None,
        "B2C",
        "instant",
        "same query",
        {},
        {"analysis_id": "second-analysis", "version": 2},
        {},
        "same-fingerprint",
    )

    cached = store.find_cached_analysis(client_id, "same-fingerprint", 24)
    assert cached is not None
    assert cached["id"] == "second-analysis"
    assert cached["data"]["version"] == 2


def test_stale_generation_release_cannot_delete_new_lease(store_module):
    store = store_module
    client_id = "b" * 32
    fingerprint = "same-generation"
    first_token = store.acquire_generation_lease(client_id, fingerprint, 30)
    assert isinstance(first_token, str)

    stale_at = (
        datetime.now(timezone.utc) - timedelta(minutes=5)
    ).isoformat(timespec="microseconds").replace("+00:00", "Z")
    with store.connection() as db:
        db.execute(
            "UPDATE generation_leases SET acquired_at=? WHERE lease_id=?",
            (stale_at, first_token),
        )

    second_token = store.acquire_generation_lease(client_id, fingerprint, 30)
    assert isinstance(second_token, str)
    assert second_token != first_token
    assert store.release_generation_lease(client_id, fingerprint, first_token) is False
    assert store.acquire_generation_lease(client_id, fingerprint, 30) is None
    assert store.release_generation_lease(client_id, fingerprint, second_token) is True
    assert isinstance(store.acquire_generation_lease(client_id, fingerprint, 30), str)


def test_old_generation_lease_schema_migrates_safely(tmp_path, monkeypatch):
    db_path = tmp_path / "old-schema.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE generation_leases (
                   client_id TEXT NOT NULL,
                   fingerprint TEXT NOT NULL,
                   acquired_at TEXT NOT NULL,
                   PRIMARY KEY (client_id, fingerprint)
               )"""
        )
        db.execute(
            "INSERT INTO generation_leases VALUES (?, ?, ?)",
            ("legacy-client", "legacy-fingerprint", "2020-01-01T00:00:00Z"),
        )

    monkeypatch.setenv("OMNI_DB_PATH", str(db_path))
    sys.modules.pop("omni_store", None)
    store = importlib.import_module("omni_store")
    store.init_db()
    with store.connection() as db:
        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(generation_leases)")
        }
        remaining = db.execute("SELECT COUNT(*) AS n FROM generation_leases").fetchone()["n"]
    assert "lease_id" in columns
    assert remaining == 0


def test_budget_reservation_is_atomic_and_fenced(store_module):
    store = store_module
    client_id = "c" * 32

    def reserve_once():
        return store.reserve_budget(client_id, "analysis", 1, 1, ttl_seconds=300)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reserve_once(), range(2)))
    tokens = [token for token in results if token is not None]
    assert len(tokens) == 1

    token = tokens[0]
    assert store.release_budget(token, "d" * 32) is False
    assert store.reserve_budget("d" * 32, "analysis", 1, 1) is None
    assert store.release_budget(token, client_id) is True
    assert isinstance(store.reserve_budget("d" * 32, "analysis", 1, 1), str)


def test_profile_memory_merge_is_atomic(store_module):
    store = store_module
    client_id = "e" * 32

    def remember(index: int):
        return store.update_profile_memory(
            client_id,
            "B2C",
            {f"skill_{index}": f"value_{index}"},
            f"context {index}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(remember, range(8)))
    facts = store.get_profile(client_id, "B2C")["memory"]["facts"]
    assert facts == {f"skill_{index}": f"value_{index}" for index in range(8)}


def test_store_forces_english_locale_and_exposes_redacted_health(store_module):
    store = store_module
    client_id = "f" * 32
    store.ensure_client(client_id, "fa")
    assert store.get_profile(client_id, "B2C")["locale"] == "en"
    assert store.storage_health() == {"ready": True}


def test_empty_authorized_legacy_claim_does_not_block_later_claim(store_module):
    store = store_module
    authorized_client = "1" * 32

    assert store.claim_legacy_analyses(authorized_client) == 0
    with store.connection() as db:
        marker = db.execute(
            "SELECT value FROM metadata WHERE key='legacy_vault_claimed'"
        ).fetchone()
    assert marker is None

    legacy_client = "legacy-local-vault"
    store.ensure_client(legacy_client)
    fixed_timestamp = "2026-01-02T03:04:05.000000Z"
    with store.connection() as db:
        db.execute(
            """INSERT INTO analyses
               (id, client_id, session_id, tier, horizon, query, answers_json,
                response_json, intelligence_json, fingerprint, created_at, updated_at)
               VALUES (?, ?, NULL, 'B2C', 'instant', ?, '{}', '{}', '{}', ?, ?, ?)""",
            (
                "synthetic-legacy-analysis",
                legacy_client,
                "Synthetic legacy query",
                "synthetic-legacy-fingerprint",
                fixed_timestamp,
                fixed_timestamp,
            ),
        )

    assert store.claim_legacy_analyses(authorized_client) == 1
    with store.connection() as db:
        analysis_owner = db.execute(
            "SELECT client_id FROM analyses WHERE id='synthetic-legacy-analysis'"
        ).fetchone()["client_id"]
        claimed_by = db.execute(
            "SELECT value FROM metadata WHERE key='legacy_vault_claimed'"
        ).fetchone()["value"]
    assert analysis_owner == authorized_client
    assert claimed_by == authorized_client
