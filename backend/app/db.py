"""Lớp dữ liệu: SQLite (mặc định, chạy trên máy) hoặc PostgreSQL (khi có biến DATABASE_URL, dùng khi deploy).

Phần còn lại của app viết SQL kiểu SQLite (dấu ?). Khi chạy PostgreSQL, lớp này tự dịch sang cú pháp
PostgreSQL nên không phải sửa các câu truy vấn ở nơi khác.
"""
import os
import re
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "EXPENSE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "expense.db")
)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_PG = bool(DATABASE_URL)


def backend_name() -> str:
    return "postgres" if USE_PG else "sqlite"


# ----------------------------------------------------------------------------- schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    store_name TEXT,
    date TEXT NOT NULL,
    total INTEGER NOT NULL,
    engine TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
CREATE TABLE IF NOT EXISTS budgets (          -- bảng cũ (trước khi có tài khoản), chỉ dùng để chuyển dữ liệu
    category TEXT PRIMARY KEY,
    monthly_limit INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS user_budgets (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    monthly_limit INTEGER NOT NULL,
    PRIMARY KEY (user_id, category)
);
"""

_NOW_TEXT = "(to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'))"
PG_SCHEMA = [
    f"""CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT {_NOW_TEXT}
    )""",
    """CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    f"""CREATE TABLE IF NOT EXISTS invoices (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
        store_name TEXT,
        date TEXT NOT NULL,
        total BIGINT NOT NULL,
        engine TEXT,
        created_at TEXT DEFAULT {_NOW_TEXT}
    )""",
    f"""CREATE TABLE IF NOT EXISTS transactions (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        name TEXT NOT NULL,
        quantity DOUBLE PRECISION NOT NULL DEFAULT 1,
        amount BIGINT NOT NULL,
        category TEXT NOT NULL,
        store TEXT,
        note TEXT,
        invoice_id BIGINT REFERENCES invoices(id) ON DELETE SET NULL,
        created_at TEXT DEFAULT {_NOW_TEXT}
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date)",
    """CREATE TABLE IF NOT EXISTS budgets (
        category TEXT PRIMARY KEY,
        monthly_limit BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS user_budgets (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category TEXT NOT NULL,
        monthly_limit BIGINT NOT NULL,
        PRIMARY KEY (user_id, category)
    )""",
    # database đã tạo từ phiên bản chưa có tài khoản: thêm cột user_id
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE CASCADE",
    "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE CASCADE",
    "CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, date)",
]


# ----------------------------------------------------------------------------- PostgreSQL adapter
_INSERT_WITH_ID = re.compile(r"^\s*INSERT\s+INTO\s+(invoices|transactions|users)\b", re.I)
_LIKE = re.compile(r"\bLIKE\b", re.I)


def _translate(sql: str) -> str:
    """SQL kiểu SQLite -> PostgreSQL: ? -> %s, LIKE -> ILIKE (SQLite LIKE không phân biệt hoa/thường)."""
    return _LIKE.sub("ILIKE", sql.replace("%", "%%").replace("?", "%s"))


class _PgCursor:
    """Giống sqlite3.Cursor ở mức app cần: lặp, fetchone/fetchall, lastrowid, rowcount."""

    def __init__(self, cur, lastrowid=None):
        self._cur = cur
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur.fetchall())


class _PgConn:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        sql = _translate(sql)
        want_id = bool(_INSERT_WITH_ID.match(sql)) and "RETURNING" not in sql.upper()
        if want_id:
            sql += " RETURNING id"
        cur = self._raw.cursor()
        cur.execute(sql, tuple(params))
        return _PgCursor(cur, cur.fetchone()["id"] if want_id else None)

    def executemany(self, sql, seq):
        cur = self._raw.cursor()
        cur.executemany(_translate(sql), [tuple(p) for p in seq])
        return _PgCursor(cur)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _pg_connect() -> _PgConn:
    import psycopg
    from psycopg.adapt import Loader
    from psycopg.rows import dict_row

    class _NumLoader(Loader):  # SUM(bigint) trả về numeric -> đổi về int/float cho giống SQLite
        def load(self, data):
            s = bytes(data).decode()
            try:
                return int(s)
            except ValueError:
                return float(s)

    # prepare_threshold=None: tắt prepared statement phía server để chạy được cả qua cổng pooler (PgBouncer) của Neon
    raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15, prepare_threshold=None)
    raw.adapters.register_loader("numeric", _NumLoader)
    return _PgConn(raw)


# ----------------------------------------------------------------------------- API dùng chung
def connect():
    if USE_PG:
        return _pg_connect()
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
    if USE_PG:
        with session() as conn:
            for stmt in PG_SCHEMA:
                conn.execute(stmt)
        return
    with session() as conn:
        conn.executescript(SCHEMA)
        # database cũ (chưa có tài khoản): thêm cột user_id
        for table in ("invoices", "transactions"):
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, date)")


def is_integrity_error(exc: Exception) -> bool:
    """Vi phạm ràng buộc (ví dụ trùng email), dùng được cho cả SQLite lẫn PostgreSQL."""
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    return type(exc).__module__.startswith("psycopg") and type(exc).__name__ in ("UniqueViolation", "IntegrityError")
