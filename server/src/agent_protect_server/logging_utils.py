import logging
import os

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def _parse_level(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        return _LEVELS.get(level.upper(), logging.INFO)
    env = os.getenv("LOG_LEVEL", "INFO")
    return _LEVELS.get(env.upper(), logging.INFO)


def _parse_json(json_flag: bool | None) -> bool:
    if isinstance(json_flag, bool):
        return json_flag
    env = os.getenv("LOG_JSON", "false").lower()
    return env in {"1", "true", "yes", "y"}


def configure_logging(*, level: str | int | None = None, json: bool | None = None) -> None:
    lvl = _parse_level(level)
    as_json = _parse_json(json)
    fmt = (
        '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
        if as_json
        else "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    datefmt = "%Y-%m-%dT%H:%M:%S%z"

    root = logging.getLogger()
    root.setLevel(lvl)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.setLevel(lvl)
        logger.propagate = True
        for h in list(logger.handlers):
            logger.removeHandler(h)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
