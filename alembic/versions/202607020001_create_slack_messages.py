"""Create slack_messages table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607020001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create slack_messages table."""
    op.create_table(
        "slack_messages",
        sa.Column("channel_id", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("slack_event_ts", sa.String(length=64), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_slack_messages_channel_id"), "slack_messages", ["channel_id"])
    op.create_index(op.f("ix_slack_messages_id"), "slack_messages", ["id"])


def downgrade() -> None:
    """Drop slack_messages table."""
    op.drop_index(op.f("ix_slack_messages_id"), table_name="slack_messages")
    op.drop_index(op.f("ix_slack_messages_channel_id"), table_name="slack_messages")
    op.drop_table("slack_messages")
