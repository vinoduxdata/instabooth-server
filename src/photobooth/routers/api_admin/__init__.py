"""Example 2nd-level subpackage."""

from fastapi import APIRouter, Depends

from ..auth_dependencies_bearer import get_current_active_user
from . import auth, booth, config, enumerate, event_templates, events, files, information, multicamera, share, users

__all__ = [
    "auth",
    "config",  # refers to the 'config.py' file
    "enumerate",
    "files",
    "information",
    "multicamera",
    "share",
]

router = APIRouter(prefix="/api/admin")
router.include_router(auth.router)
router.include_router(config.router, dependencies=[Depends(get_current_active_user)])
router.include_router(enumerate.router, dependencies=[Depends(get_current_active_user)])
router.include_router(files.router, dependencies=[Depends(get_current_active_user)])
router.include_router(information.router, dependencies=[Depends(get_current_active_user)])
router.include_router(multicamera.router, dependencies=[Depends(get_current_active_user)])
router.include_router(share.router, dependencies=[Depends(get_current_active_user)])
router.include_router(events.router, dependencies=[Depends(get_current_active_user)])
router.include_router(event_templates.router, dependencies=[Depends(get_current_active_user)])
router.include_router(booth.router, dependencies=[Depends(get_current_active_user)])
router.include_router(users.router, dependencies=[Depends(get_current_active_user)])
