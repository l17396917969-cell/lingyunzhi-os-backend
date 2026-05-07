# tests/integration/test_query_sql.py
import re
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from cryptography.fernet import Fernet
from testcontainers.mysql import MySqlContainer

from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, PropertyTypeDefinition,
    AssetMapping, ComplianceConfig, Sensitivity, MaskingStrategy, DataType,
)
from onto_platform.connections.store import ConnectionStore, ConnectionKind
from onto_platform.connections.probe import register_connection
from onto_platform.connections.pool import ConnectionPool
from onto_platform.connections.data_query import query_sql, SqlRejectedError

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def mysql_container():
    with MySqlContainer("mysql:8.0") as mc:
        yield mc


@pytest.fixture(scope="module")
def mysql_dsn(mysql_container):
    raw = mysql_container.get_connection_url()
    return re.sub(r"^mysql(?:\+\w+)?://", "mysql+aiomysql://", raw)


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM connections"))
        await s.commit()
    yield f
    await engine.dispose()


@pytest.fixture(scope="module")
def seeded_mysql(mysql_container, mysql_dsn):
    """Create MD_MATERIAL with a few rows."""
    raw_url = mysql_container.get_connection_url()
    sync_url = re.sub(r"^mysql(?:\+\w+)?://", "mysql+pymysql://", raw_url)
    from sqlalchemy import create_engine
    sync = create_engine(sync_url, future=True)
    with sync.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS MD_MATERIAL")
        conn.exec_driver_sql(
            "CREATE TABLE MD_MATERIAL ("
            "material_code VARCHAR(50), material_name VARCHAR(50), cost_price DECIMAL(10,2))"
        )
        conn.exec_driver_sql(
            "INSERT INTO MD_MATERIAL VALUES "
            "('MTL-0001','Bolt',1.25),('MTL-0002','Nut',0.40),('MTL-0003','Washer',0.10)"
        )
    sync.dispose()
    return mysql_dsn


@pytest.fixture
def registry():
    obj = ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="material",
        property_types={
            "code": PropertyTypeDefinition(
                rid="ri.prop.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                api_name="code", data_type=DataType.DT_STRING, physical_column="material_code",
            ),
            "name": PropertyTypeDefinition(
                rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc",
                api_name="name", data_type=DataType.DT_STRING, physical_column="material_name",
            ),
            "cost_price": PropertyTypeDefinition(
                rid="ri.prop.dddddddd-dddd-dddd-dddd-dddddddddddd",
                api_name="cost_price", data_type=DataType.DT_DOUBLE,
                physical_column="cost_price",
                compliance=ComplianceConfig(
                    sensitivity=Sensitivity.CONFIDENTIAL,
                    masking=MaskingStrategy.MASK_REDACT_FULL,
                ),
            ),
        },
        asset_mapping=AssetMapping(read_connection_id="conn", read_asset_path="MD_MATERIAL"),
    )
    return OntologyRegistry(version="1", object_types={obj.rid: obj})


async def test_query_returns_rows_and_masks_cost(factory, seeded_mysql, registry):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    pool = ConnectionPool(store=store)
    async with factory() as s:
        c = await register_connection(s, store=store, label="x", kind=ConnectionKind.mysql, dsn=seeded_mysql)
        await s.commit()
    async with factory() as s:
        result = await query_sql(
            s, pool=pool, connection_id=c.id,
            sql="SELECT material_code, material_name, cost_price FROM MD_MATERIAL ORDER BY material_code",
            max_rows=10, timeout_ms=5000, registry=registry, dialect="mysql",
        )
    assert result["row_count"] == 3
    assert "cost_price" in result["masked_columns"]
    cost_idx = next(i for i, col in enumerate(result["columns"]) if col["name"] == "cost_price")
    name_idx = next(i for i, col in enumerate(result["columns"]) if col["name"] == "material_name")
    assert all(row[cost_idx] == "***" for row in result["rows"])
    assert result["rows"][0][name_idx] == "Bolt"
    await pool.dispose_all()


async def test_query_aliased_cost_still_masked(factory, seeded_mysql, registry):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    pool = ConnectionPool(store=store)
    async with factory() as s:
        c = await register_connection(s, store=store, label="y", kind=ConnectionKind.mysql, dsn=seeded_mysql)
        await s.commit()
    async with factory() as s:
        result = await query_sql(
            s, pool=pool, connection_id=c.id,
            sql="SELECT cost_price AS leaked FROM MD_MATERIAL",
            max_rows=5, timeout_ms=5000, registry=registry, dialect="mysql",
        )
    assert "leaked" in result["masked_columns"]
    leaked_idx = next(i for i, col in enumerate(result["columns"]) if col["name"] == "leaked")
    assert all(row[leaked_idx] == "***" for row in result["rows"])
    await pool.dispose_all()


async def test_query_sql_rejected_on_dml(factory, seeded_mysql, registry):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    pool = ConnectionPool(store=store)
    async with factory() as s:
        c = await register_connection(s, store=store, label="z", kind=ConnectionKind.mysql, dsn=seeded_mysql)
        await s.commit()
    async with factory() as s:
        with pytest.raises(SqlRejectedError):
            await query_sql(
                s, pool=pool, connection_id=c.id,
                sql="DROP TABLE MD_MATERIAL",
                max_rows=10, timeout_ms=5000, registry=registry, dialect="mysql",
            )
    await pool.dispose_all()


async def test_query_truncation_marker(factory, seeded_mysql, registry):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    pool = ConnectionPool(store=store)
    async with factory() as s:
        c = await register_connection(s, store=store, label="trunc", kind=ConnectionKind.mysql, dsn=seeded_mysql)
        await s.commit()
    async with factory() as s:
        result = await query_sql(
            s, pool=pool, connection_id=c.id,
            sql="SELECT material_code FROM MD_MATERIAL",
            max_rows=2, timeout_ms=5000, registry=registry, dialect="mysql",
        )
    assert result["truncated"] is True
    assert result["row_count"] == 2
    await pool.dispose_all()
