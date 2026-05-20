"""Telegram WebApp initData verification.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status
from sqlalchemy import select

from config import settings
from models import Admin
from models.db import SessionLocal


def _secret_key() -> bytes:
    return hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()


def verify_init_data(init_data: str, max_age_seconds: int = 3600) -> dict:
    if not init_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash")

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    expected = hmac.new(_secret_key(), data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad hash")

    auth_date = int(pairs.get("auth_date", "0"))
    if auth_date and time.time() - auth_date > max_age_seconds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")

    user_raw = pairs.get("user")
    user = json.loads(user_raw) if user_raw else None
    return {"user": user, "raw": pairs}


async def require_admin(
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> int:
    """FastAPI dependency: validates initData and returns the admin's tg_user_id.

    Allowed users: superadmins from .env and anyone with a row in the `admins`
    table (created when the user redeems a promo code via the bot).
    """
    if not settings.bot_token:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Bot token not configured")
    data = verify_init_data(x_telegram_init_data)
    user = data.get("user") or {}
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No user in initData")
    if user_id in settings.superadmin_ids:
        return user_id

    async with SessionLocal() as session:
        result = await session.execute(select(Admin).where(Admin.tg_user_id == user_id))
        if result.scalar_one_or_none() is not None:
            return user_id

    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not an admin")
