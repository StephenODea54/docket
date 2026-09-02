import logging
import os

_root = logging.getLogger("docket")
_root.addHandler(logging.NullHandler())

_env_level = os.environ.get("DOCKET_LOG_LEVEL", "").upper()
if _env_level:
    try:
        _root.setLevel(_env_level)
    except ValueError:
        _root.warning("ignoring invalid DOCKET_LOG_LEVEL=%s", _env_level)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger namespaced under docket,
    e.g. get_logger("glue") -> docket.glue.

    Args:
        name: logger namespace

    Returns:
        Logger

    Raises:
        ValueError: if name is blank
    """
    if not name.strip():
        raise ValueError("logger name must not be blank")
    return logging.getLogger(f"docket.{name}")
