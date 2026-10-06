"""SQLite storage for the two user-facing features: wishlist and search history.

There is no login in this project, so each browser gets a random anonymous id (cookie
`pw_vid`) and every row is stored against it. One browser never sees another browser's
wishlist or history. Prices are NOT a dataset: a wishlist row is just the snapshot of a
product the user chose to save, and it is labelled with the date it was saved.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.getenv("PRICEWISE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "instance", "pricewise.db"))
HISTORY_LIMIT = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visitor TEXT NOT NULL,
    query TEXT NOT NULL COLLATE NOCASE,
    searched_at REAL NOT NULL,
    UNIQUE (visitor, query)
);
CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visitor TEXT NOT NULL,
    product_key TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    added_at REAL NOT NULL,
    UNIQUE (visitor, product_key)
);
"""


@contextmanager
def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---- history ---------------------------------------------------------------
def history_add(visitor, query):
    with _db() as c:
        c.execute("INSERT INTO history (visitor, query, searched_at) VALUES (?,?,?) "
                  "ON CONFLICT(visitor, query) DO UPDATE SET searched_at = excluded.searched_at",
                  (visitor, query, time.time()))
        c.execute("DELETE FROM history WHERE visitor = ? AND id NOT IN ("
                  "SELECT id FROM history WHERE visitor = ? ORDER BY searched_at DESC, id DESC LIMIT ?)",
                  (visitor, visitor, HISTORY_LIMIT))


def history_list(visitor):
    with _db() as c:
        rows = c.execute("SELECT query, searched_at FROM history WHERE visitor = ? "
                         "ORDER BY searched_at DESC, id DESC", (visitor,)).fetchall()
    return [{"query": r["query"], "searched_at": r["searched_at"]} for r in rows]


def history_clear(visitor):
    with _db() as c:
        c.execute("DELETE FROM history WHERE visitor = ?", (visitor,))


# ---- wishlist --------------------------------------------------------------
def wishlist_add(visitor, key, snapshot):
    with _db() as c:
        c.execute("INSERT INTO wishlist (visitor, product_key, snapshot, added_at) VALUES (?,?,?,?) "
                  "ON CONFLICT(visitor, product_key) DO NOTHING",
                  (visitor, key, json.dumps(snapshot), time.time()))


def wishlist_remove(visitor, key):
    with _db() as c:
        c.execute("DELETE FROM wishlist WHERE visitor = ? AND product_key = ?", (visitor, key))


def wishlist_list(visitor):
    with _db() as c:
        rows = c.execute("SELECT snapshot, added_at FROM wishlist WHERE visitor = ? "
                         "ORDER BY added_at DESC, id DESC", (visitor,)).fetchall()
    out = []
    for r in rows:
        try:
            item = json.loads(r["snapshot"])
        except ValueError:
            continue
        item["saved_at"] = r["added_at"]
        out.append(item)
    return out


def wishlist_keys(visitor):
    with _db() as c:
        return [r["product_key"] for r in c.execute(
            "SELECT product_key FROM wishlist WHERE visitor = ?", (visitor,))]
