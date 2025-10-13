import os
import asyncpg
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not found")

db_pool: Optional[asyncpg.Pool] = None

async def init_db():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10
        )
    return db_pool

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None

async def get_db():
    if db_pool is None:
        await init_db()
    return db_pool
