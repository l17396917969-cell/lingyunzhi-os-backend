# tests/unit/test_proto_models_action.py
from onto_platform.proto_models import (
    DataType, ActionTypeDefinition, ActionParameter,
    ActionExecutionConfig, ActionSafetyLevel,
    SideEffectDeclaration, SideEffectCategory,
)


def test_action_round_trip():
    a = ActionTypeDefinition(
        rid="ri.action.aaa",
        api_name="ship_material",
        parameters=[
            ActionParameter(
                api_name="material_rid",
                required=True,
                derived_from_object_type_rid="ri.obj.material",
            ),
            ActionParameter(
                api_name="qty",
                required=True,
                explicit_type=DataType.DT_INTEGER,
            ),
        ],
        execution=ActionExecutionConfig(
            type=ActionExecutionConfig.EngineType.ENGINE_NATIVE_CRUD,
            is_batch=False,
            is_sync=True,
            native_crud_json='{"op":"insert"}',
        ),
        safety_level=ActionSafetyLevel.SAFETY_NON_IDEMPOTENT,
        side_effects=[
            SideEffectDeclaration(
                category=SideEffectCategory.DATA_MUTATION,
                description="creates a shipment row",
            ),
        ],
    )
    j = a.model_dump_json()
    a2 = ActionTypeDefinition.model_validate_json(j)
    assert a == a2
