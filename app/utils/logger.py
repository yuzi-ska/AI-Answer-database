"""
OCS网课助手日志配置
"""
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import settings


_SENSITIVE_LOG_KEYS = {"authorization", "x-api-key", "api_key", "api-key"}


def _sanitize_log_value(value: Any, key: str = "") -> Any:
    normalized_key = key.lower()
    if normalized_key in _SENSITIVE_LOG_KEYS and value not in (None, ""):
        return "***"

    if isinstance(value, dict):
        return {str(item_key): _sanitize_log_value(item_value, str(item_key)) for item_key, item_value in value.items()}

    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_sanitize_log_value(item) for item in value)

    return value


def _get_exception_info(exc: Exception):
    return type(exc), exc, exc.__traceback__


def setup_logger(name: str = "ocs_api", log_file: str = None, level: str = None) -> logging.Logger:
    """设置日志记录器"""
    if hasattr(sys, 'meta_path') and sys.meta_path is None:
        return logging.getLogger(name)

    try:
        log_file = log_file or settings.LOG_FILE_PATH
        level = level or settings.LOG_LEVEL
        resolved_level = getattr(logging, str(level).upper(), logging.INFO)

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        configured_logger = logging.getLogger(name)
        configured_logger.setLevel(resolved_level)
        configured_logger.propagate = False

        if configured_logger.handlers:
            configured_logger.handlers.clear()

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=500 * 1024,
            backupCount=5,
            encoding='utf-8',
            delay=True
        )
        file_handler.setFormatter(formatter)
        configured_logger.addHandler(file_handler)

        try:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            configured_logger.addHandler(console_handler)
        except Exception:
            pass

        return configured_logger
    except Exception:
        return logging.getLogger(name)


logger = setup_logger()


def is_debug_enabled() -> bool:
    return logger.isEnabledFor(logging.DEBUG)


def debug_log_payload(title: str, payload: Any) -> None:
    if not is_debug_enabled():
        return

    sanitized_payload = _sanitize_log_value(payload)
    try:
        formatted_payload = json.dumps(sanitized_payload, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        formatted_payload = repr(sanitized_payload)

    logger.debug(f"{title}:\n{formatted_payload}")


def log_exception(message: str, exc: Exception) -> None:
    if is_debug_enabled():
        logger.error(message, exc_info=_get_exception_info(exc))
        return
    logger.error(f"{message}: {exc}")
