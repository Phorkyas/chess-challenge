from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import SECRET_KEY
from app.database import get_db
from app.models import User

serializer = URLSafeSerializer(SECRET_KEY, salt="session")
COOKIE_NAME = "chess_session"


def set_session(response: RedirectResponse, user_id: int):
    response.set_cookie(
        COOKIE_NAME,
        serializer.dumps(user_id),
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
    )


def clear_session(response: RedirectResponse):
    response.delete_cookie(COOKIE_NAME)


async def current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401)
    try:
        user_id = serializer.loads(cookie)
    except Exception:
        raise HTTPException(status_code=401)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401)
    return user


async def current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    try:
        user_id = serializer.loads(cookie)
    except Exception:
        return None
    return await db.get(User, user_id)
