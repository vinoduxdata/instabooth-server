"""Admin user accounts stored in instabooth-admin/users.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .event_admin import EventAdminError, _load_booth_config, _require_admin, _write_json_atomic

logger = logging.getLogger(__name__)

UserRole = Literal["admin"]


class UserAdminError(Exception):
    pass


class AdminUser(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=1, max_length=256)
    role: UserRole = "admin"
    enabled: bool = True


class AdminUserPublic(BaseModel):
    username: str
    full_name: str | None = None
    role: UserRole = "admin"
    enabled: bool = True


def _users_file() -> Path:
    _require_admin()
    from ..paths import admin_path

    return admin_path("users.json")


def _read_users_registry() -> dict[str, Any]:
    users_file = _users_file()
    if not users_file.is_file():
        return _bootstrap_users_registry()
    return json.loads(users_file.read_text(encoding="utf-8"))


def _bootstrap_users_registry() -> dict[str, Any]:
    users_file = _users_file()
    booth = _load_booth_config()
    password = booth.get("common", {}).get("admin_password", "0000")
    payload = {
        "users": [
            AdminUser(
                username="admin",
                full_name="Administrator",
                password=str(password),
                role="admin",
                enabled=True,
            ).model_dump()
        ]
    }
    _write_json_atomic(users_file, payload)
    return payload


def _save_users_registry(registry: dict[str, Any]) -> None:
    _write_json_atomic(_users_file(), registry)


def list_users(*, include_passwords: bool = False) -> list[dict[str, Any]]:
    try:
        registry = _read_users_registry()
    except EventAdminError as exc:
        raise UserAdminError(str(exc)) from exc

    users = registry.get("users", [])
    if include_passwords:
        return users
    return [AdminUserPublic.model_validate(user).model_dump() for user in users]


def get_user(username: str, *, include_password: bool = False) -> dict[str, Any]:
    for user in _read_users_registry().get("users", []):
        if user["username"] == username:
            if include_password:
                return user
            return AdminUserPublic.model_validate(user).model_dump()
    raise UserAdminError(f"user not found: {username}")


def create_user(
    username: str,
    password: str,
    full_name: str | None = None,
    role: UserRole = "admin",
    enabled: bool = True,
) -> dict[str, Any]:
    registry = _read_users_registry()
    users = registry.setdefault("users", [])
    if any(user["username"] == username for user in users):
        raise UserAdminError(f"user already exists: {username}")

    user = AdminUser(username=username, password=password, full_name=full_name, role=role, enabled=enabled)
    users.append(user.model_dump())
    _save_users_registry(registry)
    return AdminUserPublic.model_validate(user).model_dump()


def update_user(
    username: str,
    *,
    password: str | None = None,
    full_name: str | None = None,
    role: UserRole | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    registry = _read_users_registry()
    updated_user: dict[str, Any] | None = None

    for user in registry.get("users", []):
        if user["username"] != username:
            continue
        if password is not None:
            user["password"] = password
        if full_name is not None:
            user["full_name"] = full_name
        if role is not None:
            user["role"] = role
        if enabled is not None:
            user["enabled"] = enabled
        updated_user = user
        break

    if updated_user is None:
        raise UserAdminError(f"user not found: {username}")

    _save_users_registry(registry)
    return AdminUserPublic.model_validate(updated_user).model_dump()


def delete_user(username: str) -> None:
    registry = _read_users_registry()
    users = registry.get("users", [])
    if len(users) <= 1:
        raise UserAdminError("cannot delete the last admin user")
    if not any(user["username"] == username for user in users):
        raise UserAdminError(f"user not found: {username}")

    registry["users"] = [user for user in users if user["username"] != username]
    _save_users_registry(registry)


def users_for_auth() -> dict[str, AdminUser]:
    try:
        registry = _read_users_registry()
    except EventAdminError:
        return {}

    users: dict[str, AdminUser] = {}
    for item in registry.get("users", []):
        if not item.get("enabled", True):
            continue
        user = AdminUser.model_validate(item)
        users[user.username] = user
    return users
