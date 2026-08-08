"""Durable local persistence for AIONEX.

The first prototype stored every signal in one JSON file.  That works for a
single demo request, but concurrent writes can corrupt it and it cannot model
profiles, conversations, goals, or usage.  This module keeps the deployment
zero-config by using SQLite while giving every write a transaction and every
user an isolated anonymous namespace.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from typing import Any, Iterator


BASE_DIR = Path(__file__).resolve().parent
_configured_db_path = Path(os.getenv("OMNI_DB_PATH", "omni.db"))
DB_PATH = (
    _configured_db_path if _configured_db_path.is_absolute()
    else BASE_DIR / _configured_db_path
).resolve()
LEGACY_VAULT_PATH = BASE_DIR / "signals_vault.json"
_WRITE_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def storage_health() -> dict[str, Any]:
    """Return a redacted, non-throwing readiness result for the health API."""
    try:
        with connection() as db:
            row = db.execute("SELECT 1 AS ok").fetchone()
        return {"ready": bool(row and row["ok"] == 1)}
    except (OSError, sqlite3.Error):
        return {"ready": False}


def init_db() -> None:
    """Create/upgrade the local schema and import the legacy vault once."""
    with _WRITE_LOCK, connection() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY,
                locale TEXT NOT NULL DEFAULT 'en',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profiles (
                client_id TEXT NOT NULL,
                tier TEXT NOT NULL CHECK (tier IN ('B2C', 'B2B')),
                memory_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (client_id, tier),
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS intake_sessions (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                tier TEXT NOT NULL CHECK (tier IN ('B2C', 'B2B')),
                horizon TEXT NOT NULL CHECK (horizon IN ('instant', 'strategic')),
                query TEXT NOT NULL,
                questions_json TEXT NOT NULL,
                answers_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'clarifying',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                session_id TEXT,
                tier TEXT NOT NULL CHECK (tier IN ('B2C', 'B2B')),
                horizon TEXT NOT NULL CHECK (horizon IN ('instant', 'strategic')),
                query TEXT NOT NULL,
                answers_json TEXT NOT NULL DEFAULT '{}',
                response_json TEXT NOT NULL,
                intelligence_json TEXT NOT NULL DEFAULT '{}',
                fingerprint TEXT,
                cached_hits INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_analyses_client_created
                ON analyses(client_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_analyses_fingerprint
                ON analyses(client_id, fingerprint, created_at DESC);

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                client_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_analysis_created
                ON messages(analysis_id, created_at ASC);

            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                analysis_id TEXT,
                tier TEXT NOT NULL CHECK (tier IN ('B2C', 'B2B')),
                title TEXT NOT NULL,
                blueprint_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'paused', 'completed', 'archived')),
                progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
                target_date TEXT,
                next_check_in TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_goals_client_updated
                ON goals(client_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                analysis_id TEXT,
                metric TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                resolve_at TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_predictions_due
                ON predictions(status, resolve_at);
            CREATE INDEX IF NOT EXISTS idx_predictions_client_created
                ON predictions(client_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS deep_dive_cache (
                cache_key TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS usage_events (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cached INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_usage_client_created
                ON usage_events(client_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS generation_leases (
                client_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                lease_id TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                PRIMARY KEY (client_id, fingerprint),
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS budget_reservations (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_budget_reservations_client_endpoint
                ON budget_reservations(client_id, endpoint, created_at);
            CREATE INDEX IF NOT EXISTS idx_budget_reservations_endpoint
                ON budget_reservations(endpoint, created_at);
            """
        )
        message_columns = {row["name"] for row in db.execute("PRAGMA table_info(messages)").fetchall()}
        if "metadata_json" not in message_columns:
            db.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
        lease_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(generation_leases)").fetchall()
        }
        if "lease_id" not in lease_columns:
            # Leases are ephemeral. Existing rows cannot be released safely
            # without a fencing token, so invalidate them during the migration.
            db.execute("ALTER TABLE generation_leases ADD COLUMN lease_id TEXT")
            db.execute("DELETE FROM generation_leases")
        # Locale is presentation state, not user-authored content. Normalize
        # existing rows as part of the English-only product migration.
        db.execute("UPDATE clients SET locale='en' WHERE locale <> 'en'")
    _migrate_legacy_vault()


