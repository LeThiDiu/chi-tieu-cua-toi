"""Lớp dữ liệu SQLite (thư viện chuẩn sqlite3, không cần cài DB riêng)."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "EXPENSE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "expense.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT,
    date TEXT NOT NULL,
    total INTEGER NOT NULL,
    engine TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- YYYY-MM-DD
    name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    amount INTEGER NOT NULL,         -- thành tiền, VND
    category TEXT NOT NULL,
    store TEXT,
    note TEXT,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT PRIMARY KEY,
    monthly_limit INTEGER NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with session() as conn:
        conn.executescript(SCHEMA)
