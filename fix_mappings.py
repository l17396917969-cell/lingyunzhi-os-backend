"""Fix and expand ObjectType mappings for Phase 1 PoC."""
import json
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from onto_platform.db import make_engine, get_sessionmaker
from onto_platform.config import Settings

SETTINGS = Settings()
ENGINE = make_engine(SETTINGS.database_url)
Session: async_sessionmaker[AsyncSession] = get_sessionmaker(ENGINE)

MES_SQLITE = "95a97bee-124f-46ec-a321-753b35c18e23"

# Mapping: ObjectType RID -> (connection_id, table_name, {property_api_name: physical_column})
MAPPINGS = {
    # --- Fix existing 4 ---
    "ri.obj.0000": (MES_SQLITE, "product", {
        "unit": "label",
        "status": "stock_real",
        "description": "description",
        "productCode": "ref",
        "productName": "label",
        "productType": "type",
        "standardCost": "price",
        "specification": "note_public",
    }),
    "ri.obj.0003": (MES_SQLITE, "mo", {
        "status": "status",
        "orderNo": "ref",
        "priority": "qty",
        "quantity": "qty",
        "productId": "product_id",
        "notePublic": "note_public",
        "planDateEnd": "plan_date_end",
        "actualDateEnd": "plan_date_end",
        "planDateStart": "plan_date_start",
        "actualDateStart": "plan_date_start",
    }),
    "ri.obj.0007": (MES_SQLITE, "stockmovement", {
        "lotNo": "label",
        "status": "type",
        "quantity": "qty",
        "recordId": "id",
        "productId": "product_id",
        "expiryDate": "datem",
        "locationId": "warehouse_id",
    }),
    "ri.obj.0008": (MES_SQLITE, "warehouse", {
        "area": "description",
        "status": "ref",
        "locationCode": "ref",
        "locationName": "label",
        "locationType": "description",
        "parentLocation": "id",
    }),
    # --- New mappings ---
    "ri.obj.0010": (MES_SQLITE, "bom", {
        "bomId": "ref",
        "status": "status",
        "version": "qty",
        "productId": "product_id",
        "description": "label",
    }),
    "ri.obj.0012": (MES_SQLITE, "stockmovement", {
        "type": "type",
        "datem": "datem",
        "label": "label",
        "quantity": "qty",
        "productId": "product_id",
        "movementId": "id",
        "warehouseId": "warehouse_id",
    }),
    "ri.obj.0013": (MES_SQLITE, "operationreport", {
        "notes": "notes",
        "worker": "worker",
        "reportId": "id",
        "outputQty": "output_qty",
        "reportedAt": "reported_at",
        "workTimeMin": "work_time_min",
        "assignmentId": "assignment_id",
        "defectiveQty": "defective_qty",
        "qualifiedQty": "qualified_qty",
    }),
    "ri.obj.0014": (MES_SQLITE, "materialconsumption", {
        "qty": "qty",
        "lotNo": "lot_no",
        "productId": "product_id",
        "recordedAt": "recorded_at",
        "assignmentId": "assignment_id",
        "consumptionId": "id",
    }),
    "ri.obj.0004": (MES_SQLITE, "operationassignment", {
        "status": "status",
        "sequence": "sequence",
        "toolType": "machine_code",
        "setupTime": "setup_time",
        "machineType": "operation_code",
        "yieldTarget": "yield_rate",
        "operationCode": "operation_code",
        "operationName": "operation_name",
        "runTimePerUnit": "run_time_per_unit",
    }),
}

async def main():
    async with Session() as session:
        row = await session.execute(
            text("SELECT payload FROM registries WHERE env = 'production'")
        )
        payload = row.scalar_one()

        for rid, (conn_id, table, col_map) in MAPPINGS.items():
            obj = payload["object_types"].get(rid)
            if not obj:
                print(f"SKIP {rid}: not found")
                continue

            # Set asset_mapping
            obj["asset_mapping"] = {
                "read_connection_id": conn_id,
                "read_asset_path": table,
                "writeback_enabled": False,
                "writeback_connection_id": "",
                "writeback_asset_path": "",
            }

            # Set physical_column on property_types
            mapped = 0
            for prop_key, prop in obj.get("property_types", {}).items():
                phys = col_map.get(prop.get("api_name", ""), "")
                if phys:
                    prop["physical_column"] = phys
                    mapped += 1
                else:
                    # Clear any stale physical_column
                    if "physical_column" in prop:
                        del prop["physical_column"]

            print(f"UPDATED {rid} ({obj['api_name']}) -> {conn_id}/{table} ({mapped}/{len(obj.get('property_types', {}))} mapped)")

        # Save back
        await session.execute(
            text(
                "UPDATE registries SET payload = CAST(:p AS jsonb), version = version + 1, "
                "updated_at = now(), updated_by_token_label = :u, last_commit_message = :m "
                "WHERE env = 'production'"
            ),
            {
                "p": json.dumps(payload),
                "u": "dev-test",
                "m": "Phase 1: fix physical_column mappings for 9 core ObjectTypes",
            },
        )
        await session.commit()
        print("SAVED production registry")

if __name__ == "__main__":
    asyncio.run(main())
