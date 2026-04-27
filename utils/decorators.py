"""Utility decorators"""

import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def async_timer(func: Callable) -> Callable:
    """Decorator to time async function execution"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start
            logger.info(f"{func.__name__} took {duration:.3f}s")

    return wrapper
