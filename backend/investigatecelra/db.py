"""SQLite persistence.

SQLite is the whole database tier. The corpus is small (tens of thousands of
documents), single-writer, and read-mostly — exactly the workload SQLite is
best at — and it keeps the deployment to a single process with no external
service to provision.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from .config import settings

_LOCK = threading.Lock()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL,
    source_name  TEXT NOT NULL,
    tier         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    host         TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    simhash      TEXT NOT NULL DEFAULT '0',
    extra        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_documents_published ON documents(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_source    ON documents(source_id);

CREATE TABLE IF NOT EXISTS trials (
    id           TEXT PRIMARY KEY,
    nct_id       TEXT,
    title        TEXT NOT NULL,
    sponsor      TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT '',
    phase        TEXT NOT NULL DEFAULT '',
    conditions   TEXT NOT NULL DEFAULT '',
    interventions TEXT NOT NULL DEFAULT '',
    enrollment   INTEGER,
    start_date   TEXT,
    updated_at   TEXT,
    why_stopped  TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_trials_sponsor ON trials(sponsor);

CREATE TABLE IF NOT EXISTS watchlist (
    entity_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    focus      TEXT NOT NULL DEFAULT '',
    added_at   TEXT NOT NULL,
    pinned     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    mode        TEXT NOT NULL,
    fetched     INTEGER NOT NULL DEFAULT 0,
    accepted    INTEGER NOT NULL DEFAULT 0,
    duplicates  INTEGER NOT NULL DEFAULT 0,
    errors      TEXT NOT NULL DEFAULT '[]',
    detail      TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def cursor(commit: bool = False) -> Iterator[sqlite3.Cursor]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.cursor()
            yield cur
            if commit:
                conn.commit()
        finally:
            conn.close()


def init() -> None:
    with cursor(commit=True) as cur:
        cur.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------
DOC_COLUMNS = (
    "id", "source_id", "source_name", "tier", "kind", "title", "body", "url",
    "host", "published_at", "fetched_at", "simhash", "extra",
)

# A 64-bit SimHash exceeds SQLite's signed-integer range about half the time,
# and sqlite3 refuses to bind such a value regardless of the column type — one
# oversized row would abort the whole batch. The ingest modules already store
# it as text; this coercion makes that a property of the store rather than a
# convention every future source has to remember.
_TEXT_COLUMNS = {"simhash", "extra", "url", "host"}


def _coerce(column: str, value) -> object:
    if column in _TEXT_COLUMNS:
        return "" if value is None else str(value)
    if isinstance(value, int) and not -(2 ** 63) <= value < 2 ** 63:
        return str(value)
    return value


def upsert_documents(docs: list[dict]) -> tuple[int, int]:
    """Insert new documents, ignoring ones we already hold. Returns (new, dupes)."""
    if not docs:
        return (0, 0)
    rows = [
        tuple(
            json.dumps(d.get(c, {})) if c == "extra" else _coerce(c, d.get(c, ""))
            for c in DOC_COLUMNS
        )
        for d in docs
    ]
    with cursor(commit=True) as cur:
        before = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        cur.executemany(
            f"INSERT OR IGNORE INTO documents ({','.join(DOC_COLUMNS)}) "
            f"VALUES ({','.join('?' * len(DOC_COLUMNS))})",
            rows,
        )
        after = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    new = after - before
    return (new, len(docs) - new)


def all_documents(limit: int = 20000) -> list[dict]:
    with cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM documents ORDER BY published_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["extra"] = json.loads(d.get("extra") or "{}")
        out.append(d)
    return out


def document_count() -> int:
    with cursor() as cur:
        return cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


# ---------------------------------------------------------------------------
# trials
# ---------------------------------------------------------------------------
TRIAL_COLUMNS = (
    "id", "nct_id", "title", "sponsor", "status", "phase", "conditions",
    "interventions", "enrollment", "start_date", "updated_at", "why_stopped",
    "url",
)


def upsert_trials(trials: list[dict]) -> int:
    if not trials:
        return 0
    rows = [tuple(t.get(c) if c in t else ("" if c != "enrollment" else None) for c in TRIAL_COLUMNS) for t in trials]
    with cursor(commit=True) as cur:
        cur.executemany(
            f"INSERT OR REPLACE INTO trials ({','.join(TRIAL_COLUMNS)}) "
            f"VALUES ({','.join('?' * len(TRIAL_COLUMNS))})",
            rows,
        )
    return len(rows)


def all_trials(limit: int = 5000) -> list[dict]:
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM trials ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# watchlist
# ---------------------------------------------------------------------------
def get_watchlist() -> list[dict]:
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM watchlist ORDER BY pinned DESC, name ASC").fetchall()
    return [dict(r) for r in rows]


def add_watch(entity_id: str, name: str, focus: str, added_at: str) -> None:
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT OR REPLACE INTO watchlist (entity_id, name, focus, added_at, pinned) "
            "VALUES (?,?,?,?, COALESCE((SELECT pinned FROM watchlist WHERE entity_id=?),0))",
            (entity_id, name, focus, added_at, entity_id),
        )


def remove_watch(entity_id: str) -> None:
    with cursor(commit=True) as cur:
        cur.execute("DELETE FROM watchlist WHERE entity_id=?", (entity_id,))


# ---------------------------------------------------------------------------
# runs & meta
# ---------------------------------------------------------------------------
def start_run(started_at: str, mode: str) -> int:
    with cursor(commit=True) as cur:
        cur.execute("INSERT INTO runs (started_at, mode) VALUES (?,?)", (started_at, mode))
        return int(cur.lastrowid)


def finish_run(run_id: int, finished_at: str, fetched: int, accepted: int,
               duplicates: int, errors: list[str], detail: dict) -> None:
    with cursor(commit=True) as cur:
        cur.execute(
            "UPDATE runs SET finished_at=?, fetched=?, accepted=?, duplicates=?, errors=?, detail=? WHERE id=?",
            (finished_at, fetched, accepted, duplicates, json.dumps(errors), json.dumps(detail), run_id),
        )


def recent_runs(limit: int = 10) -> list[dict]:
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["errors"] = json.loads(d.get("errors") or "[]")
        d["detail"] = json.loads(d.get("detail") or "{}")
        out.append(d)
    return out


def set_meta(key: str, value: Any) -> None:
    with cursor(commit=True) as cur:
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, json.dumps(value)))


def get_meta(key: str, default: Any = None) -> Any:
    with cursor() as cur:
        row = cur.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default
