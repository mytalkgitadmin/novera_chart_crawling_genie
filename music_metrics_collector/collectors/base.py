"""플랫폼별 Collector의 공통 기본 클래스 정의."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Tuple
import logging

from ..models import TrackInfo, MetricsResult
from ..fetcher import Fetcher

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """플랫폼별 Collector의 추상 기본 클래스."""
    
    PLATFORM: str = ""  # 하위 클래스에서 플랫폼 이름으로 재정의
    SUPPORTED_METRICS: List[str] = []  # 하위 클래스에서 지원 지표 목록 재정의: ['total_plays', 'total_listeners']
    
    def __init__(self, fetcher: Fetcher):
        """
        Collector를 초기화한다.

        Args:
            fetcher: HTTP 요청을 담당하는 Fetcher 인스턴스
        """
        self.fetcher = fetcher
    
    @abstractmethod
    def build_url(self, song_id: str) -> str:
        """
        곡 상세 페이지 URL을 생성한다.

        Args:
            song_id: 플랫폼별 곡 ID

        Returns:
            곡 상세 페이지의 전체 URL
        """
        pass
    
    @abstractmethod
    def parse_metrics(self, html: str, custom_selectors: Optional[Dict[str, str]] = None) -> MetricsResult:
        """
        HTML 내용에서 메트릭 값을 파싱한다.

        Args:
            html: HTML 문자열
            custom_selectors: 지표 이름 → CSS 선택자 맵
                예: {'total_plays': '.daily-chart .total div p'}

        Returns:
            파싱된 값을 담은 MetricsResult
        """
        pass
    
    def _extract_text_with_js(self, page, selector: str) -> Optional[str]:
        """
        JavaScript `document.querySelector`를 사용해 요소의 텍스트를 추출한다.

        Args:
            page: Playwright Page 객체
            selector: JavaScript `querySelector`와 호환되는 CSS 선택자

        Returns:
            텍스트 문자열 또는 없으면 None
        """
        try:
            # Use Playwright's evaluate with selector as argument to avoid escaping issues
            text = page.evaluate("""
                (selector) => {
                    const element = document.querySelector(selector);
                    return element ? element.textContent.trim() : null;
                }
            """, selector)
            return text
        except Exception as e:
            logger.debug(f"JavaScript selector '{selector}' failed: {e}")
            return None
    
    def collect(
        self,
        track_info: TrackInfo,
        song_name_selector: Optional[str] = None,
        artist_name_selector: Optional[str] = None,
        album_name_selector: Optional[str] = None,
    ) -> Tuple[MetricsResult, Optional[str], Optional[str], Optional[str]]:
        """
        하나의 곡에 대해 메트릭과 곡 제목/아티스트명/앨범명을 수집한다.

        Args:
            track_info: 수집 대상 곡 정보 (requested_metrics 포함 가능)
            song_name_selector: 곡 제목을 찾기 위한 CSS 선택자 (없으면 제목 미수집)
            artist_name_selector: 아티스트명을 찾기 위한 CSS 선택자 (없으면 아티스트명 미수집)
            album_name_selector: 앨범명을 찾기 위한 CSS 선택자 (없으면 앨범명 미수집)

        Returns:
            (메트릭 결과 MetricsResult, 곡 제목 또는 None, 아티스트명 또는 None, 앨범명 또는 None) 튜플
        """
        try:
            url = self.build_url(track_info.song_id)
            logger.info(f"Fetching {self.PLATFORM} track {track_info.song_id} from {url}")
            
            # requested_metrics가 있으면 커스텀 선택자 추출
            custom_selectors = None
            requested_metric_names = None
            use_js_selectors = False
            
            if track_info.requested_metrics:
                # 딕셔너리(선택자 포함)인지, 리스트(레거시 형식)인지 구분
                if isinstance(track_info.requested_metrics, dict):
                    custom_selectors = track_info.requested_metrics
                    requested_metric_names = list(track_info.requested_metrics.keys())
                    use_js_selectors = True  # 커스텀 선택자가 있으면 JavaScript 모드 사용
                elif isinstance(track_info.requested_metrics, list):
                    # Legacy format: list of metric names
                    requested_metric_names = track_info.requested_metrics
            
            # 커스텀 선택자가 있으면 Playwright + JavaScript로 수집
            if use_js_selectors:
                metrics, song_name, artist_name, album_name = self._collect_with_js(
                    url,
                    custom_selectors,
                    song_name_selector=song_name_selector,
                    artist_name_selector=artist_name_selector,
                    album_name_selector=album_name_selector,
                )
            else:
                # 전통적인 HTML 파싱 사용 (이 모드에서는 곡 제목 미수집)
                html = self.fetcher.fetch_html(url)
                metrics = self.parse_metrics(html, custom_selectors=None)
                song_name = None
                artist_name = None
                album_name = None
            
            # requested_metrics에 따라 필터링
            if requested_metric_names:
                # 요청된 지표가 SUPPORTED_METRICS에 포함되는지 검증
                invalid_metrics = [m for m in requested_metric_names if m not in self.SUPPORTED_METRICS]
                if invalid_metrics:
                    logger.warning(f"Unsupported metrics for {self.PLATFORM}: {invalid_metrics}. "
                                 f"Supported: {self.SUPPORTED_METRICS}")
                
                # 요청되지 않은 지표는 None으로 처리
                if 'total_plays' not in requested_metric_names:
                    metrics.total_plays = None
                if 'total_listeners' not in requested_metric_names:
                    metrics.total_listeners = None
                
                logger.info(
                    f"Collected {self.PLATFORM} metrics for {track_info.song_id} "
                    f"(requested: {requested_metric_names}): "
                    f"plays={metrics.total_plays}, listeners={metrics.total_listeners}"
                )
            else:
                logger.info(
                    f"Collected {self.PLATFORM} metrics for {track_info.song_id}: "
                    f"plays={metrics.total_plays}, listeners={metrics.total_listeners}"
                )
            
            return metrics, song_name, artist_name, album_name
        except Exception as e:
            logger.error(f"Failed to collect {self.PLATFORM} metrics for {track_info.song_id}: {e}")
            raise
    
    def _collect_with_js(
        self,
        url: str,
        custom_selectors: Dict[str, str],
        song_name_selector: Optional[str] = None,
        artist_name_selector: Optional[str] = None,
        album_name_selector: Optional[str] = None,
    ) -> Tuple[MetricsResult, Optional[str], Optional[str], Optional[str]]:
        """
        Playwright + JavaScript를 사용해 메트릭과 곡 제목/아티스트명/앨범명을 수집한다.

        Args:
            url: 요청할 곡 상세 URL
            custom_selectors: 지표 이름 → CSS 선택자 딕셔너리
            song_name_selector: 곡 제목을 찾기 위한 CSS 선택자
            artist_name_selector: 아티스트명을 찾기 위한 CSS 선택자
            album_name_selector: 앨범명을 찾기 위한 CSS 선택자

        Returns:
            (메트릭 결과 MetricsResult, 곡 제목 또는 None, 아티스트명 또는 None, 앨범명 또는 None) 튜플
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("playwright not installed. Install with: pip install playwright && playwright install chromium")
        
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(url, wait_until='networkidle', timeout=self.fetcher.timeout * 1000)
            
            metrics = MetricsResult()
            song_name = None
            artist_name = None
            album_name = None
            
            # 곡 제목 추출 (선택자 제공 시)
            if song_name_selector:
                song_name = self._extract_text_with_js(page, song_name_selector)
                if song_name:
                    song_name = song_name.strip()
                    logger.debug(f"Found song name using selector '{song_name_selector}': {song_name}")
            
            # 아티스트명 추출 (선택자 제공 시)
            if artist_name_selector:
                artist_name = self._extract_text_with_js(page, artist_name_selector)
                if artist_name:
                    artist_name = artist_name.strip()
                    logger.debug(f"Found artist name using selector '{artist_name_selector}': {artist_name}")
            
            # 앨범명 추출 (선택자 제공 시)
            if album_name_selector:
                album_name = self._extract_text_with_js(page, album_name_selector)
                if album_name:
                    album_name = album_name.strip()
                    logger.debug(f"Found album name using selector '{album_name_selector}': {album_name}")
            
            # 각 지표를 JavaScript querySelector로 추출
            for metric_name, selector in custom_selectors.items():
                if metric_name not in self.SUPPORTED_METRICS:
                    logger.warning(f"Unsupported metric '{metric_name}' for {self.PLATFORM}")
                    continue
                
                text = self._extract_text_with_js(page, selector)
                if text:
                    from ..normalizer import extract_number_from_text
                    num = extract_number_from_text(text)
                    if num is not None:
                        if metric_name == 'total_plays':
                            metrics.total_plays = num
                        elif metric_name == 'total_listeners':
                            metrics.total_listeners = num
                        logger.debug(f"Found {metric_name} using JavaScript selector '{selector}': {num}")
            
            return metrics, song_name, artist_name, album_name
        finally:
            page.close()
            browser.close()
            playwright.stop()

