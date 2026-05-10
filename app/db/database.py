"""
database.py — Inicialización y acceso a la base de datos PostgreSQL.
Usa asyncpg para operaciones asíncronas.
"""
import os
import logging
import asyncpg
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Default local connection string if not provided
_db_user = os.getenv("DB_USER", "postgres")
_db_password = os.getenv("DB_PASSWORD", "mypassword123")
_db_name = os.getenv("DB_NAME", "mldb")

_env_url = os.getenv("DATABASE_URL")
if not _env_url or "${DB_USER}" in _env_url:
    DATABASE_URL = f"postgresql://{_db_user}:{_db_password}@localhost/{_db_name}"
else:
    DATABASE_URL = _env_url

_pool = None

async def init_db() -> None:
    """Crea las tablas si no existen. Llamar al arrancar la aplicación."""
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise e
            
    try:
        async with _pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name  TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS quota_usage (
                id         SERIAL PRIMARY KEY,
                email      TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                used_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS payments (
                id              SERIAL PRIMARY KEY,
                email           TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                mp_payment_id   TEXT UNIQUE,
                mp_preference_id TEXT,
                amount          REAL NOT NULL,
                currency        TEXT DEFAULT 'CLP',
                status          TEXT DEFAULT 'pending',
                valid_until     TEXT,
                plan_type       TEXT DEFAULT 'pro',
                created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)
    except Exception as e:
        logger.error(f"Error initializing database tables: {e}")
        raise e

@asynccontextmanager
async def get_db():
    """Retorna un context manager de conexión asyncpg. Usar con 'async with'."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    async with _pool.acquire() as conn:
        yield conn
