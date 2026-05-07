from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, LifecycleStatus,
)
from onto_platform.ingestion.working_registry import WorkingRegistry


OBJ_RID = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_initialized_from_existing_registry():
    base = OntologyRegistry(version="x", object_types={
        OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="material",
                                       lifecycle_status=LifecycleStatus.ACTIVE),
    })
    wr = WorkingRegistry.from_registry(base)
    assert OBJ_RID in wr.snapshot().object_types


def test_initialized_empty():
    wr = WorkingRegistry.empty()
    snap = wr.snapshot()
    assert snap.version == "__empty__"
    assert snap.object_types == {}


def test_snapshot_is_independent_copy():
    base = OntologyRegistry(version="x")
    wr = WorkingRegistry.from_registry(base)
    snap1 = wr.snapshot()
    wr._registry = wr._registry.model_copy(update={"version": "y"})
    snap2 = wr.snapshot()
    assert snap1.version == "x"
    assert snap2.version == "y"