def _upsert_client(
    db: sqlite3.Connection,
    client_id: str,
    locale: str,
    now: str,
) -> None:
    _ = locale  # Kept for call-site compatibility; product locale is fixed.
    db.execute(
        """INSERT INTO clients(client_id, locale, created_at, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(client_id) DO UPDATE
           SET locale=CASE
               WHEN ? = '' THEN clients.locale
               ELSE excluded.locale
           END,
               updated_at=excluded.updated_at""",
        (client_id, "en", now, now, "en"),
    )


def ensure_client(client_id: str, locale: str | None = None) -> None:
    now = utc_now()
    with _WRITE_LOCK, connection() as db:
        _upsert_client(db, client_id, locale or "", now)


def _migrate_legacy_vault() -> None:
    if not LEGACY_VAULT_PATH.exists():
        return
    with connection() as db:
        if db.execute("SELECT value FROM metadata WHERE key='legacy_vault_imported'").fetchone():
            return
    try:
        rows = json.loads(LEGACY_VAULT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rows = []
    if not isinstance(rows, list):
        rows = []

    legacy_client = "legacy-local-vault"
    ensure_client(legacy_client, "en")
    with _WRITE_LOCK, connection() as db:
        for index, payload in enumerate(rows):
            if not isinstance(payload, dict):
                continue
            stable = hashlib.sha256(_dumps(payload).encode("utf-8")).hexdigest()[:24]
            analysis_id = f"legacy-{stable}"
            timestamp = payload.get("timestamp") or utc_now()
            db.execute(
                """INSERT OR IGNORE INTO analyses
                   (id, client_id, session_id, tier, horizon, query, answers_json,
                    response_json, intelligence_json, fingerprint, created_at, updated_at)
                   VALUES (?, ?, NULL, ?, ?, ?, '{}', ?, ?, ?, ?, ?)""",
                (
                    analysis_id,
                    legacy_client,
                    payload.get("tier") if payload.get("tier") in {"B2C", "B2B"} else "B2C",
                    payload.get("horizon_mode") if payload.get("horizon_mode") in {"instant", "strategic"} else "instant",
                    str(payload.get("original_query") or "Legacy signal"),
                    _dumps(payload),
                    _dumps(payload.get("intelligence_snapshot") or {}),
                    f"legacy-{index}-{stable}",
                    str(timestamp),
                    str(timestamp),
                ),
            )
        db.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('legacy_vault_imported', ?)",
            (utc_now(),),
        )


