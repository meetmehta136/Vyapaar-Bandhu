"""Logging configuration — uses loguru with structured output.

Run `configure_logging()` once at app startup to replace standard logging
with loguru's handler and set global level from LOG_LEVEL env var."""
import os, sys, logging
from loguru import logger


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class InterceptHandler(logging.Handler):
    """Redirect Python stdlib logging to loguru."""

    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def configure_logging():
    """Configure loguru: remove default handler, add structured stderr handler."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - {message}",
        colorize=True,
        backtrace=True,
        diagnose=False,
    )

    # Intercept stdlib loggers (fastapi, uvicorn, etc.)
    logging.basicConfig(handlers=[InterceptHandler()], level=LOG_LEVEL, force=True)

    logger.info(f"Logging configured — level={LOG_LEVEL}")


def get_logger(name: str = __name__):
    """Get a named child logger, bound to the calling module."""
    return logger.bind(module=name)
