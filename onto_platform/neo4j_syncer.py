"""Neo4j 图谱同步服务"""

from typing import Optional
import logging

from neo4j import AsyncGraphDatabase

from onto_platform.proto_models import (
    OntologyRegistry,
    ObjectTypeDefinition,
    InterfaceTypeDefinition,
    LinkTypeDefinition,
    ActionTypeDefinition,
)

logger = logging.getLogger(__name__)


class Neo4jSyncer:
    """将本体 Registry 同步到 Neo4j 图数据库"""

    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password

    async def sync_registry(self, registry: OntologyRegistry) -> None:
        """同步整个 Registry 到 Neo4j"""
        driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))
        try:
            async with driver.session() as session:
                # 清空现有数据
                await session.run("MATCH (n) DETACH DELETE n")
                logger.info("Cleared existing Neo4j data")

                # 同步 ObjectType 节点
                for rid, obj in registry.object_types.items():
                    await self._upsert_object_type(session, obj)

                # 同步 InterfaceType 节点
                for rid, iface in registry.interface_types.items():
                    await self._upsert_interface_type(session, iface)

                # 同步 ActionType 节点
                for rid, action in registry.action_types.items():
                    await self._upsert_action_type(session, action)

                # 同步 LINK 关系
                for rid, link in registry.link_types.items():
                    await self._upsert_link_relation(session, link)

                # 同步 IMPLEMENTS 关系
                for rid, obj in registry.object_types.items():
                    for iface_rid in obj.implements_interface_type_rids:
                        await self._upsert_implements(session, rid, iface_rid)

                # 同步 ACTS_ON 关系（ActionType -> ObjectType）
                for rid, action in registry.action_types.items():
                    for obj_rid in action.edited_object_types:
                        await self._upsert_acts_on(session, rid, obj_rid)

                logger.info(f"Synced {len(registry.object_types)} ObjectTypes, "
                           f"{len(registry.interface_types)} InterfaceTypes, "
                           f"{len(registry.action_types)} ActionTypes to Neo4j")
        finally:
            await driver.close()

    async def _upsert_object_type(self, session, obj: ObjectTypeDefinition) -> None:
        """创建或更新 ObjectType 节点"""
        await session.run(
            """
            MERGE (n:ObjectType {rid: $rid})
            SET n.api_name = $api_name,
                n.display_name = $display_name,
                n.description = $description,
                n.lifecycle_status = $lifecycle_status
            """,
            rid=obj.rid,
            api_name=obj.api_name,
            display_name=obj.display_name or "",
            description=obj.description or "",
            lifecycle_status=obj.lifecycle_status.value if hasattr(obj.lifecycle_status, 'value') else str(obj.lifecycle_status),
        )

    async def _upsert_interface_type(self, session, iface: InterfaceTypeDefinition) -> None:
        """创建或更新 InterfaceType 节点"""
        await session.run(
            """
            MERGE (n:InterfaceType {rid: $rid})
            SET n.api_name = $api_name,
                n.display_name = $display_name,
                n.description = $description,
                n.category = $category
            """,
            rid=iface.rid,
            api_name=iface.api_name,
            display_name=iface.display_name or "",
            description=iface.description or "",
            category=iface.category.value if hasattr(iface.category, 'value') else str(iface.category),
        )

    async def _upsert_action_type(self, session, action: ActionTypeDefinition) -> None:
        """创建或更新 ActionType 节点"""
        await session.run(
            """
            MERGE (n:ActionType {rid: $rid})
            SET n.api_name = $api_name,
                n.display_name = $display_name,
                n.description = $description,
                n.safety_level = $safety_level
            """,
            rid=action.rid,
            api_name=action.api_name,
            display_name=action.display_name or "",
            description=action.description or "",
            safety_level=action.safety_level.value if hasattr(action.safety_level, 'value') else str(action.safety_level),
        )

    async def _upsert_link_relation(self, session, link: LinkTypeDefinition) -> None:
        """创建 LINK 关系"""
        if not link.source_object_type_rid or not link.target_object_type_rid:
            return
        await session.run(
            """
            MATCH (a:ObjectType {rid: $source_rid})
            MATCH (b:ObjectType {rid: $target_rid})
            MERGE (a)-[r:LINK]->(b)
            SET r.rid = $rid,
                r.api_name = $api_name,
                r.display_name = $display_name,
                r.description = $description,
                r.cardinality = $cardinality
            """,
            rid=link.rid,
            source_rid=link.source_object_type_rid,
            target_rid=link.target_object_type_rid,
            api_name=link.api_name or "",
            display_name=link.display_name or "",
            description=link.description or "",
            cardinality=link.cardinality.value if hasattr(link.cardinality, 'value') else str(link.cardinality),
        )

    async def _upsert_implements(self, session, obj_rid: str, iface_rid: str) -> None:
        """创建 IMPLEMENTS 关系"""
        await session.run(
            """
            MATCH (o:ObjectType {rid: $obj_rid})
            MATCH (i:InterfaceType {rid: $iface_rid})
            MERGE (o)-[r:IMPLEMENTS]->(i)
            """,
            obj_rid=obj_rid,
            iface_rid=iface_rid,
        )

    async def _upsert_acts_on(self, session, action_rid: str, obj_rid: str) -> None:
        """创建 ACTS_ON 关系"""
        await session.run(
            """
            MATCH (a:ActionType {rid: $action_rid})
            MATCH (o:ObjectType {rid: $obj_rid})
            MERGE (a)-[r:ACTS_ON]->(o)
            """,
            action_rid=action_rid,
            obj_rid=obj_rid,
        )