def create_intake_session(
    client_id: str,
    tier: str,
    horizon: str,
    query: str,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_client(client_id)
    session_id = uuid.uuid4().hex
    now = utc_now()
    with _WRITE_LOCK, connection() as db:
        db.execute(
            """INSERT INTO intake_sessions
               (id, client_id, tier, horizon, query, questions_json, answers_json, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '{}', 'clarifying', ?, ?)""",
            (session_id, client_id, tier, horizon, query, _dumps(questions), now, now),
        )
    return {
        "id": session_id,
        "client_id": client_id,
        "tier": tier,
        "horizon": horizon,
        "query": query,
        "questions": questions,
        "answers": {},
        "status": "clarifying",
        "created_at": now,
    }


def get_intake_session(session_id: str, client_id: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM intake_sessions WHERE id=? AND client_id=?",
            (session_id, client_id),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "tier": row["tier"],
        "horizon": row["horizon"],
        "query": row["query"],
        "questions": _loads(row["questions_json"], []),
        "answers": _loads(row["answers_json"], {}),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def complete_intake_session(session_id: str, client_id: str, answers: dict[str, Any]) -> bool:
    now = utc_now()
    with _WRITE_LOCK, connection() as db:
        cur = db.execute(
            """UPDATE intake_sessions
               SET answers_json=?, status='ready', updated_at=?
               WHERE id=? AND client_id=? AND status IN ('clarifying', 'ready')""",
            (_dumps(answers), now, session_id, client_id),
        )
    return cur.rowcount == 1


def get_profile(client_id: str, tier: str) -> dict[str, Any]:
    ensure_client(client_id)
    with connection() as db:
        row = db.execute(
            "SELECT memory_json, updated_at FROM profiles WHERE client_id=? AND tier=?",
            (client_id, tier),
        ).fetchone()
    memory = _loads(row["memory_json"], {}) if row else {}
    return {
        "client_id": client_id,
        "tier": tier,
        "locale": "en",
        "memory": memory,
        "updated_at": row["updated_at"] if row else None,
    }


def update_profile_memory(
    client_id: str,
    tier: str,
    facts: dict[str, Any],
    query: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    with _WRITE_LOCK, connection() as db:
        # A write reservation before the SELECT makes the whole merge atomic
        # across threads and separate application processes using this DB.
        db.execute("BEGIN IMMEDIATE")
        _upsert_client(db, client_id, "", now)
        row = db.execute(
            "SELECT memory_json FROM profiles WHERE client_id=? AND tier=?",
            (client_id, tier),
        ).fetchone()
        current = _loads(row["memory_json"], {}) if row else {}
        if not isinstance(current, dict):
            current = {}
        current_facts = current.get("facts")
        if not isinstance(current_facts, dict):
            current_facts = {}
        else:
            current_facts = dict(current_facts)
        for key, value in facts.items():
            if value is not None and str(value).strip():
                current_facts[str(key)[:64]] = str(value).strip()[:800]
        recent = current.get("recent_contexts")
        if not isinstance(recent, list):
            recent = []
        if query:
            bounded_query = query[:500]
            recent = [bounded_query] + [item for item in recent if item != bounded_query]
        memory = {
            "facts": dict(list(current_facts.items())[-30:]),
            "recent_contexts": recent[:5],
        }
        db.execute(
            """INSERT INTO profiles(client_id, tier, memory_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(client_id, tier) DO UPDATE
               SET memory_json=excluded.memory_json, updated_at=excluded.updated_at""",
            (client_id, tier, _dumps(memory), now, now),
        )
    return memory


def clear_profile_memory(client_id: str, tier: str) -> bool:
    with _WRITE_LOCK, connection() as db:
        cur = db.execute("DELETE FROM profiles WHERE client_id=? AND tier=?", (client_id, tier))
    return cur.rowcount > 0


def analysis_fingerprint(query: str, tier: str, horizon: str, answers: dict[str, Any]) -> str:
    canonical = _dumps(
        {
            "query": " ".join(query.lower().split()),
            "tier": tier,
            "horizon": horizon,
            "answers": answers,
        }
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def find_cached_analysis(
    client_id: str,
    fingerprint: str,
    max_age_hours: int = 24,
) -> dict[str, Any] | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat().replace("+00:00", "Z")
    with connection() as db:
        row = db.execute(
            """SELECT * FROM analyses
               WHERE client_id=? AND fingerprint=? AND created_at>=?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (client_id, fingerprint, cutoff),
        ).fetchone()
    if not row:
        return None
    with _WRITE_LOCK, connection() as db:
        db.execute("UPDATE analyses SET cached_hits=cached_hits+1 WHERE id=?", (row["id"],))
    return _analysis_row(row)


def save_analysis(
    client_id: str,
    session_id: str | None,
    tier: str,
    horizon: str,
    query: str,
    answers: dict[str, Any],
    response: dict[str, Any],
    intelligence: dict[str, Any],
    fingerprint: str,
) -> str:
    ensure_client(client_id)
    analysis_id = str(response.get("analysis_id") or uuid.uuid4().hex)
    now = utc_now()
    response = dict(response)
    response["analysis_id"] = analysis_id
    response.setdefault("created_at", now)
    with _WRITE_LOCK, connection() as db:
        db.execute(
            """INSERT INTO analyses
               (id, client_id, session_id, tier, horizon, query, answers_json,
                response_json, intelligence_json, fingerprint, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id,
                client_id,
                session_id,
                tier,
                horizon,
                query,
                _dumps(answers),
                _dumps(response),
                _dumps(intelligence),
                fingerprint,
                now,
                now,
            ),
        )
    return analysis_id


def _analysis_row(row: sqlite3.Row) -> dict[str, Any]:
    response = _loads(row["response_json"], {})
    response.setdefault("analysis_id", row["id"])
    response.setdefault("original_query", row["query"])
    response.setdefault("tier", row["tier"])
    response.setdefault("horizon_mode", row["horizon"])
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "session_id": row["session_id"],
        "tier": row["tier"],
        "horizon": row["horizon"],
        "query": row["query"],
        "answers": _loads(row["answers_json"], {}),
        "data": response,
        "intelligence": _loads(row["intelligence_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "cached_hits": row["cached_hits"],
    }


def get_analysis(analysis_id: str, client_id: str | None = None) -> dict[str, Any] | None:
    sql = "SELECT * FROM analyses WHERE id=?"
    params: tuple[Any, ...] = (analysis_id,)
    if client_id:
        sql += " AND client_id=?"
        params = (analysis_id, client_id)
    with connection() as db:
        row = db.execute(sql, params).fetchone()
    return _analysis_row(row) if row else None


def list_analyses(client_id: str, limit: int = 30, include_legacy: bool = False) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    with connection() as db:
        if include_legacy:
            rows = db.execute(
                """SELECT * FROM analyses WHERE client_id IN (?, 'legacy-local-vault')
                   ORDER BY created_at DESC LIMIT ?""",
                (client_id, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM analyses WHERE client_id=? ORDER BY created_at DESC LIMIT ?",
                (client_id, limit),
            ).fetchall()
    return [_analysis_row(row) for row in rows]


def claim_legacy_analyses(client_id: str) -> int:
    """Attach imported pre-v2 analyses after explicit user authorization."""
    ensure_client(client_id)
    with _WRITE_LOCK, connection() as db:
        claimed = db.execute("SELECT value FROM metadata WHERE key='legacy_vault_claimed'").fetchone()
        if claimed:
            return 0
        cur = db.execute(
            "UPDATE analyses SET client_id=?, updated_at=? WHERE client_id='legacy-local-vault'",
            (client_id, utc_now()),
        )
        if cur.rowcount > 0:
            db.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('legacy_vault_claimed', ?)",
                (client_id,),
            )
    return cur.rowcount


def add_message(
    analysis_id: str,
    client_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message_id = uuid.uuid4().hex
    now = utc_now()
    with _WRITE_LOCK, connection() as db:
        db.execute(
            """INSERT INTO messages(id, analysis_id, client_id, role, content, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message_id, analysis_id, client_id, role, content, _dumps(metadata or {}), now),
        )
    return {"id": message_id, "role": role, "content": content, "metadata": metadata or {}, "created_at": now}


def list_messages(analysis_id: str, client_id: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 50))
    with connection() as db:
        rows = db.execute(
            """SELECT * FROM (
                   SELECT rowid AS sequence, id, role, content, metadata_json, created_at
                   FROM messages WHERE analysis_id=? AND client_id=?
                   ORDER BY rowid DESC LIMIT ?
               ) ORDER BY sequence ASC""",
            (analysis_id, client_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"], "role": row["role"], "content": row["content"],
            "metadata": _loads(row["metadata_json"], {}), "created_at": row["created_at"],
        }
        for row in rows
    ]


def create_goal(
    client_id: str,
    analysis_id: str | None,
    tier: str,
    title: str,
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    ensure_client(client_id)
    goal_id = uuid.uuid4().hex
    now = utc_now()
    target_date = blueprint.get("target_date") or blueprint.get("deadline")
    next_check_in = blueprint.get("next_check_in")
    with _WRITE_LOCK, connection() as db:
        if analysis_id:
            duplicate = db.execute(
                "SELECT id FROM goals WHERE client_id=? AND analysis_id=? AND status!='archived'",
                (client_id, analysis_id),
            ).fetchone()
            if duplicate:
                existing = get_goal(duplicate["id"], client_id)
                if existing:
                    return existing
        db.execute(
            """INSERT INTO goals
               (id, client_id, analysis_id, tier, title, blueprint_json, status,
                progress, target_date, next_check_in, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?, ?, ?, ?)""",
            (
                goal_id,
                client_id,
                analysis_id,
                tier,
                title[:180],
                _dumps(blueprint),
                target_date,
                next_check_in,
                now,
                now,
            ),
        )
    return get_goal(goal_id, client_id) or {}


def _goal_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "analysis_id": row["analysis_id"],
        "tier": row["tier"],
        "title": row["title"],
        "blueprint": _loads(row["blueprint_json"], {}),
        "status": row["status"],
        "progress": row["progress"],
        "target_date": row["target_date"],
        "next_check_in": row["next_check_in"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_goal(goal_id: str, client_id: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute("SELECT * FROM goals WHERE id=? AND client_id=?", (goal_id, client_id)).fetchone()
    return _goal_row(row) if row else None


def list_goals(client_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    with connection() as db:
        if include_archived:
            rows = db.execute(
                "SELECT * FROM goals WHERE client_id=? ORDER BY updated_at DESC", (client_id,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM goals WHERE client_id=? AND status!='archived' ORDER BY updated_at DESC",
                (client_id,),
            ).fetchall()
    return [_goal_row(row) for row in rows]


def update_goal(
    goal_id: str,
    client_id: str,
    progress: int | None = None,
    status: str | None = None,
    next_check_in: str | None = None,
) -> dict[str, Any] | None:
    current = get_goal(goal_id, client_id)
    if not current:
        return None
    new_progress = current["progress"] if progress is None else max(0, min(100, int(progress)))
    new_status = status or current["status"]
    if new_progress == 100 and status is None:
        new_status = "completed"
    allowed = {"active", "paused", "completed", "archived"}
    if new_status not in allowed:
        raise ValueError("Invalid goal status")
    check_in = current["next_check_in"] if next_check_in is None else next_check_in
    with _WRITE_LOCK, connection() as db:
        db.execute(
            """UPDATE goals SET progress=?, status=?, next_check_in=?, updated_at=?
               WHERE id=? AND client_id=?""",
            (new_progress, new_status, check_in, utc_now(), goal_id, client_id),
        )
    return get_goal(goal_id, client_id)


def get_deep_dive(cache_key: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute("SELECT response_json FROM deep_dive_cache WHERE cache_key=?", (cache_key,)).fetchone()
    return _loads(row["response_json"], None) if row else None


def save_deep_dive(cache_key: str, analysis_id: str, response: dict[str, Any]) -> None:
    with _WRITE_LOCK, connection() as db:
        db.execute(
            """INSERT OR REPLACE INTO deep_dive_cache(cache_key, analysis_id, response_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (cache_key, analysis_id, _dumps(response), utc_now()),
        )


def record_usage(
    client_id: str,
    endpoint: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached: bool = False,
) -> None:
    ensure_client(client_id)
    with _WRITE_LOCK, connection() as db:
        db.execute(
            """INSERT INTO usage_events
               (id, client_id, endpoint, model, input_tokens, output_tokens, cached, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex,
                client_id,
                endpoint,
                model,
                max(0, int(input_tokens or 0)),
                max(0, int(output_tokens or 0)),
                1 if cached else 0,
                utc_now(),
            ),
        )


def usage_summary(client_id: str, days: int = 30) -> dict[str, Any]:
    days = max(1, min(int(days), 365))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    with connection() as db:
        aggregate = db.execute(
            """SELECT COUNT(*) AS requests,
                      COALESCE(SUM(input_tokens),0) AS input_tokens,
                      COALESCE(SUM(output_tokens),0) AS output_tokens,
                      COALESCE(SUM(cached),0) AS cached_requests
               FROM usage_events WHERE client_id=? AND created_at>=?""",
            (client_id, cutoff),
        ).fetchone()
        by_endpoint = db.execute(
            """SELECT endpoint, COUNT(*) AS requests,
                      COALESCE(SUM(input_tokens),0) AS input_tokens,
                      COALESCE(SUM(output_tokens),0) AS output_tokens,
                      COALESCE(SUM(cached),0) AS cached_requests
               FROM usage_events WHERE client_id=? AND created_at>=?
               GROUP BY endpoint ORDER BY requests DESC""",
            (client_id, cutoff),
        ).fetchall()
    return {
        "period_days": days,
        "requests": aggregate["requests"],
        "input_tokens": aggregate["input_tokens"],
        "output_tokens": aggregate["output_tokens"],
        "cached_requests": aggregate["cached_requests"],
        "by_endpoint": [dict(row) for row in by_endpoint],
    }


def count_recent_usage(client_id: str, endpoint: str, hours: int = 24) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    with connection() as db:
        row = db.execute(
            """SELECT COUNT(*) AS n FROM usage_events
               WHERE client_id=? AND endpoint=? AND created_at>=? AND cached=0""",
            (client_id, endpoint, cutoff),
        ).fetchone()
    return int(row["n"] if row else 0)


def acquire_generation_lease(
    client_id: str,
    fingerprint: str,
    ttl_seconds: int = 300,
) -> str | None:
    """Return a fenced lease token, or ``None`` when this generation is active."""
    lease_id = uuid.uuid4().hex
    now = utc_now()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max(30, ttl_seconds))).isoformat().replace("+00:00", "Z")
    with _WRITE_LOCK, connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _upsert_client(db, client_id, "", now)
        db.execute("DELETE FROM generation_leases WHERE acquired_at<?", (cutoff,))
        cur = db.execute(
            """INSERT OR IGNORE INTO generation_leases
               (client_id, fingerprint, lease_id, acquired_at)
               VALUES (?, ?, ?, ?)""",
            (client_id, fingerprint, lease_id, now),
        )
    return lease_id if cur.rowcount == 1 else None


def release_generation_lease(client_id: str, fingerprint: str, lease_id: str) -> bool:
    """Release only the generation lease owned by ``lease_id``."""
    with _WRITE_LOCK, connection() as db:
        cur = db.execute(
            """DELETE FROM generation_leases
               WHERE client_id=? AND fingerprint=? AND lease_id=?""",
            (client_id, fingerprint, lease_id),
        )
    return cur.rowcount == 1


def reserve_budget(
    client_id: str,
    endpoint: str,
    client_limit: int,
    global_limit: int,
    hours: int = 24,
    ttl_seconds: int = 300,
) -> str | None:
    """Atomically reserve one uncached provider call under client/global caps."""
    endpoint = str(endpoint).strip()[:64]
    if not endpoint:
        raise ValueError("endpoint cannot be empty")
    client_limit = int(client_limit)
    global_limit = int(global_limit)
    hours = max(1, int(hours))
    ttl_seconds = max(1, int(ttl_seconds))
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
    usage_cutoff = (now_dt - timedelta(hours=hours)).isoformat(timespec="microseconds").replace("+00:00", "Z")
    reservation_cutoff = (now_dt - timedelta(seconds=ttl_seconds)).isoformat(timespec="microseconds").replace("+00:00", "Z")
    reservation_id = uuid.uuid4().hex

    with _WRITE_LOCK, connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _upsert_client(db, client_id, "", now)
        db.execute(
            "DELETE FROM budget_reservations WHERE created_at<?",
            (reservation_cutoff,),
        )
        client_usage = db.execute(
            """SELECT COUNT(*) AS n FROM usage_events
               WHERE client_id=? AND endpoint=? AND created_at>=? AND cached=0""",
            (client_id, endpoint, usage_cutoff),
        ).fetchone()["n"]
        client_active = db.execute(
            """SELECT COUNT(*) AS n FROM budget_reservations
               WHERE client_id=? AND endpoint=?""",
            (client_id, endpoint),
        ).fetchone()["n"]
        global_usage = db.execute(
            """SELECT COUNT(*) AS n FROM usage_events
               WHERE endpoint=? AND created_at>=? AND cached=0""",
            (endpoint, usage_cutoff),
        ).fetchone()["n"]
        global_active = db.execute(
            """SELECT COUNT(*) AS n FROM budget_reservations
               WHERE endpoint=?""",
            (endpoint,),
        ).fetchone()["n"]
        if (
            client_limit <= 0
            or global_limit <= 0
            or int(client_usage) + int(client_active) >= client_limit
            or int(global_usage) + int(global_active) >= global_limit
        ):
            return None
        db.execute(
            """INSERT INTO budget_reservations(id, client_id, endpoint, created_at)
               VALUES (?, ?, ?, ?)""",
            (reservation_id, client_id, endpoint, now),
        )
    return reservation_id


def release_budget(reservation_id: str, client_id: str) -> bool:
    """Release only the budget reservation identified by both owner and token."""
    with _WRITE_LOCK, connection() as db:
        cur = db.execute(
            "DELETE FROM budget_reservations WHERE id=? AND client_id=?",
            (reservation_id, client_id),
        )
    return cur.rowcount == 1


def append_predictions(
    records: list[dict[str, Any]],
    client_id: str,
    analysis_id: str | None = None,
) -> None:
    if not records:
        return
    ensure_client(client_id)
    now = utc_now()
    with _WRITE_LOCK, connection() as db:
        for record in records:
            payload = dict(record)
            prediction_id = str(payload.get("id") or uuid.uuid4().hex)
            payload["id"] = prediction_id
            payload["client_id"] = client_id
            if analysis_id:
                payload["analysis_id"] = analysis_id
            db.execute(
                """INSERT OR IGNORE INTO predictions
                   (id, client_id, analysis_id, metric, status, resolve_at,
                    payload_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction_id,
                    client_id,
                    analysis_id,
                    str(payload.get("metric") or "unknown")[:40],
                    str(payload.get("status") or "pending")[:24],
                    payload.get("resolve_at"),
                    _dumps(payload),
                    str(payload.get("created_at") or now),
                    now,
                ),
            )


def list_predictions(
    client_id: str | None = None,
    limit: int = 100,
    pending_due_before: str | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 1000))
    clauses: list[str] = []
    params: list[Any] = []
    if client_id:
        clauses.append("client_id=?")
        params.append(client_id)
    if pending_due_before:
        clauses.extend(["status='pending'", "resolve_at IS NOT NULL", "resolve_at<=?"])
        params.append(pending_due_before)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with connection() as db:
        rows = db.execute(
            f"SELECT payload_json FROM predictions{where} ORDER BY created_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [_loads(row["payload_json"], {}) for row in rows]


def update_prediction(prediction: dict[str, Any]) -> bool:
    prediction_id = str(prediction.get("id") or "")
    if not prediction_id:
        return False
    with _WRITE_LOCK, connection() as db:
        cur = db.execute(
            """UPDATE predictions
               SET metric=?, status=?, resolve_at=?, payload_json=?, updated_at=?
               WHERE id=?""",
            (
                str(prediction.get("metric") or "unknown")[:40],
                str(prediction.get("status") or "pending")[:24],
                prediction.get("resolve_at"),
                _dumps(prediction),
                utc_now(),
                prediction_id,
            ),
        )
    return cur.rowcount == 1
