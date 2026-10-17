
"""
Initial schema migration from declarative models (safe to run repeatedly).

This initializes missing tables; future column changes need versioned migrations.
The former JSON-record database is intentionally not converted automatically.
"""

import asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from rest_api_server.globals import Database, Settings
from rest_api_server.models import Base

async def initialize_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        if "records" in tables:
            raise RuntimeError("Legacy JSON-record database detected. Set DATABASE_URL to a new database; preserve the old file for an explicit data migration.")
        await connection.run_sync(Base.metadata.create_all)

async def main():
    database = Database(Settings())
    try:
        await initialize_schema(database.engine)
    finally:
        await database.close()

if __name__ == "__main__":
    asyncio.run(main())
