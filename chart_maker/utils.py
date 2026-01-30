"""공통 유틸리티: 로깅 설정, 경로 유틸리티 등."""

import logging
from pathlib import Path


def setup_logging(level: int = logging.INFO) -> None:
    """기본 로깅 설정을 수행한다."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def ensure_dir(path: Path) -> Path:
    """디렉토리가 없으면 생성하고 Path를 반환한다."""
    path.mkdir(parents=True, exist_ok=True)
    return path



