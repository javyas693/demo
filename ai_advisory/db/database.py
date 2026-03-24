import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent.parent / "data" / "advisory.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables and seed static data. Safe to call on every startup."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker      TEXT NOT NULL,
                date        TEXT NOT NULL,
                close       REAL NOT NULL,
                is_proxy    INTEGER DEFAULT 0,
                proxy_for   TEXT,
                PRIMARY KEY (ticker, date)
            );

            CREATE TABLE IF NOT EXISTS proxy_map (
                ticker          TEXT PRIMARY KEY,
                proxy_ticker    TEXT NOT NULL,
                beta            REAL NOT NULL DEFAULT 1.0,
                inception_date  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS simulations (
                id                      INTEGER PRIMARY KEY,
                created_at              TEXT NOT NULL,
                inputs                  TEXT NOT NULL,
                timeline                TEXT NOT NULL,
                monthly_intelligence    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS simulation_whatif (
                id                      INTEGER PRIMARY KEY,
                created_at              TEXT NOT NULL,
                gate_overrides          TEXT NOT NULL,
                monthly_intelligence    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gate_override_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT NOT NULL,
                gate_overrides      TEXT NOT NULL,
                summary_metrics     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS client_profile (
                id          INTEGER PRIMARY KEY,
                updated_at  TEXT NOT NULL,
                data        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id     TEXT NOT NULL,
                role                TEXT NOT NULL,
                content             TEXT NOT NULL,
                created_at          TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_price_cache_ticker_date
                ON price_cache (ticker, date);

            CREATE INDEX IF NOT EXISTS idx_chat_history_conversation
                ON chat_history (conversation_id, created_at);
        """)
        _seed_proxy_map(conn)


def _seed_proxy_map(conn: sqlite3.Connection) -> None:
    """
    Seed proxy_map from hardcoded source of truth.
    To add a new ticker: add a row here and restart the server.
    Format: (ticker, proxy_ticker, beta, inception_date)
    """
    PROXY_MAP = [
        ("JEPQ", "QQQ", 0.75, "2022-05-03"),
        ("TLTW", "TLT", 0.60, "2022-08-18"),
        ("SVOL", "SPY", 0.81, "2021-05-12"),
    ]
    conn.executemany("""
        INSERT INTO proxy_map (ticker, proxy_ticker, beta, inception_date)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            proxy_ticker   = excluded.proxy_ticker,
            beta           = excluded.beta,
            inception_date = excluded.inception_date
    """, PROXY_MAP)
