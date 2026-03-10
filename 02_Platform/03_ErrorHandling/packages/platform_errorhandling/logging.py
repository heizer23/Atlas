import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(app_name: str, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    log_file = log_dir / f"{app_name}.log"
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Only add file handler if one for this app isn't already registered
    already_has_file = any(
        isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(log_file)
        for h in logger.handlers
    )
    if not already_has_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    # Only add console handler if one isn't already registered
    already_has_console = any(
        type(h) is logging.StreamHandler for h in logger.handlers
    )
    if not already_has_console:
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)
