"""Create webapi_messages table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230001"
down_revision: str | Sequence[str] | None = "202607020001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create webapi_messages table."""
    op.create_table(
        "webapi_messages",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(length=256), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webapi_messages_id"), "webapi_messages", ["id"])
    op.create_index(
        op.f("ix_webapi_messages_session_id"),
        "webapi_messages",
        ["session_id"],
    )


def downgrade() -> None:
    """Drop webapi_messages table."""
    op.drop_index(op.f("ix_webapi_messages_session_id"), table_name="webapi_messages")
    op.drop_index(op.f("ix_webapi_messages_id"), table_name="webapi_messages")
    op.drop_table("webapi_messages")
