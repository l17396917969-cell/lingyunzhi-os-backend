from onto_platform.proto_models import (
    SharedPropertyTypeDefinition, InterfaceTypeDefinition,
    ObjectTypeDefinition, LinkTypeDefinition, ActionTypeDefinition,
    AssetMapping, OntologyRegistry,
)
from onto_platform.registry.crud import (
    put_shared_property_type, delete_shared_property_type,
    put_interface_type, delete_interface_type,
    put_object_type, delete_object_type,
    put_link_type, delete_link_type,
    put_action_type, delete_action_type,
    set_asset_mapping,
)
from onto_platform.registry.imports import import_into_registry, ImportMode
from onto_platform.ingestion.working_registry import WorkingRegistry


def working_put_shared_property_type(wr: WorkingRegistry, defn: SharedPropertyTypeDefinition, *, connection_ids: set[str]) -> None:
    wr.replace(put_shared_property_type(wr.registry, defn, connection_ids=connection_ids))


def working_delete_shared_property_type(wr: WorkingRegistry, rid: str) -> None:
    wr.replace(delete_shared_property_type(wr.registry, rid))


def working_put_interface_type(wr: WorkingRegistry, defn: InterfaceTypeDefinition, *, connection_ids: set[str]) -> None:
    wr.replace(put_interface_type(wr.registry, defn, connection_ids=connection_ids))


def working_delete_interface_type(wr: WorkingRegistry, rid: str) -> None:
    wr.replace(delete_interface_type(wr.registry, rid))


def working_put_object_type(wr: WorkingRegistry, defn: ObjectTypeDefinition, *, connection_ids: set[str]) -> None:
    wr.replace(put_object_type(wr.registry, defn, connection_ids=connection_ids))


def working_delete_object_type(wr: WorkingRegistry, rid: str) -> None:
    wr.replace(delete_object_type(wr.registry, rid))


def working_put_link_type(wr: WorkingRegistry, defn: LinkTypeDefinition, *, connection_ids: set[str]) -> None:
    wr.replace(put_link_type(wr.registry, defn, connection_ids=connection_ids))


def working_delete_link_type(wr: WorkingRegistry, rid: str) -> None:
    wr.replace(delete_link_type(wr.registry, rid))


def working_put_action_type(wr: WorkingRegistry, defn: ActionTypeDefinition, *, connection_ids: set[str]) -> None:
    wr.replace(put_action_type(wr.registry, defn, connection_ids=connection_ids))


def working_delete_action_type(wr: WorkingRegistry, rid: str) -> None:
    wr.replace(delete_action_type(wr.registry, rid))


def working_set_asset_mapping(wr: WorkingRegistry, target_rid: str, am: AssetMapping, *, connection_ids: set[str]) -> None:
    wr.replace(set_asset_mapping(wr.registry, target_rid, am, connection_ids=connection_ids))


def working_import(wr: WorkingRegistry, incoming: OntologyRegistry, *, mode: ImportMode, connection_ids: set[str]) -> None:
    wr.replace(import_into_registry(wr.registry, incoming, mode=mode, connection_ids=connection_ids))
