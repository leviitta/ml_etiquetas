"""
database.py — Inicialización y acceso a la base de datos SQLite.
Usa aiosqlite para operaciones asíncronas compatibles con FastAPI.
"""
import aiosqlite
import os
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "app/db/app.db")

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name  TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quota_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT NOT NULL,
    used_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (email) REFERENCES users(email)
);

CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL,
    mp_payment_id   TEXT UNIQUE,
    mp_preference_id TEXT,
    amount          REAL NOT NULL,
    currency        TEXT DEFAULT 'CLP',
    status          TEXT DEFAULT 'pending',   -- pending | approved | rejected
    valid_until     TEXT,                     -- datetime ISO8601
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (email) REFERENCES users(email)
);
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager

def get_db() -> aiosqlite.Connection:
    """Retorna un context manager de conexión aiosqlite. Usar con 'async with'."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return aiosqlite.connect(DB_PATH)

async def init_db() -> None:
    """Crea las tablas si no existen. Llamar al arrancar la aplicación."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()
