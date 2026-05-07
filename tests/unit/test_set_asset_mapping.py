import pytest
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, AssetMapping,
)
from onto_platform.registry.crud import set_asset_mapping, ValidationFailedError


OBJ_RID = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_set_asset_mapping_updates_only_mapping():
    obj = ObjectTypeDefinition(rid=OBJ_RID, api_name="x", description="orig")
    reg = OntologyRegistry(version="1", object_types={OBJ_RID: obj})
    am = AssetMapping(read_connection_id="conn-1", read_asset_path="db.t")
    out = set_asset_mapping(reg, OBJ_RID, am, connection_ids={"conn-1"})
    o = out.object_types[OBJ_RID]
    assert o.asset_mapping == am
    assert o.description == "orig"  # other fields preserved


def test_set_asset_mapping_unknown_target_raises():
    reg = OntologyRegistry(version="1")
    with pytest.raises(KeyError):
        set_asset_mapping(reg, OBJ_RID, AssetMapping(), connection_ids=set())


def test_set_asset_mapping_validates_connection():
    obj = ObjectTypeDefinition(rid=OBJ_RID, api_name="x")
    reg = OntologyRegistry(version="1", object_types={OBJ_RID: obj})
    am = AssetMapping(read_connection_id="missing", read_asset_path="db.t")
    with pytest.raises(ValidationFailedError):
        set_asset_mapping(reg, OBJ_RID, am, connection_ids=set())
