from __future__ import annotations

import logging


_LOGGER = logging.getLogger("sekretariat_app.sips")


def safe_log(message: str) -> None:
    _LOGGER.warning("%s", message)
