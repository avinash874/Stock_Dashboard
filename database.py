"""SQLite persistence for cleaned stock data."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config import DB_PATH, DATA_DIR


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    ensure_data_dir()
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                symbol TEXT PRIMARY KEY,
                display_symbol TEXT NOT NULL,
                name TEXT,
                exchange TEXT DEFAULT 'NSE'
            );

            CREATE TABLE IF NOT EXISTS stock_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                bar_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                daily_return REAL,
                ma7 REAL,
                week52_high REAL,
                week52_low REAL,
                volatility REAL,
                UNIQUE(symbol, bar_date)
            );

            CREATE INDEX IF NOT EXISTS idx_stock_bars_symbol_date
            ON stock_bars(symbol, bar_date DESC);
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}
