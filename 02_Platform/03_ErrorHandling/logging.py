import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(app_name: str, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_dir / f"{app_name}.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console)
