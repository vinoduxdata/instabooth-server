import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.user_admin import UserAdminError, UserRole, create_user, delete_user, list_users, update_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["admin", "users"])


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    full_name: str | None = Field(default=None, max_length=120)
    role: UserRole = "admin"
    enabled: bool = True


class UpdateUserRequest(BaseModel):
    password: str | None = Field(default=None, min_length=1, max_length=256)
    full_name: str | None = Field(default=None, max_length=120)
    role: UserRole | None = None
    enabled: bool | None = None


@router.get("")
def api_list_users():
    try:
        return {"users": list_users()}
    except UserAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("")
def api_create_user(body: CreateUserRequest):
    try:
        return create_user(
            username=body.username,
            password=body.password,
            full_name=body.full_name,
            role=body.role,
            enabled=body.enabled,
        )
    except UserAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{username}")
def api_update_user(username: str, body: UpdateUserRequest):
    try:
        return update_user(
            username,
            password=body.password,
            full_name=body.full_name,
            role=body.role,
            enabled=body.enabled,
        )
    except UserAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{username}")
def api_delete_user(username: str):
    try:
        delete_user(username)
        return {"deleted": username}
    except UserAdminError as exc:
        raise HTTPException(400, str(exc)) from exc
