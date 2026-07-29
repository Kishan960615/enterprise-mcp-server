"""Create audit and connector metadata tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("subject_id", sa.String(200), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("capability_name", sa.String(200)),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_tenant_time", "audit_events", ["tenant_id", "occurred_at"])
    op.create_index("ix_audit_request", "audit_events", ["request_id"])
    op.create_table(
        "connectors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_connector_tenant_name"),
    )
    op.create_index("ix_connectors_tenant", "connectors", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("connectors")
    op.drop_table("audit_events")
