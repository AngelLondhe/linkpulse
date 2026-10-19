from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_db
from app.models import User
from app.routers.deps import get_current_user
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_response(user: User) -> AuthResponse:
    token = create_access_token(user.id)
    return AuthResponse(
        access_token=token.token,
        expires_in=token.expires_in,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = await auth_service.register_user(db, body.email, body.password)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = await auth_service.authenticate_user(db, body.email, body.password)
    return _auth_response(user)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
