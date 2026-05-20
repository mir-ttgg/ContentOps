"""per-user channel ownership

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE channels ADD COLUMN IF NOT EXISTS owner_tg_id BIGINT NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE channels ALTER COLUMN owner_tg_id DROP DEFAULT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_channels_owner_tg_id ON channels(owner_tg_id)"
    )

    op.execute("ALTER TABLE channels DROP CONSTRAINT IF EXISTS channels_tg_channel_id_key")
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE channels
                ADD CONSTRAINT uq_channels_owner_tg UNIQUE (owner_tg_id, tg_channel_id);
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE channels DROP CONSTRAINT IF EXISTS uq_channels_owner_tg")
    op.execute("DROP INDEX IF EXISTS ix_channels_owner_tg_id")
    op.execute("ALTER TABLE channels DROP COLUMN IF EXISTS owner_tg_id")
    op.execute(
        "ALTER TABLE channels ADD CONSTRAINT channels_tg_channel_id_key UNIQUE (tg_channel_id)"
    )
