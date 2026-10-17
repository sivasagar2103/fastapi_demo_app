"""SQLite is an isolated test double; the application uses MySQL in Docker."""
import pytest
from sqlalchemy import event
from rest_api_server import globals as configuration

@pytest.fixture(autouse=True)
def sqlite_test_constraints(monkeypatch):
    original = configuration.create_async_engine
    def create_test_engine(url, **kwargs):
        engine = original(url, **kwargs)
        if engine.dialect.name == 'sqlite':
            def enable_test_constraints(connection, _):
                cursor = connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()
            event.listen(engine.sync_engine, 'connect', enable_test_constraints)
        return engine
    monkeypatch.setattr(configuration, 'create_async_engine', create_test_engine)
