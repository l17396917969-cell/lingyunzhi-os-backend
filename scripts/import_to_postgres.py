#!/usr/bin/env python3
"""
将制造业本体 Schema 导入 PostgreSQL onto.registries 表
"""

import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def load_schema() -> dict:
    """加载本体 Schema JSON"""
    schema_path = project_root / "ontology_output" / "manufacturing_ontology_v1.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def convert_to_registry_format(schema: dict) -> dict:
    """
    将标准 Schema JSON 转换为 Onto Platform registries 表格式。

    Onto Platform 的 payload 结构：
    {
        "version": 8,
        "action_types": { "ri.action.xxx": { ... } },
        "object_types": { "ri.obj.xxx": { ... } },
        "link_types": { "ri.link.xxx": { ... } },
        "function_types": { ... },
        "interface_types": { "ri.iface.xxx": { ... } },
        "shared_property_types": { "ri.shprop.xxx": { ... } },
        "edit_types": { ... }
    }
    """

    # 生成 RID（使用简单的索引方式）
    def make_rid(prefix: str, index: int) -> str:
        return f"ri.{prefix}.{index:04d}"

    registry = {
        "version": "8",
        "action_types": {},
        "object_types": {},
        "link_types": {},
        "interface_types": {},
        "shared_property_types": {},
    }

    # 转换 Object Types
    for i, obj in enumerate(schema.get("objectTypes", [])):
        rid = make_rid("obj", i)
        # 转换为 Onto Platform 格式
        registry_obj = {
            "rid": rid,
            "api_name": obj["apiName"],
            "display_name": obj["displayName"],
            "description": obj.get("description", ""),
            "lifecycle_status": "ACTIVE",
            "property_types": {},
            "implements_interface_type_rids": [],
            "primary_key_property_type_rids": [],
            "validation": {"rules": []},
            "asset_mapping": {
                "read_connection_id": "",
                "read_asset_path": "",
                "writeback_enabled": False,
                "writeback_connection_id": "",
                "writeback_asset_path": "",
            },
        }

        # 转换属性
        for j, prop in enumerate(obj.get("properties", [])):
            prop_rid = f"{rid}.prop.{j:04d}"
            registry_obj["property_types"][prop["apiName"]] = {
                "rid": prop_rid,
                "api_name": prop["apiName"],
                "display_name": prop["displayName"],
                "description": prop.get("description", ""),
                "data_type": prop["baseType"].upper().replace("STRING", "DT_STRING").replace("INTEGER", "DT_INTEGER").replace("DECIMAL", "DT_DOUBLE").replace("BOOLEAN", "DT_BOOLEAN").replace("DATETIME", "DT_TIMESTAMP").replace("DATE", "DT_DATE"),
                "lifecycle_status": "ACTIVE",
                "inherit_from_shared_property_type_rid": prop.get("fromInterface", ""),
                "physical_column": "",
                "virtual_expression": "",
                "widget": {},
                "validation": {"rules": []},
                "compliance": {"masking": "MASK_NONE", "sensitivity": "SENSITIVITY_UNSPECIFIED"},
            }
            if prop.get("isPrimaryKey"):
                registry_obj["primary_key_property_type_rids"].append(prop_rid)

        # 转换接口实现
        for iface_name in obj.get("implementedInterfaces", []):
            # 简化为接口名称，实际需要映射到 RID
            registry_obj["implements_interface_type_rids"].append(iface_name)

        registry["object_types"][rid] = registry_obj

    # 转换 Link Types
    for i, link in enumerate(schema.get("linkTypes", [])):
        rid = make_rid("link", i)
        registry_link = {
            "rid": rid,
            "api_name": link["apiName"],
            "display_name": link["displayName"],
            "description": link.get("description", ""),
            "lifecycle_status": "ACTIVE",
            "cardinality": link.get("cardinality", "ONE_TO_MANY").replace("MANY_TO_ONE", "ONE_TO_MANY"),
            "property_types": {},
            "source_object_type_rid": link["objectTypeA"],
            "target_object_type_rid": link["objectTypeB"],
            "source_interface_type_rid": "",
            "target_interface_type_rid": "",
            "primary_key_property_type_rids": [],
        }

        for j, prop in enumerate(link.get("properties", [])):
            prop_rid = f"{rid}.prop.{j:04d}"
            registry_link["property_types"][prop["apiName"]] = {
                "rid": prop_rid,
                "api_name": prop["apiName"],
                "display_name": prop["displayName"],
                "description": prop.get("description", ""),
                "data_type": prop["baseType"].upper().replace("STRING", "DT_STRING").replace("INTEGER", "DT_INTEGER").replace("DECIMAL", "DT_DOUBLE").replace("BOOLEAN", "DT_BOOLEAN").replace("DATETIME", "DT_TIMESTAMP").replace("DATE", "DT_DATE"),
                "lifecycle_status": "ACTIVE",
                "inherit_from_shared_property_type_rid": "",
                "physical_column": "",
                "virtual_expression": "",
                "widget": {},
                "validation": {"rules": []},
                "compliance": {"masking": "MASK_NONE", "sensitivity": "SENSITIVITY_UNSPECIFIED"},
            }

        registry["link_types"][rid] = registry_link

    # 转换 Action Types
    for i, action in enumerate(schema.get("actionTypes", [])):
        rid = make_rid("action", i)
        # Determine safety level based on action name patterns
        api_name = action["apiName"]
        if api_name.startswith("Get") or api_name.startswith("List") or api_name.startswith("Query") or api_name.startswith("Search"):
            safety_level = "SAFETY_READ_ONLY"
        elif api_name.startswith("Delete") or api_name.startswith("Cancel") or api_name.startswith("Terminate"):
            safety_level = "SAFETY_NON_IDEMPOTENT"
        else:
            safety_level = "SAFETY_UNSPECIFIED"

        registry_action = {
            "rid": rid,
            "api_name": action["apiName"],
            "display_name": action["displayName"],
            "description": action.get("description", ""),
            "lifecycle_status": "ACTIVE",
            "safety_level": safety_level,
            "parameters": [],
            "execution": {
                "type": "ENGINE_UNSPECIFIED",
                "is_batch": False,
                "is_sync": True,
                "native_crud_json": "",
                "python_script": "",
                "sql_template": "",
                "webhook_config_json": "",
            },
            "side_effects": [],
            "edited_object_types": action.get("editedObjectTypes", []),
            "edits": [],
        }

        for param in action.get("parameters", []):
            registry_action["parameters"].append({
                "api_name": param["id"],
                "display_name": param["displayName"],
                "description": param.get("description", ""),
                "required": param.get("required", False),
                "explicit_type": param["baseType"].upper().replace("STRING", "DT_STRING").replace("INTEGER", "DT_INTEGER").replace("DECIMAL", "DT_DOUBLE").replace("BOOLEAN", "DT_BOOLEAN").replace("DATETIME", "DT_TIMESTAMP").replace("DATE", "DT_DATE"),
                "derived_from_object_type_rid": "",
                "derived_from_link_type_rid": "",
                "derived_from_interface_type_rid": "",
            })

        # 转换 edits（原始 schema 中的 edits 字段）
        for edit in action.get("edits", []):
            prop_updates = edit.get("propertyUpdates", [])
            first_prop = prop_updates[0] if prop_updates else {}
            registry_action["edits"].append({
                "edit_type": edit.get("editType", ""),
                "object_type": edit.get("objectType", ""),
                "target_object_type": edit.get("objectType", ""),
                "property_updates": prop_updates,
                "target_property": first_prop.get("property", ""),
                "property_value_change": first_prop.get("value", ""),
                "condition": edit.get("condition", ""),
                "error_message": edit.get("errorMessage", ""),
            })

        # 原始 schema 中的 sideEffects
        for effect in action.get("sideEffects", []):
            effect_type = effect.get("type", "NOTIFICATION").upper()
            category_map = {
                "NOTIFICATION": "NOTIFICATION",
                "WEBHOOK": "EXTERNAL_API_CALL",
            }
            registry_action["side_effects"].append({
                "category": category_map.get(effect_type, "OTHER"),
                "description": effect.get("template", effect.get("url", "")),
            })

        # 为关键 action 自动补充 sideEffects（如果原始数据中没有）
        if not registry_action["side_effects"]:
            auto_side_effects = {
                "CancelMo": [("NOTIFICATION", "工单已取消")],
                "CompleteMo": [("NOTIFICATION", "工单已完工")],
                "CompleteOperation": [("NOTIFICATION", "工序已完工")],
                "ScrapTool": [("DATA_DELETION", "刀具已报废"), ("NOTIFICATION", "刀具报废通知")],
                "ApprovePurchaseOrder": [("NOTIFICATION", "采购订单已审批通过")],
                "ApproveSalesOrder": [("NOTIFICATION", "销售订单已审批通过")],
                "CreateDefectRecord": [("NOTIFICATION", "缺陷记录已创建")],
                "QualityCheck": [("NOTIFICATION", "质检结果已记录")],
                "Inbound": [("NOTIFICATION", "入库完成")],
                "Outbound": [("NOTIFICATION", "出库完成")],
                "ReportOperation": [("NOTIFICATION", "工序报工已提交")],
                "ScheduleProduction": [("NOTIFICATION", "生产排程已完成")],
                "ReplaceTool": [("NOTIFICATION", "刀具更换已完成")],
                "DispatchAGV": [("NOTIFICATION", "AGV任务已派发")],
                "StartMo": [("NOTIFICATION", "工单已开工")],
                "StartOperation": [("NOTIFICATION", "工序已开工")],
            }
            if api_name in auto_side_effects:
                for category, desc in auto_side_effects[api_name]:
                    registry_action["side_effects"].append({
                        "category": category,
                        "description": desc,
                    })

        registry["action_types"][rid] = registry_action

    # 转换 Interfaces
    for i, iface in enumerate(schema.get("interfaces", [])):
        rid = make_rid("iface", i)
        registry_iface = {
            "rid": rid,
            "api_name": iface["apiName"],
            "display_name": iface["displayName"],
            "description": iface.get("description", ""),
            "lifecycle_status": "ACTIVE",
            "category": "OBJECT_INTERFACE",
            "link_requirements": [],
            "object_constraint": None,
            "extends_interface_type_rids": [],
            "required_shared_property_type_rids": [],
        }
        registry["interface_types"][rid] = registry_iface

    # 转换 Shared Properties
    for i, sp in enumerate(schema.get("sharedProperties", [])):
        rid = make_rid("shprop", i)
        registry_sp = {
            "rid": rid,
            "api_name": sp["apiName"],
            "display_name": sp["displayName"],
            "description": sp.get("description", ""),
            "lifecycle_status": "ACTIVE",
            "data_type": "DT_STRING",
            "widget": {},
            "validation": {"rules": []},
            "compliance": {"masking": "MASK_NONE", "sensitivity": "SENSITIVITY_UNSPECIFIED"},
        }
        registry["shared_property_types"][rid] = registry_sp

    return registry


