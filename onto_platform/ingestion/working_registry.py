from onto_platform.proto_models import OntologyRegistry, empty_registry


class WorkingRegistry:
    def __init__(self, registry: OntologyRegistry) -> None:
        self._registry = registry

    @classmethod
    def empty(cls) -> "WorkingRegistry":
        return cls(empty_registry())

    @classmethod
    def from_registry(cls, registry: OntologyRegistry) -> "WorkingRegistry":
        return cls(registry.model_copy(deep=True))

    @property
    def registry(self) -> OntologyRegistry:
        return self._registry

    def replace(self, new: OntologyRegistry) -> None:
        self._registry = new

    def snapshot(self) -> OntologyRegistry:
        return self._registry.model_copy(deep=True)
