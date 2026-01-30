"""플랫폼별 Collector 인스턴스를 생성하는 팩토리."""

import logging
from typing import Dict, Type

from .collectors.base import BaseCollector
from .collectors.genie import GenieCollector
from .fetcher import Fetcher

logger = logging.getLogger(__name__)


class CollectorFactory:
    """Collector 생성용 팩토리 클래스."""

    _collectors: Dict[str, Type[BaseCollector]] = {
        "GENIE": GenieCollector,
    }

    @classmethod
    def create(cls, platform: str, fetcher: Fetcher) -> BaseCollector:
        """
        지정한 플랫폼에 대한 Collector 인스턴스를 생성한다.

        Args:
            platform: 플랫폼 이름 (GENIE)
            fetcher: HTTP Fetcher 인스턴스

        Returns:
            플랫폼에 맞는 Collector 인스턴스

        Raises:
            ValueError: 지원하지 않는 플랫폼인 경우
        """
        platform_upper = platform.upper()
        collector_class = cls._collectors.get(platform_upper)

        if collector_class is None:
            raise ValueError(f"Unsupported platform: {platform}. Supported platforms: {list(cls._collectors.keys())}")

        return collector_class(fetcher)
    
    @classmethod
    def is_supported(cls, platform: str) -> bool:
        """해당 플랫폼이 지원되는지 여부를 반환한다."""
        return platform.upper() in cls._collectors
    
    @classmethod
    def get_supported_platforms(cls) -> list:
        """지원되는 플랫폼 이름 목록을 반환한다."""
        return list(cls._collectors.keys())

