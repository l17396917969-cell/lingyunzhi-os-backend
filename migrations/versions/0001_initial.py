"""initial schema: registries, api_tokens, connections, audit_log

Revision ID: 0001
Revises:
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


EMPTY_REGISTRY = '{"version": "__empty__", "shared_property_types": {}, "interface_types": {}, "object_types": {}, "link_types": {}, "action_types": {}}'


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "registries",
        sa.Column("env", sa.Text, primary_key=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by_token_label", sa.Text),
        sa.Column("last_commit_message", sa.Text),
        sa.CheckConstraint("env IN ('staging','production','previous_production')", name="registries_env_chk"),
    )

    for env in ("staging", "production", "previous_production"):
        op.execute(f"INSERT INTO registries (env, payload) VALUES ('{env}', '{EMPTY_REGISTRY}'::jsonb)")

    op.create_table(
        "api_tokens",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("token_prefix", sa.Text, nullable=False, index=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_token_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("scope IN ('read','editor','admin')", name="api_tokens_scope_chk"),
    )

    op.create_table(
        "connections",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.Text, nullable=False, unique=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("dsn_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_probe_ok_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('postgres','mysql','sqlite')", name="connections_kind_chk"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("token_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("token_label", sa.Text),
        sa.Column("scope", sa.Text),
        sa.Column("tool", sa.Text, nullable=False),
        sa.Column("args_summary", sa.dialects.postgresql.JSONB),
        sa.Column("outcome", sa.Text, nullable=False),
        sa.Column("error_code", sa.Text),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("connections")
    op.drop_table("api_tokens")
    op.drop_table("registries")