def import_to_postgres(registry_payload: dict) -> bool:
    """导入到 PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False

    # 连接配置（Docker 容器内部网络）
    conn_params = {
        "host": "172.20.0.2",
        "database": "onto",
        "user": "onto",
        "password": "onto_xianyu_2026",
        "port": 5432,
    }

    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        # 检查 registries 表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'registries'
            );
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            print("Creating registries table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registries (
                    env VARCHAR(50) PRIMARY KEY,
                    payload JSONB NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by_token_label VARCHAR(255),
                    last_commit_message TEXT
                );
            """)
            conn.commit()

        # 插入/更新数据
        cursor.execute("""
            INSERT INTO registries (env, payload, version)
            VALUES (%s, %s, %s)
            ON CONFLICT (env) DO UPDATE
            SET payload = EXCLUDED.payload,
                version = registries.version + 1,
                updated_at = CURRENT_TIMESTAMP
            RETURNING env, version;
        """, ("production", Json(registry_payload), 1))

        result = cursor.fetchone()
        conn.commit()

        print(f"Schema imported successfully!")
        print(f"  Registry ID: {result[0]}")
        print(f"  Version: {result[1]}")
        print(f"  Object Types: {len(registry_payload.get('object_types', {}))}")
        print(f"  Link Types: {len(registry_payload.get('link_types', {}))}")
        print(f"  Action Types: {len(registry_payload.get('action_types', {}))}")
        print(f"  Interfaces: {len(registry_payload.get('interface_types', {}))}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Error importing to PostgreSQL: {e}")
        return False


