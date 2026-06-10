import logging
from typing import Any, AnyStr

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic_core import ValidationError

from ...container import container
from ...services.booth_config import BoothConfig, BoothConfigError, get_booth_config, reset_booth_config, set_booth_config
from ...services.config.baseconfig import SchemaTypes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/booth", tags=["admin", "booth"])


@router.get("/config/list")
def api_list_booth_configurables():
    from ...services.booth_config import list_booth_configurables

    return list_booth_configurables()


@router.get("/config/{configurable}/schema")
def api_get_booth_config_schema(configurable: str, schema_type: SchemaTypes = "default"):
    if configurable != "app":
        raise HTTPException(400, "booth configuration supports configurable=app only")
    return BoothConfig.get_schema(schema_type)


@router.get("/config/{configurable}")
def api_get_booth_config(configurable: str):
    if configurable != "app":
        raise HTTPException(400, "booth configuration supports configurable=app only")
    try:
        return get_booth_config(secrets_is_allowed=True)
    except BoothConfigError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/config/{configurable}")
def api_patch_booth_config(configurable: str, updated_config: dict[AnyStr, Any], reload: bool = False):
    if configurable != "app":
        raise HTTPException(400, "booth configuration supports configurable=app only")
    try:
        set_booth_config(updated_config)
    except BoothConfigError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    if reload:
        logger.info("reload parameter is set, reloading services after booth config update")
        container.reload()
    return get_booth_config(secrets_is_allowed=True)


@router.delete("/config/{configurable}")
def api_reset_booth_config(configurable: str, reload: bool = False):
    if configurable != "app":
        raise HTTPException(400, "booth configuration supports configurable=app only")
    try:
        reset_booth_config()
    except BoothConfigError as exc:
        raise HTTPException(400, str(exc)) from exc

    if reload:
        container.reload()
