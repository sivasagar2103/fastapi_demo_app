
"""Environment configuration; secrets are never committed."""
from collections.abc import AsyncIterator
from fastapi import Request
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import os
import secrets
from dataclasses import dataclass, field

@dataclass
class Settings:
    mysql_host: str = field(default_factory=lambda: os.getenv("MYSQL_HOST", "127.0.0.1"))
    mysql_port: int = field(default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")))
    mysql_database: str = field(default_factory=lambda: os.getenv("MYSQL_DATABASE", "management_demo"))
    mysql_user: str = field(default_factory=lambda: os.getenv("MYSQL_USER", "management_app"))
    mysql_password: str = field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    database_url: str | None = field(default_factory = lambda: os.getenv("DATABASE_URL"))
    jwt_secret: str = field(default_factory = lambda: os.getenv("JWT_SECRET", secrets.token_urlsafe(48)))
    foundry_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_FOUNDRY_ENDPOINT", ""))
    foundry_api_key: str = field(default_factory=lambda: os.getenv("AZURE_FOUNDRY_API_KEY", ""))
    foundry_deployment: str = field(default_factory=lambda: os.getenv("AZURE_FOUNDRY_DEPLOYMENT", ""))
    rabbitmq_host: str = field(default_factory=lambda: os.getenv("RABBITMQ_HOST", "127.0.0.1"))
    rabbitmq_user: str = field(default_factory=lambda: os.getenv("RABBITMQ_USER", "management_worker"))
    rabbitmq_password: str = field(default_factory=lambda: os.getenv("RABBITMQ_PASSWORD", ""))
    exchange_rates_api_key: str = field(default_factory=lambda: os.getenv("EXCHANGE_RATES_API_KEY", ""))
    token_minutes: int = 30
    seed_demo: bool = field(default_factory = lambda: os.getenv("SEED_DEMO", "false").lower() == "true")
    demo_password: str | None = field(default_factory = lambda: os.getenv("DEMO_PASSWORD"))


class Database:
    
    """Application-owned engine and session factory; no shared request session."""

    def __init__(self, settings: Settings):
        if not settings.database_url and not settings.mysql_password:
            raise ValueError("Set MYSQL_PASSWORD or DATABASE_URL before starting the API")
        url = settings.database_url or URL.create(
            "mysql+aiomysql",
            username = settings.mysql_user, password = settings.mysql_password,
            host = settings.mysql_host, port = settings.mysql_port,
            database = settings.mysql_database, query = {"charset": "utf8mb4"},
        )
        self.engine = create_async_engine(url, pool_pre_ping = True, pool_recycle = 1800)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit = False)

    async def close(self):
        await self.engine.dispose()

async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One transaction per request; rollback on service/validation/database failure."""
    async with request.app.state.database.session_factory() as session:
        async with session.begin():
            yield session
