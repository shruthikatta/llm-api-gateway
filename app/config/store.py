from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.config.loader import DEFAULT_CONFIG_PATH, load_gateway_config
from app.config.schema import GatewayYamlConfig
from app.exceptions.gateway import ValidationError as GatewayValidationError

logger = logging.getLogger(__name__)


class ConfigStore:
    """
    Thread-safe in-memory holder for the validated gateway YAML config.

    Hot reload never applies a partially validated document: on failure the
    previous snapshot is retained and the error is logged.
    """

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
        self._lock = threading.RLock()
        self._config = load_gateway_config(self._path)
        self._mtime = self._stat_mtime()

    @property
    def path(self) -> Path:
        return self._path

    def get(self) -> GatewayYamlConfig:
        with self._lock:
            return self._config

    def reload(self, *, force: bool = False) -> bool:
        """
        Reload from disk if the file mtime changed (or force=True).

        Returns True when a new config was applied.
        """
        mtime = self._stat_mtime()
        with self._lock:
            if not force and mtime is not None and mtime == self._mtime:
                return False

            try:
                config = load_gateway_config(self._path)
            except GatewayValidationError:
                logger.exception(
                    "Hot reload rejected invalid gateway config path=%s",
                    self._path,
                )
                raise

            self._config = config
            self._mtime = mtime
            logger.info("Gateway config reloaded path=%s", self._path)
            return True

    def _stat_mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime
        except OSError:
            return None


_store: ConfigStore | None = None
_store_lock = threading.Lock()


def get_config_store(path: Path | str | None = None) -> ConfigStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = ConfigStore(path)
        return _store


def reset_config_store() -> None:
    """Test helper to clear the process-wide store."""
    global _store
    with _store_lock:
        _store = None
