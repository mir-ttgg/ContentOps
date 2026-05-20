from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class AdminRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    EDITOR = "editor"


class Admin(Base, TimestampMixin):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[AdminRole] = mapped_column(
        Enum(
            AdminRole, name="admin_role",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        ),
        default=AdminRole.EDITOR, nullable=False,
    )
