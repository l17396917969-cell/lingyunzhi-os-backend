# Ontology Evaluation Skill

You are an **ontology review specialist** for the LingShu/DataOS platform. Your task is to evaluate an existing `OntologyRegistry` JSON file for correctness, completeness, and modeling quality against the proto3 schema and LingShu conventions.

You will work through 5 phases, producing a structured evaluation report with severity-rated findings. **Present results at each phase; do not silently skip issues.**

---

## Input Parsing

Parse `$ARGUMENTS` to extract:

1. **Ontology file** (required): Path to the `OntologyRegistry` JSON file to evaluate
   - e.g., `./ontology_registry.json`, `./output/my_ontology.json`
2. **Proto reference** (optional): `--proto <dir>` — path to proto definitions directory (defaults to `./proto/`)
3. **Strictness level** (optional): `--strict` for zero-tolerance mode, default is normal
4. **Source schema** (optional): `--schema <path_or_connection>` — original SQL schema for completeness checking

If the ontology file path is missing, ask the user.

---

## Phase 1: Structural Validation

Validate that the JSON conforms to the `OntologyRegistry` proto3 message structure.

### 1.1 JSON Validity
- Parse the JSON file — report any syntax errors with line numbers
- Verify it is a JSON object (not array or primitive)

### 1.2 Top-Level Structure
- `version` field exists and is a non-empty string
- Exactly these top-level map fields exist: `shared_property_types`, `interface_types`, `object_types`, `link_types`, `action_types`
- No unexpected top-level fields

### 1.3 Entity Structure
For each entity in every map, validate required fields:

**All entities must have:**
- `rid` — non-empty string matching `ri.{prefix}.{uuid}` format
- `api_name` — non-empty string, valid snake_case (lowercase, digits, underscores only; no leading digit; no consecutive/trailing underscores)
- `display_name` — non-empty string
- `lifecycle_status` — valid enum string: `ACTIVE`, `EXPERIMENTAL`, `DEPRECATED`, `EXAMPLE`

**SharedPropertyTypeDefinition:**
- `data_type` — valid DataType enum string

**PropertyTypeDefinition:**
- `data_type` — valid DataType enum string
- `backing` oneof: exactly one of `physical_column` or `virtual_expression` should be set (or neither if inherited)

**InterfaceTypeDefinition:**
- `category` — must be `OBJECT_INTERFACE` or `LINK_INTERFACE` (NOT `INTERFACE_CATEGORY_INVALID`)
- If `OBJECT_INTERFACE`: `object_constraint` must NOT be set
- If `LINK_INTERFACE`: `link_requirements` must NOT be set

**ObjectTypeDefinition:**
- `property_types` — map should not be empty (an object without properties is suspicious)
- `primary_key_property_type_rids` — should not be empty

**LinkTypeDefinition:**
- At least one source (`source_object_type_rid` or `source_interface_type_rid`) must be set
- At least one target (`target_object_type_rid` or `target_interface_type_rid`) must be set
- `cardinality` — valid enum: `ONE_TO_ONE`, `ONE_TO_MANY`, `MANY_TO_MANY`

**ActionTypeDefinition:**
- `parameters` — each parameter must have `api_name` and exactly one `definition_source`
- `safety_level` — valid enum if set

### 1.4 Enum Validation
Verify all enum fields use valid string values:

| Field | Valid Values |
|-------|-------------|
| `data_type` | DT_STRING, DT_INTEGER, DT_DOUBLE, DT_BOOLEAN, DT_TIMESTAMP, DT_DATE, DT_ATTACHMENT |
| `lifecycle_status` | ACTIVE, EXPERIMENTAL, DEPRECATED, EXAMPLE |
| `cardinality` | ONE_TO_ONE, ONE_TO_MANY, MANY_TO_MANY |
| `category` | OBJECT_INTERFACE, LINK_INTERFACE |
| `sensitivity` | PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED |
| `masking` | MASK_NONE, MASK_NULLIFY, MASK_REDACT_FULL, SHOW_LAST_4, SHOW_FIRST_2, MASK_EMAIL_DOMAIN, MASK_EMAIL_USER, MASK_PHONE_MIDDLE |
| `safety_level` | SAFETY_READ_ONLY, SAFETY_IDEMPOTENT_WRITE, SAFETY_NON_IDEMPOTENT, SAFETY_CRITICAL |

### Output:
Report findings as a table:

```
| # | Severity | Entity | Field | Issue |
|---|----------|--------|-------|-------|
| 1 | ERROR | ri.obj.xxx | rid | RID prefix "ri.object" should be "ri.obj" |
| 2 | WARN | ri.obj.yyy | property_types | Empty property map |
```

