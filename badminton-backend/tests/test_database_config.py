import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app import _database_uri, create_app, db


@pytest.mark.parametrize('scheme', ['postgresql', 'postgres'])
def test_postgres_uri_uses_installed_driver_and_preserves_connection(scheme):
    original = f'{scheme}://member:p%40ss%2Fword@database:5433/badminton?sslmode=require'
    configured = make_url(_database_uri(original))

    assert configured.drivername == 'postgresql+psycopg2'
    assert configured.username == 'member'
    assert configured.password == 'p@ss/word'
    assert configured.host == 'database'
    assert configured.port == 5433
    assert configured.database == 'badminton'
    assert configured.query == {'sslmode': 'require'}
    # Engine construction imports the DBAPI but never connects to a database.
    # This catches the deployed missing-driver failure with SQLite-only tests.
    engine = create_engine(configured)
    try:
        assert engine.dialect.driver == 'psycopg2'
        assert engine.dialect.dbapi.__name__ == 'psycopg2'
    finally:
        engine.dispose()


@pytest.mark.parametrize('uri', [
    'sqlite:///:memory:',
    'sqlite:///db.sqlite',
    'postgresql+psycopg2://member:secret@database/badminton',
    'postgresql+psycopg://member:secret@database/badminton',
])
def test_other_database_uris_and_explicit_drivers_are_preserved(uri):
    assert _database_uri(uri) == uri


def test_app_selects_postgres_driver_before_initializing_database(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://member:secret@database/badminton')
    configured = {}

    class InitializationCaptured(Exception):
        pass

    def capture_config(app):
        configured['uri'] = app.config['SQLALCHEMY_DATABASE_URI']
        raise InitializationCaptured

    monkeypatch.setattr(db, 'init_app', capture_config)
    with pytest.raises(InitializationCaptured):
        create_app()

    assert configured['uri'] == 'postgresql+psycopg2://member:secret@database/badminton'
