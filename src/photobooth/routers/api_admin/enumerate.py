import logging
import sys
from glob import glob
from pathlib import Path

from fastapi import APIRouter

from ... import USERDATA_PATH
from ...services.scoped_context import ScopeError, resolve_scope
from ...utils.enumerate import rclone_remotes, serial_ports, webcameras
from ...utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enumerate", tags=["admin", "enumerate"])


@router.get("/serialports")
def api_get_serial_ports() -> list[str]:
    return serial_ports()


@router.get("/usbcameras")
def api_get_usbcameras() -> list[str]:
    return webcameras()


@router.get("/userfiles")
def get_search(q: str = "", event_id: str | None = None, template_id: str | None = None) -> list[str]:
    search_pattern = f"*{q}*" if q else ""
    try:
        scope = resolve_scope(event_id, template_id)
        userdata_root = scope.userdata_dir
        if not userdata_root.exists():
            return []
        matches = userdata_root.rglob(search_pattern.lstrip("/") or "*")
        return sorted(path.relative_to(scope.root).as_posix() for path in matches if path.is_file())
    except ScopeError:
        sanitized_input = filenames_sanitize(f"{USERDATA_PATH}**/{search_pattern}").relative_to(Path.cwd())
        return [result for result in sorted(glob(str(sanitized_input), recursive=True)) if Path(result).is_file()]


@router.get("/rclone_remotes")
def api_get_rclone_remotes() -> list[str]:
    remotes = [f"{r}:" for r in rclone_remotes()]
    return ["C:\\" if sys.platform == "win32" else "/"] + remotes