Severity levels:
- **ERROR**: Proto schema violation — the JSON cannot be deserialized correctly
- **WARN**: Suspicious but technically valid — likely a mistake
- **INFO**: Style/convention deviation

---

## Phase 2: Referential Integrity

Validate all cross-entity references resolve correctly.

### 2.1 RID Consistency
- Every map key matches the `rid` field of its value (e.g., `"ri.obj.xxx": { "rid": "ri.obj.xxx", ... }`)
- No duplicate RIDs across the entire registry

### 2.2 SharedPropertyType References
- Every `inherit_from_shared_property_type_rid` in PropertyTypes points to an existing SharedPropertyType
- When a PropertyType inherits from a SharedPropertyType, `data_type` must match (cannot override data_type)

### 2.3 InterfaceType References
- Every RID in `implements_interface_type_rids` (on ObjectType/LinkType) points to an existing InterfaceType
- Every RID in `extends_interface_type_rids` (on InterfaceType) points to an existing InterfaceType
- No circular inheritance in `extends_interface_type_rids` chains (detect via DFS)
- Every RID in `required_shared_property_type_rids` points to an existing SharedPropertyType
- **Category match**: ObjectTypes only implement `OBJECT_INTERFACE`; LinkTypes can implement `LINK_INTERFACE`

### 2.4 LinkType Endpoint References
- Every `source_object_type_rid` / `target_object_type_rid` points to an existing ObjectType
- Every `source_interface_type_rid` / `target_interface_type_rid` points to an existing InterfaceType
- Exactly one source oneof and one target oneof is set (not both object and interface for the same end)

### 2.5 Primary Key References
- Every RID in `primary_key_property_type_rids` points to a PropertyType **within the same entity**
- Referenced PropertyType exists in the entity's `property_types` map

### 2.6 ActionType References
- Every `derived_from_object_type_rid` points to an existing ObjectType
- Every `derived_from_link_type_rid` points to an existing LinkType
- Every `derived_from_interface_type_rid` points to an existing InterfaceType

### 2.7 ObjectLinkRequirement References (in InterfaceType)
- `source_object` and `target_object` ObjectTypeSpec references resolve:
  - `EXPLICIT_OBJECT` → `object_type_rid` exists in `object_types`
  - `EXPLICIT_INTERFACE` → `interface_type_rid` exists in `interface_types`
  - `SELF` → no reference needed

### Output:
Report all broken references with full context:

```
| # | Severity | Source Entity | Reference Field | Target RID | Issue |
|---|----------|-------------|-----------------|------------|-------|
| 1 | ERROR | ri.obj.xxx (robot) | implements_interface_type_rids[0] | ri.iface.999 | Target InterfaceType not found |
| 2 | ERROR | ri.link.yyy | source_object_type_rid | ri.obj.888 | Target ObjectType not found |
```

---

## Phase 3: Interface Contract Compliance

Validate that entities satisfy the contracts of the interfaces they implement.

### 3.1 Property Requirements
For each ObjectType/LinkType that implements an InterfaceType:
1. Collect all `required_shared_property_type_rids` from the InterfaceType (including inherited interfaces via `extends_interface_type_rids` — walk the full chain)
2. For each required SharedPropertyType RID, check that the implementing entity has **at least one PropertyType** with `inherit_from_shared_property_type_rid` pointing to that SharedPropertyType
3. Report missing required properties

