#!/usr/bin/python3
"""
Photobooth Application start script
"""

import argparse
import logging
import os
import sys
from importlib.metadata import version
from pathlib import Path

import uvicorn

from .paths import bootstrap_from_argv

parser = argparse.ArgumentParser()
parser.add_argument("--host", action="store", type=str, default="0.0.0.0", help="Host the server is bound to (default: %(default)s).")
parser.add_argument("--port", action="store", type=int, default=8000, help="Port the server listens to (default: %(default)s).")
parser.add_argument("--data-dir", type=str, default=None, help="Event data directory (overrides active-event.json).")
parser.add_argument("--admin-dir", type=str, default=None, help="instabooth-admin directory for event registry and templates.")

logger = logging.getLogger(f"{__name__}")


def main(args=None, run_server: bool = True):
    remaining_args = bootstrap_from_argv(args)

    from . import initialize_data_environment

    initialize_data_environment()

    from .services.booth_config import apply_booth_config_on_startup

    synced_config = apply_booth_config_on_startup()
    if synced_config is not None:
        logger.info(f"synced booth config into active event: {synced_config}")

    from .services.hotspot import ensure_auto_wifi_qr_on_startup

    wifi_qr = ensure_auto_wifi_qr_on_startup()
    if wifi_qr is not None:
        logger.info(f"hotspot Wi-Fi QR: {wifi_qr}")

    args = parser.parse_args(remaining_args)  # parse here, not above because pytest system exit 2

    print("Booting app, this can take some time depending on installed extras...")

    from .database.database import create_db_and_tables

    # create all db before anything else...
    create_db_and_tables()

    from .application import app
    from .container import container

    host = args.host
    port = args.port

    logger.info("✨ Welcome to the photobooth-app ✨")

    from .paths import ADMIN_DIR, DATA_DIR

    logger.info(f"photobooth directory: {Path(__file__).parent.resolve()}")
    logger.info(f"working directory: {Path.cwd().resolve()}")
    logger.info(f"data directory: {DATA_DIR}")
    logger.info(f"admin directory: {ADMIN_DIR}")
    from .services.event_admin import booth_config_file

    try:
        logger.info(f"booth mode: {os.environ.get('INSTABOOTH_MODE', 'prod')}")
        logger.info(f"booth config: {booth_config_file()}")
    except Exception:
        pass
    logger.info(f"app version started: {version('photobooth-app')}")

    server = uvicorn.Server(uvicorn.Config(app=app, host=host, port=port, log_level="info", workers=None))

    # adjust logging after uvicorn setup
    container.logging_service.uvicorn()

    # start all services
    container.start()

    # serve, loops endless
    # this one is not executed in tests because it's not stoppable from within
    if run_server:
        try:
            server.run()
        except KeyboardInterrupt:
            print("got ctrl-c, photobooth-app stopped")


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
