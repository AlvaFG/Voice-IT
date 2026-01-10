"""
Voice IT - Retry utilities
Provides retry logic with exponential backoff for API calls.
"""

import asyncio
import functools
import random
import time
from typing import Any, Callable, Optional, Type, TypeVar, Union

T = TypeVar("T")


class RetryError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Calculate backoff delay with optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (exponential_base**attempt), max_delay)

    if jitter:
        # Add jitter: random value between 0 and delay
        delay = delay * (0.5 + random.random() * 0.5)

    return delay


def retry(
    max_attempts: int = 3,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying synchronous functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        exceptions: Tuple of exception types to catch and retry
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        on_retry: Optional callback called on each retry (attempt, exception)

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        raise RetryError(
                            f"Failed after {max_attempts} attempts: {e}",
                            attempts=max_attempts,
                            last_exception=e,
                        ) from e

                    if on_retry:
                        on_retry(attempt + 1, e)

                    delay = calculate_backoff(
                        attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                    )
                    time.sleep(delay)

            # Should never reach here
            raise RetryError(
                "Retry exhausted",
                attempts=max_attempts,
                last_exception=last_exception,
            )

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        exceptions: Tuple of exception types to catch and retry
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        on_retry: Optional callback called on each retry (attempt, exception)

    Returns:
        Decorated async function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        raise RetryError(
                            f"Failed after {max_attempts} attempts: {e}",
                            attempts=max_attempts,
                            last_exception=e,
                        ) from e

                    if on_retry:
                        on_retry(attempt + 1, e)

                    delay = calculate_backoff(
                        attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                    )
                    await asyncio.sleep(delay)

            # Should never reach here
            raise RetryError(
                "Retry exhausted",
                attempts=max_attempts,
                last_exception=last_exception,
            )

        return wrapper

    return decorator


async def retry_async_operation(
    operation: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    **kwargs: Any,
) -> T:
    """
    Retry an async operation with exponential backoff.

    Args:
        operation: Async function to retry
        *args: Positional arguments for the operation
        max_attempts: Maximum number of attempts
        exceptions: Tuple of exception types to catch and retry
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries
        on_retry: Optional callback called on each retry
        **kwargs: Keyword arguments for the operation

    Returns:
        Result of the operation

    Raises:
        RetryError: When all attempts are exhausted
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return await operation(*args, **kwargs)
        except exceptions as e:
            last_exception = e

            if attempt == max_attempts - 1:
                raise RetryError(
                    f"Failed after {max_attempts} attempts: {e}",
                    attempts=max_attempts,
                    last_exception=e,
                ) from e

            if on_retry:
                on_retry(attempt + 1, e)

            delay = calculate_backoff(
                attempt,
                base_delay=base_delay,
                max_delay=max_delay,
            )
            await asyncio.sleep(delay)

    # Should never reach here
    raise RetryError(
        "Retry exhausted",
        attempts=max_attempts,
        last_exception=last_exception,
    )
