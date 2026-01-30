"""메트릭 숫자 파싱을 위한 정규화 유틸리티."""

import re
from typing import Optional


def normalize_number(text: str) -> Optional[int]:
    """
    문자열 형태의 숫자를 정수로 변환한다.

    처리 예시:
    - "1,234,567" -> 1234567
    - "12.3만" -> 123000
    - "1.2M" -> 1200000
    - "1234" -> 1234

    Args:
        text: 숫자 정보가 들어 있는 문자열

    Returns:
        변환된 정수 값, 실패 시 None
    """
    if not text:
        return None
    
    # Remove whitespace
    text = text.strip()
    
    # Remove commas
    text = text.replace(',', '')
    
    # Handle Korean "만" (10,000)
    if '만' in text:
        match = re.search(r'([\d.]+)\s*만', text)
        if match:
            try:
                value = float(match.group(1))
                return int(value * 10000)
            except ValueError:
                pass
    
    # Handle "M" (million)
    if 'M' in text.upper():
        match = re.search(r'([\d.]+)\s*M', text, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                return int(value * 1000000)
            except ValueError:
                pass
    
    # Handle "K" (thousand)
    if 'K' in text.upper():
        match = re.search(r'([\d.]+)\s*K', text, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                return int(value * 1000)
            except ValueError:
                pass
    
    # Extract digits and dots only
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            value = float(match.group(0))
            return int(value)
        except ValueError:
            pass
    
    return None


def extract_number_from_text(text: str) -> Optional[int]:
    """
    주어진 문자열에서 첫 번째 숫자를 추출한다.

    Args:
        text: 숫자가 포함될 수 있는 문자열

    Returns:
        추출된 정수 값, 없으면 None
    """
    if not text:
        return None
    
    # Try direct normalization first
    result = normalize_number(text)
    if result is not None:
        return result
    
    # Extract all digits
    digits = re.sub(r'[^\d]', '', text)
    if digits:
        try:
            return int(digits)
        except ValueError:
            pass
    
    return None

