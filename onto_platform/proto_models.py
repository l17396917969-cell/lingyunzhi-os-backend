from enum import Enum
from pydantic import BaseModel, ConfigDict


class _StrEnum(str, Enum):
    pass


class DataType(_StrEnum):
    DT_UNKNOWN = "DT_UNKNOWN"
    DT_STRING = "DT_STRING"
    DT_INTEGER = "DT_INTEGER"
    DT_DOUBLE = "DT_DOUBLE"
    DT_BOOLEAN = "DT_BOOLEAN"
    DT_TIMESTAMP = "DT_TIMESTAMP"
    DT_DATE = "DT_DATE"
    DT_ATTACHMENT = "DT_ATTACHMENT"


class LifecycleStatus(_StrEnum):
    LIFECYCLE_UNSPECIFIED = "LIFECYCLE_UNSPECIFIED"
    ACTIVE = "ACTIVE"
    EXPERIMENTAL = "EXPERIMENTAL"
    DEPRECATED = "DEPRECATED"
    EXAMPLE = "EXAMPLE"


class Sensitivity(_StrEnum):
    SENSITIVITY_UNSPECIFIED = "SENSITIVITY_UNSPECIFIED"
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class MaskingStrategy(_StrEnum):
    MASK_NONE = "MASK_NONE"
    MASK_NULLIFY = "MASK_NULLIFY"
    MASK_REDACT_FULL = "MASK_REDACT_FULL"
    SHOW_LAST_4 = "SHOW_LAST_4"
    SHOW_FIRST_2 = "SHOW_FIRST_2"
    MASK_EMAIL_DOMAIN = "MASK_EMAIL_DOMAIN"
    MASK_EMAIL_USER = "MASK_EMAIL_USER"
    MASK_PHONE_MIDDLE = "MASK_PHONE_MIDDLE"


class InterfaceCategory(_StrEnum):
    INTERFACE_CATEGORY_INVALID = "INTERFACE_CATEGORY_INVALID"
    OBJECT_INTERFACE = "OBJECT_INTERFACE"
    LINK_INTERFACE = "LINK_INTERFACE"


class Cardinality(_StrEnum):
    CARDINALITY_UNSPECIFIED = "CARDINALITY_UNSPECIFIED"
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_MANY = "MANY_TO_MANY"


class _ProtoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class ComplianceConfig(_ProtoModel):
    sensitivity: Sensitivity = Sensitivity.SENSITIVITY_UNSPECIFIED
    masking: MaskingStrategy = MaskingStrategy.MASK_NONE


class AssetMapping(_ProtoModel):
    read_connection_id: str = ""
    read_asset_path: str = ""
    writeback_enabled: bool = False
    writeback_connection_id: str = ""
    writeback_asset_path: str = ""


from typing import Optional


class NotNullRule(_ProtoModel):
    pass


class RangeRule(_ProtoModel):
    min: Optional[float] = None
    max: Optional[float] = None
    min_inclusive: bool = True
    max_inclusive: bool = True


class LengthRule(_ProtoModel):
    min_length: Optional[int] = None
    max_length: Optional[int] = None


class PatternRule(_ProtoModel):
    regex: str


class EnumValue(_ProtoModel):
    value: str
    display_name: str = ""


class EnumRule(_ProtoModel):
    allowed_values: list[EnumValue] = []


class PropertyValidationRule(_ProtoModel):
    error_message: str = ""
    not_null: Optional[NotNullRule] = None
    range: Optional[RangeRule] = None
    length: Optional[LengthRule] = None
    pattern: Optional[PatternRule] = None
    enum_values: Optional[EnumRule] = None


class PropertyValidationConfig(_ProtoModel):
    rules: list[PropertyValidationRule] = []


class CrossPropertyExpression(_ProtoModel):
    expression: str


class EntityValidationRule(_ProtoModel):
    error_message: str = ""
    cross_property: Optional[CrossPropertyExpression] = None


class EntityValidationConfig(_ProtoModel):
    rules: list[EntityValidationRule] = []


from typing import Any


