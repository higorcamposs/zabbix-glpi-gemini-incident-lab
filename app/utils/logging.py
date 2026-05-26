"""
Centralized logging configuration for the Gemini Incident API.
"""

import logging
import sys


def configure_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure root logging for the application and return the API logger.

    Never log secrets; callers should use mask_secret() for tokens.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger("gemini-incident-api")
