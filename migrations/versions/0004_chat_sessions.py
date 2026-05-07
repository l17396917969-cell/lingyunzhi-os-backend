"""chat sessions, messages, and ingestion_jobs.chat_session_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("pre_session_registry", postgresql.JSONB, nullable=False),
        sa.Column("pre_session_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_turn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active','saving','cancelling')",
            name="chat_sessions_status_check",
        ),
    )
    op.create_index(
        "chat_sessions_token_idx", "chat_sessions", ["token_id"], unique=False
    )
    op.create_index(
        "chat_sessions_active_idx",
        "chat_sessions",
        ["status", "last_turn_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN ('user','assistant','tool_call','tool_result')",
            name="chat_messages_role_check",
        ),
    )
    op.create_index(
        "chat_messages_session_idx", "chat_messages", ["session_id", "id"], unique=False
    )

    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "chat_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ingestion_jobs_chat_session_idx",
        "ingestion_jobs",
        ["chat_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ingestion_jobs_chat_session_idx", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "chat_session_id")
    op.drop_index("chat_messages_session_idx", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("chat_sessions_active_idx", table_name="chat_sessions")
    op.drop_index("chat_sessions_token_idx", table_name="chat_sessions")
    op.drop_table("chat_sessions")