class SharedPropertyTypeDefinition(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.LIFECYCLE_UNSPECIFIED
    data_type: DataType = DataType.DT_UNKNOWN
    widget: dict[str, Any] = {}
    validation: PropertyValidationConfig = PropertyValidationConfig()
    compliance: ComplianceConfig = ComplianceConfig()


class PropertyTypeDefinition(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.LIFECYCLE_UNSPECIFIED
    data_type: DataType = DataType.DT_UNKNOWN
    inherit_from_shared_property_type_rid: str = ""
    physical_column: str = ""
    virtual_expression: str = ""
    widget: dict[str, Any] = {}
    validation: PropertyValidationConfig = PropertyValidationConfig()
    compliance: ComplianceConfig = ComplianceConfig()


class ObjectTypeSpec(_ProtoModel):
    class ReferenceType(_StrEnum):
        REFERENCE_TYPE_INVALID = "REFERENCE_TYPE_INVALID"
        SELF = "SELF"
        EXPLICIT_OBJECT = "EXPLICIT_OBJECT"
        EXPLICIT_INTERFACE = "EXPLICIT_INTERFACE"

    reference_type: "ObjectTypeSpec.ReferenceType" = ReferenceType.REFERENCE_TYPE_INVALID
    object_type_rid: str = ""
    interface_type_rid: str = ""


class ObjectLinkRequirement(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    cardinality: Cardinality = Cardinality.CARDINALITY_UNSPECIFIED
    source_object: ObjectTypeSpec = ObjectTypeSpec()
    target_object: ObjectTypeSpec = ObjectTypeSpec()


class LinkObjectConstraint(_ProtoModel):
    source_object: ObjectTypeSpec = ObjectTypeSpec()
    target_object: ObjectTypeSpec = ObjectTypeSpec()


class InterfaceTypeDefinition(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.LIFECYCLE_UNSPECIFIED
    category: InterfaceCategory = InterfaceCategory.INTERFACE_CATEGORY_INVALID
    extends_interface_type_rids: list[str] = []
    required_shared_property_type_rids: list[str] = []
    link_requirements: list[ObjectLinkRequirement] = []
    object_constraint: LinkObjectConstraint | None = None


class ObjectTypeDefinition(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.LIFECYCLE_UNSPECIFIED
    property_types: dict[str, PropertyTypeDefinition] = {}
    implements_interface_type_rids: list[str] = []
    primary_key_property_type_rids: list[str] = []
    validation: EntityValidationConfig = EntityValidationConfig()
    asset_mapping: AssetMapping = AssetMapping()


class LinkTypeDefinition(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.LIFECYCLE_UNSPECIFIED
    source_object_type_rid: str = ""
    source_interface_type_rid: str = ""
    target_object_type_rid: str = ""
    target_interface_type_rid: str = ""
    property_types: dict[str, PropertyTypeDefinition] = {}
    cardinality: Cardinality = Cardinality.CARDINALITY_UNSPECIFIED
    primary_key_property_type_rids: list[str] = []
    validation: EntityValidationConfig = EntityValidationConfig()
    implements_interface_type_rids: list[str] = []
    asset_mapping: AssetMapping = AssetMapping()


class ActionSafetyLevel(_StrEnum):
    SAFETY_UNSPECIFIED = "SAFETY_UNSPECIFIED"
    SAFETY_READ_ONLY = "SAFETY_READ_ONLY"
    SAFETY_IDEMPOTENT_WRITE = "SAFETY_IDEMPOTENT_WRITE"
    SAFETY_NON_IDEMPOTENT = "SAFETY_NON_IDEMPOTENT"
    SAFETY_CRITICAL = "SAFETY_CRITICAL"


class SideEffectCategory(_StrEnum):
    CATEGORY_UNSPECIFIED = "CATEGORY_UNSPECIFIED"
    DATA_MUTATION = "DATA_MUTATION"
    DATA_DELETION = "DATA_DELETION"
    NOTIFICATION = "NOTIFICATION"
    EXTERNAL_API_CALL = "EXTERNAL_API_CALL"
    BILLING_EVENT = "BILLING_EVENT"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    OTHER = "OTHER"


class ActionParameter(_ProtoModel):
    api_name: str
    display_name: str = ""
    description: str = ""
    required: bool = False
    explicit_type: DataType | None = None
    derived_from_object_type_rid: str = ""
    derived_from_link_type_rid: str = ""
    derived_from_interface_type_rid: str = ""


class ActionExecutionConfig(_ProtoModel):
    class EngineType(_StrEnum):
        ENGINE_UNSPECIFIED = "ENGINE_UNSPECIFIED"
        ENGINE_NATIVE_CRUD = "ENGINE_NATIVE_CRUD"
        ENGINE_PYTHON_VENV = "ENGINE_PYTHON_VENV"
        ENGINE_SQL_RUNNER = "ENGINE_SQL_RUNNER"
        ENGINE_WEBHOOK = "ENGINE_WEBHOOK"

    type: "ActionExecutionConfig.EngineType" = EngineType.ENGINE_UNSPECIFIED
    is_batch: bool = False
    is_sync: bool = True
    native_crud_json: str = ""
    python_script: str = ""
    sql_template: str = ""
    webhook_config_json: str = ""


class EditDeclaration(_ProtoModel):
    edit_type: str = ""
    object_type: str = ""
    target_object_type: str = ""
    property_updates: list[dict[str, Any]] = []
    target_property: str = ""
    property_value_change: str = ""
    condition: str = ""
    error_message: str = ""



class SideEffectDeclaration(_ProtoModel):
    category: SideEffectCategory = SideEffectCategory.CATEGORY_UNSPECIFIED
    description: str = ""


class ActionTypeDefinition(_ProtoModel):
    rid: str
    api_name: str = ""
    display_name: str = ""
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.LIFECYCLE_UNSPECIFIED
    parameters: list[ActionParameter] = []
    execution: ActionExecutionConfig = ActionExecutionConfig()
    safety_level: ActionSafetyLevel = ActionSafetyLevel.SAFETY_UNSPECIFIED
    side_effects: list[SideEffectDeclaration] = []
    edited_object_types: list[str] = []
    edits: list[EditDeclaration] = []


EMPTY_REGISTRY_VERSION = "__empty__"


class OntologyRegistry(_ProtoModel):
    version: str = ""
    shared_property_types: dict[str, SharedPropertyTypeDefinition] = {}
    interface_types: dict[str, InterfaceTypeDefinition] = {}
    object_types: dict[str, ObjectTypeDefinition] = {}
    link_types: dict[str, LinkTypeDefinition] = {}
    action_types: dict[str, ActionTypeDefinition] = {}


def empty_registry() -> OntologyRegistry:
    return OntologyRegistry(version=EMPTY_REGISTRY_VERSION)
