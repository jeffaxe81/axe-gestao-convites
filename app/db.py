"""MySQL connection and idempotent initial schema migration."""
import argparse
import os
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from app.models import Base, EventSettings


def database_url():
    if os.getenv('DATABASE_URL'):
        return os.environ['DATABASE_URL']
    password = os.getenv('MYSQL_PASSWORD')
    if not password:
        raise RuntimeError('MYSQL_PASSWORD ausente; configure .env antes de iniciar.')
    return URL.create('mysql+pymysql', username=os.getenv('MYSQL_USER', 'isadora'),
                      password=password, host=os.getenv('MYSQL_HOST', 'db'),
                      port=int(os.getenv('MYSQL_PORT', '3306')),
                      database=os.getenv('MYSQL_DATABASE', 'isadora'),
                      query={'charset': 'utf8mb4'})


def new_engine():
    return create_engine(database_url(), pool_pre_ping=True, pool_recycle=1800)


def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


def migrate(engine) -> None:
    """Release 1 initial migration; never drops tables or data."""
    schema = MetaData()
    versions = Table('schema_migrations', schema,
                     Column('version', Integer, primary_key=True))
    schema.create_all(engine)
    Base.metadata.create_all(engine)
    with sessionmaker(engine).begin() as session:
        if session.get(EventSettings, 1) is None:
            session.add(EventSettings(id=1, venue=None, edit_deadline_utc=None, buffet_limit=40))
        if session.execute(select(versions.c.version).where(versions.c.version == 1)).first() is None:
            session.execute(versions.insert().values(version=1))
        # V2 creates the new audit_events table via Base.metadata.create_all.
        # Existing families and event settings are never dropped or rewritten.
        if session.execute(select(versions.c.version).where(versions.c.version == 2)).first() is None:
            session.execute(versions.insert().values(version=2))
        # V3 adds invited_families without modifying earlier confirmation records.
        if session.execute(select(versions.c.version).where(versions.c.version == 3)).first() is None:
            session.execute(versions.insert().values(version=3))
        # V4 maps one invitation to one RSVP without altering existing tables.
        if session.execute(select(versions.c.version).where(versions.c.version == 4)).first() is None:
            session.execute(versions.insert().values(version=4))
        # V6 tracks explicit opt-in interest independently from RSVP.
        if session.execute(select(versions.c.version).where(versions.c.version == 6)).first() is None:
            session.execute(versions.insert().values(version=6))
        # V5 adds the organizer's manual dispatch ledger, without altering
        # invitation response status or any existing table/row.
        if session.execute(select(versions.c.version).where(versions.c.version == 5)).first() is None:
            session.execute(versions.insert().values(version=5))


def main():
    parser = argparse.ArgumentParser(description='Banco de dados Isadora')
    parser.add_argument('command', choices=['migrate'])
    args = parser.parse_args()
    engine = new_engine()
    try:
        if args.command == 'migrate':
            migrate(engine)
            print('Migrações 001/002/003/004/005/006 verificadas. Dados existentes preservados.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
