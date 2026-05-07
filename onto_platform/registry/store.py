from dataclasses import dataclass
from enum import Enum
from typing import Optional, cast
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from onto_platform.proto_models import OntologyRegistry


class Env(str, Enum):
    staging = "staging"
    production = "production"
    previous_production = "previous_production"


@dataclass
class RegistrySnapshot:
    env: Env
    registry: OntologyRegistry
    version: int


class StaleVersionError(Exception):
    def __init__(self, env: Env, expected: int, current: int):
        super().__init__(
            f"Stale version on {env.value}: expected {expected}, current {current}"
        )
        self.env = env
        self.expected_version = expected
        self.current_version = current


class RegistryStore:
    async def load(self, session: AsyncSession, env: Env) -> RegistrySnapshot:
        row = await session.execute(
            text("SELECT payload, version FROM registries WHERE env = :e"),
            {"e": env.value},
        )
        rec = row.one()
        return RegistrySnapshot(
            env=env,
            registry=OntologyRegistry.model_validate(rec.payload),
            version=rec.version,
        )

    async def save(
        self,
        session: AsyncSession,
        env: Env,
        registry: OntologyRegistry,
        *,
        expected_version: Optional[int],
        token_label: Optional[str],
        commit_message: Optional[str] = None,
    ) -> int:
        # FOR UPDATE so two concurrent saves serialize
        cur = await session.execute(
            text("SELECT version FROM registries WHERE env = :e FOR UPDATE"),
            {"e": env.value},
        )
        current = cast(int, cur.scalar_one())
        if expected_version is not None and current != expected_version:
            raise StaleVersionError(env, expected_version, current)
        new_version = current + 1
        await session.execute(
            text(
                "UPDATE registries SET payload = CAST(:p AS jsonb), version = :v, "
                "updated_at = now(), updated_by_token_label = :u, "
                "last_commit_message = COALESCE(:m, last_commit_message) "
                "WHERE env = :e"
            ),
            {
                "p": registry.model_dump_json(),
                "v": new_version,
                "u": token_label,
                "m": commit_message,
                "e": env.value,
            },
        )
        return new_version
