from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(tags=["auth"])


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str | None


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(id=current_user.id, email=current_user.email)
