"""로깅, 재시도, 타임존 유틸리티 함수 모음."""

import logging
import os
import time
from functools import wraps
from typing import Callable, TypeVar, Any
from datetime import datetime
import pytz

T = TypeVar('T')

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 기본 타임존: Asia/Seoul
SEOUL_TZ = pytz.timezone('Asia/Seoul')


def get_seoul_now() -> datetime:
    """Asia/Seoul 타임존의 현재 시각을 반환한다."""
    return datetime.now(SEOUL_TZ)


def get_seoul_date() -> str:
    """Asia/Seoul 타임존 기준 현재 날짜를 'YYYY-MM-DD' 형식으로 반환한다."""
    return get_seoul_now().strftime('%Y-%m-%d')


def get_iso8601_now() -> str:
    """Asia/Seoul 타임존 기준 현재 시각을 ISO8601 문자열로 반환한다."""
    return get_seoul_now().isoformat()


def get_current_hour() -> int:
    """Asia/Seoul 타임존 기준 현재 시(0–23)를 반환한다."""
    return get_seoul_now().hour


def get_current_minute() -> int:
    """Asia/Seoul 타임존 기준 현재 분(0–59)을 반환한다."""
    return get_seoul_now().minute


def retry(max_retries: int = 3, backoff_sec: float = 2.0, exceptions: tuple = (Exception,)):
    """지수 백오프를 적용해 함수를 재시도하는 데코레이터."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_sec * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator

