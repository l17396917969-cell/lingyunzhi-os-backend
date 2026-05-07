import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/ontology-platform')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from onto_platform.connections.store import ConnectionStore, ConnectionAlreadyExists, ConnectionKind

# ---------------------------------------------------------------------------
# Environment-based configuration
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('ONTO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('Environment variable ONTO_SECRET_KEY is required')

DATABASE_URL = os.environ.get('ONTO_DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('Environment variable ONTO_DATABASE_URL is required')

MES_SQLITE_DSN = os.environ.get(
    'MES_SQLITE_DSN',
    'sqlite+aiosqlite:///home/ubuntu/demo_mes/mes_lite.db',
)
WMS_SQLITE_DSN = os.environ.get(
    'WMS_SQLITE_DSN',
    'sqlite+aiosqlite:///home/ubuntu/demo_wms/data/wms.sqlite3',
)

APS_POSTGRES_DSN = os.environ.get('APS_POSTGRES_DSN')
if not APS_POSTGRES_DSN:
    raise RuntimeError('Environment variable APS_POSTGRES_DSN is required')

TMS_POSTGRES_DSN = os.environ.get('TMS_POSTGRES_DSN')
if not TMS_POSTGRES_DSN:
    raise RuntimeError('Environment variable TMS_POSTGRES_DSN is required')

CONNECTIONS = [
    {'label': 'mes_sqlite',   'kind': ConnectionKind.sqlite,   'dsn': MES_SQLITE_DSN},
    {'label': 'wms_sqlite',   'kind': ConnectionKind.sqlite,   'dsn': WMS_SQLITE_DSN},
    {'label': 'aps_postgres', 'kind': ConnectionKind.postgres, 'dsn': APS_POSTGRES_DSN},
    {'label': 'tms_postgres', 'kind': ConnectionKind.postgres, 'dsn': TMS_POSTGRES_DSN},
]

# ---------------------------------------------------------------------------

async def main():
    store = ConnectionStore(SECRET_KEY)
    engine = create_async_engine(DATABASE_URL, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for conn in CONNECTIONS:
            try:
                async with session.begin():
                    await store.insert(session, label=conn['label'], kind=conn['kind'], dsn=conn['dsn'])
                print(f"OK: registered '{conn['label']}' ({conn['kind'].value})")
            except ConnectionAlreadyExists:
                print(f"SKIP: '{conn['label']}' already exists")
            except Exception as e:
                print(f"ERR: '{conn['label']}' failed: {e}")

    # Verify all 4 connections exist after running
    async with async_session() as session:
        existing = await store.list_all(session)
        existing_labels = {c.label for c in existing}
        required_labels = {c['label'] for c in CONNECTIONS}
        missing = required_labels - existing_labels
        if missing:
            print(f'Verification FAILED: missing connections: {missing}')
            sys.exit(1)
        else:
            print('Verification OK: all 4 connections present.')

    await engine.dispose()
    print('Done.')

if __name__ == '__main__':
    asyncio.run(main())
