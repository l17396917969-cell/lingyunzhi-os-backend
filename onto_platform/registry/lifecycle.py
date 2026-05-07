from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from onto_platform.proto_models import empty_registry, EMPTY_REGISTRY_VERSION
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.crud import _validate_or_raise


async def promote_staging_to_production(
    session: AsyncSession,
    store: RegistryStore,
    *,
    commit_message: str,
    token_label: Optional[str],
    connection_ids: set[str],
) -> None:
    """Atomic: re-validate staging against live connection_ids; copy current
    production -> previous_production; copy staging -> production. Caller's
    transaction must wrap this call (the store uses FOR UPDATE)."""
    staging = await store.load(session, Env.staging)
    _validate_or_raise(staging.registry, connection_ids)
    production = await store.load(session, Env.production)
    prev_production = await store.load(session, Env.previous_production)
    await store.save(
        session, Env.previous_production, production.registry,
        expected_version=prev_production.version, token_label=token_label,
    )
    await store.save(
        session, Env.production, staging.registry,
        expected_version=production.version, token_label=token_label,
        commit_message=commit_message,
    )


async def revert_staging_to_production(
    session: AsyncSession,
    store: RegistryStore,
    *,
    token_label: Optional[str],
) -> None:
    production = await store.load(session, Env.production)
    staging = await store.load(session, Env.staging)
    await store.save(
        session, Env.staging, production.registry,
        expected_version=staging.version, token_label=token_label,
    )


class UndoUnavailableError(Exception):
    """Raised when undo_promote is called and previous_production is empty."""


async def undo_promote(
    session: AsyncSession,
    store: RegistryStore,
    *,
    token_label: Optional[str],
) -> None:
    prev = await store.load(session, Env.previous_production)
    if prev.registry.version == EMPTY_REGISTRY_VERSION:
        raise UndoUnavailableError("previous_production slot is empty; nothing to undo")
    production = await store.load(session, Env.production)
    await store.save(
        session, Env.production, prev.registry,
        expected_version=production.version, token_label=token_label,
    )
    await store.save(
        session, Env.previous_production, empty_registry(),
        expected_version=prev.version, token_label=token_label,
    )
