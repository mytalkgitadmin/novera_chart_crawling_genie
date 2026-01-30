"""GENIE 플랫폼용 Collector 구현."""

from typing import Optional, Dict
from bs4 import BeautifulSoup
import logging

from .base import BaseCollector
from ..models import MetricsResult
from ..normalizer import extract_number_from_text

logger = logging.getLogger(__name__)


class GenieCollector(BaseCollector):
    """GENIE 플랫폼에서 곡 메트릭을 수집하는 Collector."""
    
    PLATFORM = "GENIE"
    SUPPORTED_METRICS = ["total_plays", "total_listeners"]
    
    def build_url(self, song_id: str) -> str:
        """GENIE 곡 상세 페이지 URL을 생성한다."""
        return f"https://www.genie.co.kr/detail/songInfo?xgnm={song_id}"
    
    def parse_metrics(self, html: str, custom_selectors: Optional[Dict[str, str]] = None) -> MetricsResult:
        """
        GENIE 곡 상세 HTML에서 메트릭을 파싱한다.

        지원 지표:
        - total_plays (전체 재생수)
        - total_listeners (전체 청취자 수)

        Args:
            html: HTML 문자열
            custom_selectors: 지표 이름 → CSS 선택자 딕셔너리 (있으면 우선 사용)
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        total_plays = None
        total_listeners = None
        
        # 커스텀 선택자가 있으면 우선 사용, 없으면 기본 선택자 목록 사용
        if custom_selectors and 'total_plays' in custom_selectors:
            play_selectors = [custom_selectors['total_plays']]
        else:
            # total_plays(재생수)를 찾기 위한 기본 선택자들
            play_selectors = [
                '.song-info .info-list .value',
                '.info_data .play_count',
                '[data-label*="재생"]',
                '.song-play-count',
                'dd.value:contains("재생")',
            ]
        
        for selector in play_selectors:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    # 커스텀 선택자를 사용하는 경우: 숫자만 추출
                    # 기본 선택자인 경우: "재생" 관련 텍스트인지 확인 후 숫자 추출
                    if custom_selectors and 'total_plays' in custom_selectors:
                        num = extract_number_from_text(text)
                        if num is not None:
                            total_plays = num
                            logger.debug(f"Found total_plays using custom selector '{selector}': {total_plays}")
                            break
                    elif '재생' in text or 'play' in text.lower() or any(char.isdigit() for char in text):
                        num = extract_number_from_text(text)
                        if num is not None:
                            total_plays = num
                            logger.debug(f"Found total_plays using selector '{selector}': {total_plays}")
                            break
                if total_plays is not None:
                    break
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue
        
        # 커스텀 선택자가 있으면 우선 사용, 없으면 기본 선택자 목록 사용
        if custom_selectors and 'total_listeners' in custom_selectors:
            listener_selectors = [custom_selectors['total_listeners']]
        else:
            # total_listeners(청취자 수)를 찾기 위한 기본 선택자들
            listener_selectors = [
                '.song-info .info-list .value',
                '.info_data .listener_count',
                '[data-label*="청취"]',
                '.song-listener-count',
                'dd.value:contains("청취")',
            ]
        
        for selector in listener_selectors:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    # 커스텀 선택자를 사용하는 경우: 숫자만 추출
                    # 기본 선택자인 경우: "청취" 관련 텍스트인지 확인 후 숫자 추출
                    if custom_selectors and 'total_listeners' in custom_selectors:
                        num = extract_number_from_text(text)
                        if num is not None and num != total_plays:  # Avoid duplicate
                            total_listeners = num
                            logger.debug(f"Found total_listeners using custom selector '{selector}': {total_listeners}")
                            break
                    elif '청취' in text or 'listener' in text.lower() or any(char.isdigit() for char in text):
                        num = extract_number_from_text(text)
                        if num is not None and num != total_plays:  # Avoid duplicate
                            total_listeners = num
                            logger.debug(f"Found total_listeners using selector '{selector}': {total_listeners}")
                            break
                if total_listeners is not None:
                    break
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue
        
        # 보조 전략: GENIE 페이지 구조에서 "재생" 텍스트 주변에서 숫자를 탐색
        if total_plays is None:
            # "재생" 이라는 단어가 있는 텍스트를 기준으로 인접 요소에서 숫자를 찾는다
            for elem in soup.find_all(text=True):
                text = str(elem).strip()
                if '재생' in text:
                    parent = elem.parent
                    if parent:
                        # Look for numbers in sibling elements
                        for sibling in parent.find_next_siblings():
                            num = extract_number_from_text(sibling.get_text())
                            if num is not None:
                                total_plays = num
                                break
                    if total_plays is not None:
                        break
        
        if total_listeners is None:
            # 보조 전략: "청취" 텍스트 주변에서 숫자를 탐색
            for elem in soup.find_all(text=True):
                text = str(elem).strip()
                if '청취' in text:
                    parent = elem.parent
                    if parent:
                        for sibling in parent.find_next_siblings():
                            num = extract_number_from_text(sibling.get_text())
                            if num is not None and num != total_plays:
                                total_listeners = num
                                break
                    if total_listeners is not None:
                        break
        
        return MetricsResult(total_plays=total_plays, total_listeners=total_listeners)

