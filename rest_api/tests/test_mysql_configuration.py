from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from rest_api_server.globals import Database, Settings
from rest_api_server.models import Base


def test_mysql_schema_compiles():
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=mysql.dialect()))
        assert 'CREATE TABLE' in sql


def test_mysql_url_and_async_session():
    import asyncio
    settings = Settings(database_url=None, mysql_password='p@ss:/word', mysql_host='mysql')
    database = Database(settings)
    try:
        assert database.engine.url.drivername == 'mysql+aiomysql'
        assert database.engine.url.password == 'p@ss:/word'
        assert database.engine.url.host == 'mysql'
        assert database.session_factory.kw['expire_on_commit'] is False
    finally:
        asyncio.run(database.close())
