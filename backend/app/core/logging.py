import sys

from loguru import logger


def setup_logging(debug: bool = False) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if debug else "INFO",
        format="{time:ISO8601} | {level:<7} | {name}:{line} | {message}",
        colorize=True,
    )
