"""ingestion tables

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_uploads",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_token_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.CheckConstraint("kind IN ('sql','pdf','docx','pptx','xlsx')", name="ingestion_uploads_kind_chk"),
    )
    op.create_index("ix_ingestion_uploads_job_id", "ingestion_uploads", ["job_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("phase_message", sa.Text, server_default=""),
        sa.Column("progress_pct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("decisions_report", sa.dialects.postgresql.JSONB),
        sa.Column("staging_version_after", sa.Integer),
        sa.Column("error_code", sa.Text),
        sa.Column("error_details", sa.dialects.postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_token_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("mode IN ('replace','merge')", name="ingestion_jobs_mode_chk"),
        sa.CheckConstraint(
            "status IN ('queued','extracting','agent_running','validating','imported','failed','cancelled')",
            name="ingestion_jobs_status_chk",
        ),
    )
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_created_at", "ingestion_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("ingestion_uploads")