### 3.2 Link Requirements (OBJECT_INTERFACE only)
For each ObjectType implementing an InterfaceType with `link_requirements`:
1. For each `ObjectLinkRequirement`, verify that a matching LinkType exists in `link_types` where:
   - The ObjectType appears as source or target (depending on the requirement's `source_object`/`target_object` specs)
   - Cardinality matches the requirement
2. Report missing required links

### 3.3 Object Constraints (LINK_INTERFACE only)
For each LinkType implementing an InterfaceType with `object_constraint`:
1. Verify the LinkType's source/target types satisfy the constraint's `source_object`/`target_object` specs
2. Report violations

### Output:
```
| # | Severity | Entity | Interface | Requirement | Issue |
|---|----------|--------|-----------|-------------|-------|
| 1 | ERROR | ri.obj.xxx (robot) | auditable | created_at (ri.shprop.aaa) | Missing property inheriting from required SharedPropertyType |
| 2 | WARN | ri.obj.yyy (station) | locatable | link: connects_to_zone | No matching LinkType found for link requirement |
```

---

## Phase 4: Modeling Quality Assessment

Assess the ontology's design quality. These are recommendations, not hard errors.

### 4.1 SharedPropertyType Reuse
- Scan all PropertyTypes across all ObjectTypes and LinkTypes
- Identify columns with the **same api_name AND same data_type** appearing in 3+ entities but NOT inheriting from a SharedPropertyType
- Recommend creating SharedPropertyTypes for these

### 4.2 InterfaceType Coverage
- Identify groups of ObjectTypes that share the same set of SharedPropertyType-backed properties but don't implement a common InterfaceType
- Recommend creating InterfaceTypes for these patterns

### 4.3 Naming Consistency
- Check `api_name` patterns within the same entity type (e.g., all ObjectTypes should follow a consistent naming pattern)
- Flag inconsistencies: mixing singular/plural (`robot` vs `tasks`), inconsistent prefixes
- Check `display_name` consistency: are they all Title Case? Are abbreviations consistent?

### 4.4 Graph Connectivity
- Identify **orphan ObjectTypes**: ObjectTypes that are neither source nor target of any LinkType (isolated nodes)
- Identify **orphan InterfaceTypes**: InterfaceTypes that no ObjectType/LinkType implements
- Identify **orphan SharedPropertyTypes**: SharedPropertyTypes that no PropertyType inherits and no InterfaceType requires

### 4.5 Cardinality Assessment
- Flag `MANY_TO_MANY` LinkTypes that have no properties — are they modeled correctly, or should they be simplified?
- Flag `ONE_TO_ONE` links — could these be properties instead of separate links?

### 4.6 AssetMapping Completeness
- Check that every ObjectType and LinkType has an `asset_mapping` with at least `read_asset_path`
- Flag placeholder values like `"TODO_CONNECTION_ID"` as INFO

### 4.7 Validation Coverage
- Calculate percentage of PropertyTypes that have at least one validation rule
- Flag properties that are likely candidates for validation but have none:
  - `DT_STRING` properties without length validation
  - `DT_INTEGER` / `DT_DOUBLE` properties that look like percentages/scores without range validation
  - Properties with names suggesting constrained values (`status`, `type`, `category`) without EnumRule

### 4.8 Compliance Coverage
- Flag properties with names suggesting sensitive data but no ComplianceConfig:
  - `email`, `phone`, `ssn`, `password`, `token`, `secret`, `address`

### Output:
Present findings grouped by category with counts:

```
## Quality Summary

| Category | Findings | Top Severity |
|----------|----------|-------------|
| SharedPropertyType Reuse | 3 opportunities | INFO |
| Naming Consistency | 2 issues | WARN |
| Orphan Entities | 1 orphan ObjectType | WARN |
| Validation Coverage | 45% (18/40 properties) | INFO |
| Compliance Gaps | 2 sensitive fields uncovered | WARN |
```

Then list each finding with recommendation.

---

## Phase 5: Evaluation Report

### 5.1 Completeness Check (if --schema provided)
If the user provided the original SQL schema:
1. Compare tables in the schema vs ObjectTypes + LinkTypes in the ontology
2. Report tables missing from the ontology
3. Report columns missing from mapped entities
4. Report FK relationships not represented as LinkTypes

### 5.2 Summary Scorecard

Produce a final scorecard:

```
## Ontology Evaluation Report

### Registry Stats
- Version: {version}
- SharedPropertyTypes: N
- InterfaceTypes: N
- ObjectTypes: N (total properties: M)
- LinkTypes: N (total properties: M)
- ActionTypes: N

### Evaluation Results
| Phase | Errors | Warnings | Info |
|-------|--------|----------|------|
| 1. Structural Validation | X | Y | Z |
| 2. Referential Integrity | X | Y | Z |
| 3. Interface Compliance | X | Y | Z |
| 4. Modeling Quality | X | Y | Z |
| 5. Completeness | X | Y | Z |
| **Total** | **X** | **Y** | **Z** |

### Verdict
- PASS: 0 errors, ontology is proto-compliant and well-modeled
- PASS WITH WARNINGS: 0 errors but warnings exist, review recommended
- FAIL: errors found, must fix before use
```

### 5.3 Actionable Recommendations

List the top 5 most impactful fixes/improvements, ordered by severity then impact:

```
### Top Recommendations
1. [ERROR] Fix broken reference: ri.obj.xxx → ri.iface.999 (InterfaceType not found)
2. [ERROR] Add missing required property: robot needs created_at for auditable interface
3. [WARN] Create SharedPropertyType for "status" (used in 5 entities with same type)
4. [WARN] ObjectType "warehouse" is orphaned — no links connect to it
5. [INFO] Add validation rules to 22 properties that currently have none
```

Ask: "Would you like me to auto-fix any of the ERROR or WARN findings?"

---

## Severity Reference

| Severity | Meaning | Action Required |
|----------|---------|----------------|
| **ERROR** | Proto schema violation or broken reference — the ontology will fail at runtime | Must fix |
| **WARN** | Likely a mistake or significant quality gap — the ontology works but is suboptimal | Should fix |
| **INFO** | Convention deviation or improvement opportunity — nice to have | Optional |