def main():
    print("Loading manufacturing ontology schema...")
    schema = load_schema()

    print("Converting to Onto Platform registry format...")
    registry = convert_to_registry_format(schema)

    # 同时保存转换后的格式（用于调试）
    registry_path = project_root / "ontology_output" / "manufacturing_registry.json"
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    print(f"Registry format saved to: {registry_path}")

    print("\nImporting to PostgreSQL...")
    success = import_to_postgres(registry)

    if not success:
        print("\nFalling back to SQL file generation...")
        # 生成 SQL 文件供手动导入
        sql_path = project_root / "ontology_output" / "import_manufacturing.sql"
        registry_json = json.dumps(registry, ensure_ascii=False)
        sql = f"""
-- 制造业本体 Schema 导入脚本
-- 生成时间: 2026-05-06

INSERT INTO registries (env, payload, version)
VALUES ('production', '{registry_json.replace("'", "''")}'::jsonb, 1)
ON CONFLICT (env) DO UPDATE
SET payload = EXCLUDED.payload,
    version = registries.version + 1,
    updated_at = CURRENT_TIMESTAMP;

-- 验证查询
SELECT env, version,
       jsonb_object_keys(payload->'object_types') as object_type,
       jsonb_object_keys(payload->'link_types') as link_type,
       jsonb_object_keys(payload->'action_types') as action_type
FROM registries WHERE env = 'production';
"""
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql)
        print(f"SQL file saved to: {sql_path}")
        print("Please run this SQL on the backend PostgreSQL server manually.")


if __name__ == "__main__":
    main()
