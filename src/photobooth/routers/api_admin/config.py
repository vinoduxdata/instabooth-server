import logging
from typing import Any, AnyStr

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic_core import ValidationError

from ...container import container
from ...services.config.baseconfig import SchemaTypes
from ...services.scoped_config import get_scoped_config, reset_scoped_config, set_scoped_config
from ...services.scoped_context import ScopeError, resolve_scope

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["admin", "config"])


def _is_scoped(event_id: str | None, template_id: str | None) -> bool:
    return bool(event_id or template_id)


@router.get("/list")
def api_get_configurables(event_id: str | None = None, template_id: str | None = None):
    if _is_scoped(event_id, template_id):
        return ["app"]
    return container.config_service.list_configurables()


@router.delete("")
def api_reset_all_config():
    raise NotImplementedError


@router.delete("/{configurable}")
def api_reset_config(configurable: str, event_id: str | None = None, template_id: str | None = None):
    try:
        if _is_scoped(event_id, template_id):
            reset_scoped_config(configurable, event_id=event_id, template_id=template_id)
            return
        container.config_service.reset(configurable)
    except ScopeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{configurable}/schema")
def api_get_config_schema(
    configurable: str,
    schema_type: SchemaTypes = "default",
    event_id: str | None = None,
    template_id: str | None = None,
):
    if _is_scoped(event_id, template_id) and configurable != "app":
        raise HTTPException(400, "scoped configuration supports configurable=app only")
    return container.config_service.get_schema(configurable, schema_type)


@router.get("/{configurable}")
def api_get_config_current_active(
    configurable: str,
    event_id: str | None = None,
    template_id: str | None = None,
):
    try:
        if _is_scoped(event_id, template_id):
            return get_scoped_config(configurable, event_id=event_id, template_id=template_id, secrets_is_allowed=True)
        return container.config_service.get_current(configurable, True)
    except ScopeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{configurable}")
def api_post_config_current(
    configurable: str,
    updated_config: dict[AnyStr, Any],
    reload: bool = False,
    event_id: str | None = None,
    template_id: str | None = None,
):
    try:
        if _is_scoped(event_id, template_id):
            scope = set_scoped_config(configurable, updated_config, event_id=event_id, template_id=template_id)
            if scope.is_runtime_active and reload:
                container.config_service.validate_and_set_current_and_persist(configurable, updated_config)
                container.reload()
            return

        container.config_service.validate_and_set_current_and_persist(configurable, updated_config)
    except ScopeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    if reload:
        logger.info("reload paramter is set, so all registered services are reloaded now. This may take some time...")
        container.reload()
