"""음원 메트릭 수집에 사용되는 데이터 모델 정의."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class TrackInfo:
    """수집 대상 트랙(곡)의 메타데이터 정보."""
    platform: str
    song_id: str
    alias: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    release_date: Optional[str] = None
    source_url: Optional[str] = None
    requested_metrics: Optional[Dict[str, str]] = None  # 지표 이름 → JS/CSS 선택자 맵 예: {'total_plays': '.daily-chart .total div p'}

    @property
    def track_key(self) -> str:
        """고유 트랙 키 '{platform}:{song_id}'를 생성한다."""
        return f"{self.platform}:{self.song_id}"


@dataclass
class MetricsResult:
    """플랫폼에서 파싱한 메트릭 결과."""
    total_plays: Optional[int] = None
    total_listeners: Optional[int] = None
    
    # 성별 비율 (해외 플랫폼용, 국내 플랫폼은 수집 불가)
    sex_m_rate: Optional[float] = None  # 남성 비율 (0-100)
    sex_w_rate: Optional[float] = None  # 여성 비율 (0-100)
    
    # 연령별 비율 (해외 플랫폼용, 국내 플랫폼은 수집 불가)
    age_10_rate: Optional[float] = None  # 10대 비율 (0-100)
    age_20_rate: Optional[float] = None  # 20대 비율 (0-100)
    age_30_rate: Optional[float] = None  # 30대 비율 (0-100)
    age_40_rate: Optional[float] = None  # 40대 비율 (0-100)
    age_50_rate: Optional[float] = None  # 50대 비율 (0-100)
    age_60_rate: Optional[float] = None  # 60대 비율 (0-100)

    def is_empty(self) -> bool:
        """모든 메트릭 값이 비어 있는지 여부를 반환한다."""
        return self.total_plays is None and self.total_listeners is None


@dataclass
class DailyMetrics:
    """일별 메트릭 저장을 위한 레코드 구조 (레거시, 현재는 JSON 로그 사용)."""
    track_key: str
    date: str  # YYYY-MM-DD
    total_plays: Optional[int]
    total_listeners: Optional[int]
    collected_at: str  # ISO8601
    status: str  # OK | FAILED
    error_message: Optional[str] = None

