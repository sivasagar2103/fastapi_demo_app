"""Verify actual database constraints and transaction behavior without HTTP policies."""
import asyncio
import sqlite3

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from rest_api_server.globals import Database, Settings
from rest_api_server.migrations import initialize_schema
from rest_api_server.repositories import Repositories


def test_schema_transactions_and_constraints(tmp_path):
    async def scenario():
        database = Database(Settings(database_url='sqlite+aiosqlite:///'+str(tmp_path / 'schema.db')))
        try:
            await initialize_schema(database.engine)
            await initialize_schema(database.engine)
            async with database.engine.connect() as connection:
                tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
                assert set(tables) == {'tenants', 'organizations', 'users', 'employees', 'employee_groups', 'group_memberships','exchange_rate_jobs'}
            async with database.session_factory() as session:
                with pytest.raises(IntegrityError):
                    async with session.begin():
                        repos = Repositories(session)
                        await repos.tenants.create({'name': 'Rolled back'})
                        await repos.organizations.create({'name': 'Invalid', 'tenant_id': 'missing'})
                async with session.begin():
                    repos = Repositories(session)
                    assert await repos.tenants.list() == []
                    tenant = await repos.tenants.create({'name': 'Persistent'})
                    first = await repos.organizations.create({'name': 'First', 'tenant_id': tenant['id']})
                    second = await repos.organizations.create({'name': 'Second', 'tenant_id': tenant['id']})
                    employee = await repos.employees.create({'name': 'Alex', 'email': 'alex@example.com', 'tenant_id': tenant['id'], 'organization_id': first['id']})
                    group = await repos.employee_groups.create({'name': 'Group', 'tenant_id': tenant['id'], 'organization_id': second['id']})
                with pytest.raises(IntegrityError):
                    async with session.begin():
                        await repos.memberships.add(group['id'], employee['id'], second['id'])
                with pytest.raises(IntegrityError):
                    async with session.begin():
                        await repos.tenants.delete(tenant['id'])
            # A fresh session sees committed state after failed transactions.
            async with database.session_factory() as session:
                assert (await Repositories(session).tenants.get(tenant['id']))['name'] == 'Persistent'
        finally:
            await database.close()
    asyncio.run(scenario())


def test_legacy_database_is_preserved(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE records (id TEXT PRIMARY KEY)')
        connection.execute("INSERT INTO records VALUES ('preserved')")

    async def scenario():
        database = Database(Settings(database_url='sqlite+aiosqlite:///'+str(path)))
        try:
            with pytest.raises(RuntimeError, match='Legacy JSON-record database'):
                await initialize_schema(database.engine)
        finally:
            await database.close()
    asyncio.run(scenario())
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT id FROM records').fetchone()[0] == 'preserved'
