"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUMS = {
    "post_status": (
        "draft", "pending_approval", "approved",
        "published", "rejected", "deleted",
    ),
    "post_source": ("manual", "ai_auto", "ai_manual"),
    "media_type": ("none", "photo", "video", "document"),
    "moderation_action": (
        "approved", "rejected", "auto_deleted", "flagged", "edited",
    ),
    "admin_role": ("superadmin", "editor"),
}


def _ensure_enum(name: str, values: tuple[str, ...]) -> None:
    vals = ", ".join(f"'{v}'" for v in values)
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {name} AS ENUM ({vals});
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )


def upgrade() -> None:
    for name, values in ENUMS.items():
        _ensure_enum(name, values)

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id              SERIAL PRIMARY KEY,
            tg_channel_id   BIGINT NOT NULL UNIQUE,
            name            VARCHAR(255) NOT NULL,
            username        VARCHAR(255),
            system_prompt   TEXT NOT NULL DEFAULT '',
            settings_json   JSON NOT NULL DEFAULT '{}'::json,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id              SERIAL PRIMARY KEY,
            channel_id      INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            text            TEXT NOT NULL DEFAULT '',
            media_url       VARCHAR(1024),
            media_file_id   VARCHAR(512),
            media_type      media_type NOT NULL DEFAULT 'none',
            status          post_status NOT NULL DEFAULT 'draft',
            source          post_source NOT NULL DEFAULT 'manual',
            scheduled_at    TIMESTAMPTZ,
            published_at    TIMESTAMPTZ,
            tg_message_id   BIGINT,
            created_by      BIGINT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_posts_channel_id ON posts(channel_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_posts_status ON posts(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_posts_scheduled_at ON posts(scheduled_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id              SERIAL PRIMARY KEY,
            post_id         INTEGER REFERENCES posts(id) ON DELETE SET NULL,
            action          moderation_action NOT NULL,
            reason          TEXT NOT NULL DEFAULT '',
            triggered_by    VARCHAR(64) NOT NULL DEFAULT 'system',
            actor_id        BIGINT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_moderation_logs_post_id "
        "ON moderation_logs(post_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_slots (
            id              SERIAL PRIMARY KEY,
            channel_id      INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            time_of_day     TIME NOT NULL,
            days_of_week    VARCHAR(32) NOT NULL DEFAULT '',
            enabled         BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_schedule_slots_channel_id "
        "ON schedule_slots(channel_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id              SERIAL PRIMARY KEY,
            tg_user_id      BIGINT NOT NULL UNIQUE,
            username        VARCHAR(255),
            role            admin_role NOT NULL DEFAULT 'editor',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    for table in (
        "admins", "schedule_slots", "moderation_logs", "posts", "channels",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    for name in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name};")
