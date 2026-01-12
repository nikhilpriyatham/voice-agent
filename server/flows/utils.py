"""Utility functions and decorators for flow handlers."""

import asyncio
import functools
import traceback
from typing import Callable, Dict

from loguru import logger
from pipecat_flows import FlowManager

# Configure logging
logger = logger.bind(name=__name__)


def handle_flow_error(func: Callable) -> Callable:
    """
    Decorator to wrap flow handler functions with error handling.
    If any exception occurs, logs the error and attempts graceful recovery.

    Args:
        func: The function to wrap with error handling

    Returns:
        A wrapper function that catches exceptions and handles them gracefully
    """

    @functools.wraps(func)
    async def async_wrapper(args: Dict, result: dict, flow_manager: FlowManager):
        try:
            return await func(args, result, flow_manager)
        except Exception as e:
            error_msg = f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)

            # Try to gracefully end the conversation on error
            try:
                from flows.end import create_error_end_node

                await flow_manager.set_node("error_end", create_error_end_node())
            except Exception as inner_e:
                logger.error(f"Failed to set error end node: {inner_e}")

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    # Check if the decorated function is a coroutine function
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
