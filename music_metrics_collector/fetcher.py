"""HTTP 요청을 담당하는 Fetcher - requests 우선, 필요 시 Playwright 사용."""

import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class Fetcher:
    """HTTP Fetcher 클래스 (requests / Playwright 지원)."""
    
    def __init__(self, mode: str = "auto", timeout_sec: int = 20):
        """
        Fetcher를 초기화한다.

        Args:
            mode: "requests" | "playwright" | "auto"
            timeout_sec: 요청 타임아웃(초)
        """
        self.mode = mode
        self.timeout = timeout_sec
        self._playwright = None
        self._browser = None
        
    def _fetch_requests(self, url: str, headers: Optional[dict] = None) -> str:
        """requests 라이브러리를 사용해 HTML을 가져온다."""
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        if headers:
            default_headers.update(headers)
            
        response = requests.get(url, headers=default_headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text
    
    def _fetch_playwright(self, url: str) -> str:
        """Playwright를 사용해 HTML을 가져온다 (JS 렌더링이 필요한 경우)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("playwright not installed. Install with: pip install playwright && playwright install chromium")
        
        if self._playwright is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
        
        page = self._browser.new_page()
        try:
            page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
            content = page.content()
            return content
        finally:
            page.close()
    
    def fetch_html(self, url: str, headers: Optional[dict] = None) -> str:
        """
        지정한 URL에서 HTML을 가져온다.

        Args:
            url: 요청할 URL
            headers: 추가 헤더 딕셔너리

        Returns:
            HTML 문자열

        Raises:
            Exception: 요청 실패 시 예외 발생
        """
        if self.mode == "playwright":
            return self._fetch_playwright(url)
        elif self.mode == "requests":
            return self._fetch_requests(url, headers)
        else:  # auto mode
            try:
                return self._fetch_requests(url, headers)
            except Exception as e:
                logger.warning(f"requests failed for {url}: {e}. Falling back to playwright...")
                return self._fetch_playwright(url)
    
    def close(self):
        """Playwright 관련 리소스를 정리한다."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

