# Importing this module is what registers checkers via @checker decorators.
from onto_platform.registry.checks import (  # noqa: F401
    structural, refs, interface_category, property_backing,
    asset_mapping, cross_property,
)
