"""검색용 CSV(search_data.csv)를 기반으로 song_id를 채우는 보조 스크립트.

사용 흐름:

1) 플랫폼별 검색 키워드 CSV 작성
   - 경로: resource/{플랫폼명}/search_data.csv
   - 컬럼: song_name, artist_name, album_name, song_type, track_code, isrc
   예:
       song_name,artist_name,album_name,song_type,track_code,isrc
       곡제목1,아티스트1,앨범명1,장르1,A1147227T001,KSB012324080
       곡제목2,아티스트2,앨범명2,장르2,A1147227T002,KSB012324081

2) 본 스크립트 실행
   - 예: python -m music_metrics_collector.generate_song_ids --config config.yaml

3) 각 플랫폼별 song_data.csv 생성/갱신
   - 경로: resource/{플랫폼명}/song_data.csv
   - 컬럼: song_id, track_code, isrc, song_type (song_type은 맨 뒤)
"""

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from .fetcher import Fetcher
from .main import load_config


logger = logging.getLogger(__name__)


def _read_search_data(platform: str, resource_dir: str) -> List[Dict[str, str]]:
    """플랫폼별 search_data.csv에서 모든 필드를 읽어온다."""
    csv_path = Path(resource_dir) / platform / "search_data.csv"
    if not csv_path.exists():
        logger.warning(f"[{platform}] search_data.csv를 찾을 수 없습니다: {csv_path}")
        return []

    rows: List[Dict[str, str]] = []
    try:
        # utf-8-sig를 사용하여 BOM(Byte Order Mark)을 자동으로 제거
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # BOM이 남아있을 수 있으므로 컬럼명에서도 제거
            reader.fieldnames = [name.strip('\ufeff') if name else name for name in (reader.fieldnames or [])]
            for row in reader:
                # BOM이 포함된 키도 처리
                row_cleaned = {}
                for key, value in row.items():
                    cleaned_key = key.strip('\ufeff') if key else key
                    row_cleaned[cleaned_key] = value
                
                # 검색에 필요한 기본 필드
                song_name = (row_cleaned.get("song_name_kor") or "").strip()
                artist_name = (row_cleaned.get("artist_name_kor") or "").strip()
                
                if not song_name and not artist_name:
                    continue
                
                # 새로운 명세에 맞춰 모든 필드 추출 (20개 필드)
                rows.append({
                    # 검색용 필드
                    "song_name": song_name,
                    "artist_name": artist_name,
                    "album_name": (row_cleaned.get("album_name_kor") or "").strip(),
                    
                    # song_data.csv 출력용 20개 필드 (순서대로)
                    "platform_seq": (row_cleaned.get("platform_seq") or "").strip(),
                    "platform_name": (row_cleaned.get("platform_name") or "").strip(),
                    "song_type_txt": (row_cleaned.get("song_type_text") or "").strip(),
                    "album_cd": (row_cleaned.get("album_cd") or "").strip(),
                    "album_name_kor": (row_cleaned.get("album_name_kor") or "").strip(),
                    "album_name_eng": (row_cleaned.get("album_name_eng") or "").strip(),
                    "song_cd": (row_cleaned.get("song_cd") or "").strip(),
                    "song_name_kor": song_name,
                    "song_name_eng": (row_cleaned.get("song_name_eng") or "").strip(),
                    "song_release_date": (row_cleaned.get("song_release_date") or "").strip(),
                    "artist_cd": (row_cleaned.get("artist_cd") or "").strip(),
                    "artist_name_kor": artist_name,
                    "artist_name_eng": (row_cleaned.get("artist_name_eng") or "").strip(),
                    "mem_cd": (row_cleaned.get("mem_cd") or "").strip(),
                    "mem_name": (row_cleaned.get("mem_name") or "").strip(),
                    "track_cd": (row_cleaned.get("track_cd") or "").strip(),
                    "isrc_cd": (row_cleaned.get("isrc_cd") or "").strip(),
                    "interest_yn": (row_cleaned.get("interest_yn") or "n").strip(),
                })
    except Exception as e:
        logger.error(f"[{platform}] search_data.csv 읽기 실패: {e}")
        return []

    logger.info(f"[{platform}] search_data.csv에서 {len(rows)}건의 검색 키워드를 읽었습니다.")
    return rows


def _remove_japanese(text: str) -> str:
    """
    텍스트에서 일본어 문자(히라가나, 가타카나, 한자)를 제거한다.
    괄호로 감싸진 일본어도 함께 제거한다.
    
    Args:
        text: 처리할 텍스트
    
    Returns:
        일본어가 제거된 텍스트
    """
    if not text:
        return ""
    
    import re
    # 일본어 문자 범위: 히라가나(ぁ-ゟ), 가타카나(ァ-ヿ), 한자(一-龯)
    # 괄호 안에 일본어가 있으면 괄호째 제거 (예: "(ユンナ)" → "")
    text = re.sub(r'\([ぁ-ゟァ-ヿ一-龯]+\)', '', text)
    text = re.sub(r'\（[ぁ-ゟァ-ヿ一-龯]+\）', '', text)  # 전각 괄호
    # 남은 일본어 문자 제거
    text = re.sub(r'[ぁ-ゟァ-ヿ一-龯]+', '', text)
    # 여러 공백을 하나로 변환
    text = " ".join(text.split())
    
    return text.strip()


def _preprocess_album_name(album_name: str) -> str:
    """
    앨범명을 검색에 적합하게 전처리한다.
    OST 키워드, Part 번호, 버전 정보 등을 제거한다.
    
    Args:
        album_name: 원본 앨범명
    
    Returns:
        전처리된 앨범명
    """
    if not album_name:
        return ""
    
    import re
    # 일본어 제거
    album_name = _remove_japanese(album_name)
    
    # OST 관련 키워드 제거
    ost_patterns = [
        r'\s*\(Original Soundtrack\)',
        r'\s*\(Original Motion Picture Soundtrack\)',
        r'\s*\(Original Television Soundtrack\)',
        r'\s*Original Soundtrack',
        r'\s*Original Motion Picture Soundtrack',
        r'\s*Original Television Soundtrack',
        r'\s*OST',
        r'\s*O\.S\.T\.',
    ]
    for pattern in ost_patterns:
        album_name = re.sub(pattern, '', album_name, flags=re.IGNORECASE)
    
    # Part, Pt 번호 제거 (예: "Part.1", "Pt. 2", "Part 3")
    album_name = re.sub(r'\s*Pt\.?\s*\d+', '', album_name, flags=re.IGNORECASE)
    album_name = re.sub(r'\s*Part\.?\s*\d+', '', album_name, flags=re.IGNORECASE)
    
    # 버전 정보 제거 (예: "2nd", "3rd", "Vol.1")
    album_name = re.sub(r'\s*\d+(st|nd|rd|th)', '', album_name, flags=re.IGNORECASE)
    album_name = re.sub(r'\s*Vol\.?\s*\d+', '', album_name, flags=re.IGNORECASE)
    
    # 여러 공백을 하나로 변환
    album_name = " ".join(album_name.split())
    
    return album_name.strip()


def _preprocess_artist_name(artist_name: str, aggressive: bool = False) -> str:
    """
    아티스트명을 검색에 적합하게 전처리한다.
    feat., Feat. 제거 및 콜라보 아티스트 처리
    
    Args:
        artist_name: 원본 아티스트명
        aggressive: True일 경우 괄호 안 모든 내용과 숫자 제거
    
    Returns:
        전처리된 아티스트명
    """
    if not artist_name:
        return ""
    
    import re
    # 일본어 제거
    artist_name = _remove_japanese(artist_name)
    
    # feat., Feat. 이후 부분 제거 (괄호 안/밖 모두)
    artist_name = re.sub(r'\s*\(?\s*[Ff]eat\.?\s+[^\)]+\)?', '', artist_name)
    artist_name = re.sub(r'\s*\(?\s*[Ff]t\.?\s+[^\)]+\)?', '', artist_name)
    
    # 콤마로 구분된 콜라보 아티스트가 있으면 첫 번째만 사용
    if ',' in artist_name:
        artist_name = artist_name.split(',')[0].strip()
    
    # aggressive 모드: 괄호 안 모든 내용 제거 및 숫자/기수 제거
    if aggressive:
        # 괄호 안 내용 모두 제거 ("정키 (정희웅)" → "정키", "민니 ((여자)아이들)" → "민니")
        artist_name = re.sub(r'\s*\([^)]+\)', '', artist_name)
        artist_name = re.sub(r'\s*\（[^）]+\）', '', artist_name)  # 전각 괄호
        
        # 숫자 + "기" 제거 ("베이비 복스 1기" → "베이비 복스")
        artist_name = re.sub(r'\s*\d+기', '', artist_name)
        
        # 끝의 숫자 제거 ("베이비 복스 1" → "베이비 복스")
        artist_name = re.sub(r'\s+\d+$', '', artist_name)
    
    # 여러 공백을 하나로 변환
    artist_name = " ".join(artist_name.split())
    
    return artist_name.strip()


def _preprocess_song_name(song_name: str, aggressive: bool = False) -> str:
    """
    곡명을 검색에 적합하게 전처리한다.
    
    Args:
        song_name: 원본 곡명
        aggressive: True일 경우 괄호 안 모든 내용 제거
    
    Returns:
        전처리된 곡명
    """
    if not song_name:
        return ""
    
    import re
    # 일본어 제거
    song_name = _remove_japanese(song_name)
    
    # aggressive 모드: 괄호 안 모든 내용 제거
    if aggressive:
        # 괄호 안 내용 제거 ("첫사랑(From 응답하라 1994)" → "첫사랑")
        song_name = re.sub(r'\s*\([^)]+\)', '', song_name)
        song_name = re.sub(r'\s*\（[^）]+\）', '', song_name)  # 전각 괄호
    
    # 여러 공백을 하나로 변환
    song_name = " ".join(song_name.split())
    
    return song_name.strip()


def _sanitize_search_text(text: str) -> str:
    """
    검색 텍스트에서 특수문자를 제거하거나 변환한다.
    플랫폼 검색에서 문제가 될 수 있는 특수문자를 처리한다.
    """
    if not text:
        return ""
    
    # & 기호를 공백으로 변환 (예: "최인희&오혜주" -> "최인희 오혜주")
    text = text.replace("&", " ")
    # 여러 공백을 하나로 변환
    text = " ".join(text.split())
    
    return text.strip()


def _remove_all_special_chars(text: str) -> str:
    """
    텍스트에서 모든 특수기호를 제거하고 한글, 영문자, 숫자, 공백만 남긴다.
    검색 실패 시 재시도를 위해 사용된다.
    
    Args:
        text: 처리할 텍스트
    
    Returns:
        특수기호가 제거된 텍스트
    """
    if not text:
        return ""
    
    import re
    # 한글(가-힣), 영문자(a-z, A-Z), 숫자(0-9), 공백만 남기고 나머지 모두 제거
    text = re.sub(r'[^a-zA-Z0-9\s가-힣]', '', text)
    # 여러 공백을 하나로 변환
    text = " ".join(text.split())
    
    return text.strip()


def _build_search_query(song_name: str, artist_name: str, album_name: str) -> str:
    """
    곡명, 아티스트명, 앨범명을 합쳐 GENIE 검색 쿼리를 생성한다.

    Args:
        song_name: 곡명
        artist_name: 아티스트명
        album_name: 앨범명

    Returns:
        검색 쿼리 문자열
    """
    # 특수문자 정제
    song_name = _sanitize_search_text(song_name)
    artist_name = _sanitize_search_text(artist_name)
    album_name = _sanitize_search_text(album_name)

    # GENIE는 "곡명/아티스트명" 형식을 선호하지만, 앨범명 포함 시 공백 사용
    # 앨범명이 있으면 모두 공백으로 결합
    if album_name:
        parts = []
        if song_name:
            parts.append(song_name)
        if artist_name:
            parts.append(artist_name)
        if album_name:
            parts.append(album_name)
        return " ".join(parts) if parts else ""
    # 곡명과 아티스트명만 있는 경우 "/" 사용
    elif song_name and artist_name:
        return f"{song_name}/{artist_name}"
    # 곡명만 있거나 아티스트명만 있는 경우
    elif song_name:
        return song_name
    elif artist_name:
        return artist_name
    else:
        return ""


def _build_search_url(query: str) -> str:
    """
    GENIE 검색 URL을 생성한다.

    한글/공백 등이 포함된 검색어를 안전하게 GET 쿼리스트링으로 인코딩하기 위해
    urllib.parse.urlencode를 사용한다.
    """
    import urllib.parse

    base = "https://www.genie.co.kr/search/searchSong"
    qs = urllib.parse.urlencode({"query": query})
    return f"{base}?{qs}"


def _extract_song_id(html: str) -> Optional[str]:
    """GENIE 검색 결과 HTML에서 첫 번째 곡의 song_id를 추출한다."""
    soup = BeautifulSoup(html, "html.parser")
    # 일반적으로 곡 리스트에서 detail/songInfo?xgnm=XXXX 형태의 링크를 사용
    for a in soup.find_all("a"):
        onclick = a.get("onclick") or ""
        if "fnViewSongInfo" in onclick:
            import re

            m = re.search(r"fnViewSongInfo\('(\d+)'\)", onclick)
            if m:
                return m.group(1)
    return None


def _write_song_ids_csv(platform: str, song_data_list: List[Dict[str, str]], resource_dir: str) -> List[Dict[str, str]]:
    """
    song_data.csv 파일을 새로운 명세에 맞춰 17개 컬럼으로 저장한다.
    
    Returns:
        중복 제거된 곡들의 정보 리스트
    """
    import json
    
    csv_path = Path(resource_dir) / platform / "song_data.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # 중복 제거 (track_cd 기준)
    unique_data = []
    seen_track_codes = {}  # track_cd -> 첫 번째 데이터 매핑
    duplicates = []  # 중복된 곡 목록
    
    for data in song_data_list:
        track_cd = data.get("track_cd", "").strip()
        if track_cd:
            if track_cd not in seen_track_codes:
                seen_track_codes[track_cd] = data
                unique_data.append(data)
            else:
                # 중복 발견
                first_data = seen_track_codes[track_cd]
                duplicates.append({
                    "track_cd": track_cd,
                    "first_song_id": first_data.get("platform_song_id", ""),
                    "duplicate_song_id": data.get("platform_song_id", ""),
                    "song_name": data.get("song_name_kor", ""),
                    "artist_name": data.get("artist_name_kor", "")
                })

    # 새로운 컬럼 순서 (명세에 맞춤 - 20개 필드)
    fieldnames = [
        "platform_seq",
        "platform_name",
        "song_type_txt",
        "album_cd",
        "album_name_kor",
        "album_name_eng",
        "song_cd",
        "song_name_kor",
        "song_name_eng",
        "song_release_date",
        "artist_cd",
        "artist_name_kor",
        "artist_name_eng",
        "mem_cd",
        "mem_name",
        "track_cd",
        "isrc_cd",
        "interest_yn",
        "platform_artist_ids",
        "platform_song_ids"
    ]

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for data in unique_data:
            # platform_song_ids를 JSON 문자열로 변환
            platform_song_id = data.get("platform_song_id", "")
            platform_song_ids_json = json.dumps({platform.upper(): platform_song_id}) if platform_song_id else "{}"
            
            # platform_artist_ids는 현재 미수집이므로 빈 문자열
            platform_artist_ids_json = ""
            
            writer.writerow({
                "platform_seq": data.get("platform_seq", ""),
                "platform_name": data.get("platform_name", ""),
                "song_type_txt": data.get("song_type_txt", ""),
                "album_cd": data.get("album_cd", ""),
                "album_name_kor": data.get("album_name_kor", ""),
                "album_name_eng": data.get("album_name_eng", ""),
                "song_cd": data.get("song_cd", ""),
                "song_name_kor": data.get("song_name_kor", ""),
                "song_name_eng": data.get("song_name_eng", ""),
                "song_release_date": data.get("song_release_date", ""),
                "artist_cd": data.get("artist_cd", ""),
                "artist_name_kor": data.get("artist_name_kor", ""),
                "artist_name_eng": data.get("artist_name_eng", ""),
                "mem_cd": data.get("mem_cd", ""),
                "mem_name": data.get("mem_name", ""),
                "track_cd": data.get("track_cd", ""),
                "isrc_cd": data.get("isrc_cd", ""),
                "interest_yn": data.get("interest_yn", "n"),
                "platform_artist_ids": platform_artist_ids_json,
                "platform_song_ids": platform_song_ids_json
            })

    logger.info(f"[{platform}] song_data.csv에 {len(unique_data)}개의 곡 정보를 기록했습니다: {csv_path}")
    return duplicates


def generate_song_ids(config_path: str) -> None:
    """config와 search_data.csv를 기반으로 song_data.csv를 생성/갱신한다."""
    config = load_config(config_path)
    resource_dir = config.get("resource_dir", "resource")
    platforms_config = config.get("platforms", {})

    # enabled_platforms에 포함된 플랫폼만 처리
    enabled_platforms = set(config.get("enabled_platforms", []))

    fetcher = Fetcher(mode="requests", timeout_sec=config.get("http", {}).get("timeout_sec", 20))

    try:
        for platform_name in platforms_config.keys():
            platform = platform_name.upper()
            if platform not in enabled_platforms:
                logger.info(f"[{platform}] enabled_platforms에 포함되지 않아 건너뜁니다.")
                continue

            rows = _read_search_data(platform, resource_dir)
            if not rows:
                continue

            song_data_list: List[Dict[str, str]] = []
            failed_songs: List[Dict[str, str]] = []  # 실패한 곡 목록
            for row in rows:
                # 검색용 필드
                song_name = row.get("song_name", "")
                artist_name = row.get("artist_name", "")
                album_name = row.get("album_name", "")
                
                song_id = None
                tried_queries = []
                
                # 다단계 검색 시도
                # 1단계: 원본 그대로 검색
                query1 = _build_search_query(song_name, artist_name, album_name)
                if query1:
                    tried_queries.append(query1)
                    try:
                        search_url = _build_search_url(query1)
                        logger.info(f"[GENIE] [1단계] 검색: '{query1}'")
                        html = fetcher.fetch_html(search_url)
                        song_id = _extract_song_id(html)
                        if song_id:
                            logger.info(f"[GENIE] ✅ [1단계] 성공 - song_id={song_id}")
                    except Exception as e:
                        logger.error(f"[GENIE] [1단계] 검색 중 오류: {e}")

                # 2단계: 앨범명/아티스트명 전처리 후 검색
                if not song_id:
                    preprocessed_album = _preprocess_album_name(album_name)
                    preprocessed_artist = _preprocess_artist_name(artist_name)
                    query2 = _build_search_query(song_name, preprocessed_artist, preprocessed_album)

                    if query2 and query2 not in tried_queries:
                        tried_queries.append(query2)
                        try:
                            search_url = _build_search_url(query2)
                            logger.info(f"[GENIE] [2단계] 전처리 검색: '{query2}'")
                            html = fetcher.fetch_html(search_url)
                            song_id = _extract_song_id(html)
                            if song_id:
                                logger.info(f"[GENIE] ✅ [2단계] 성공 - song_id={song_id}")
                        except Exception as e:
                            logger.error(f"[GENIE] [2단계] 검색 중 오류: {e}")

                # 3단계: 앨범명 없이 검색 (곡명 + 전처리된 아티스트명)
                if not song_id:
                    preprocessed_artist = _preprocess_artist_name(artist_name)
                    query3 = _build_search_query(song_name, preprocessed_artist, "")

                    if query3 and query3 not in tried_queries:
                        tried_queries.append(query3)
                        try:
                            search_url = _build_search_url(query3)
                            logger.info(f"[GENIE] [3단계] 앨범명 제외 검색: '{query3}'")
                            html = fetcher.fetch_html(search_url)
                            song_id = _extract_song_id(html)
                            if song_id:
                                logger.info(f"[GENIE] ✅ [3단계] 성공 - song_id={song_id}")
                        except Exception as e:
                            logger.error(f"[GENIE] [3단계] 검색 중 오류: {e}")
                
                # 4단계: 특수기호 제거 후 검색
                if not song_id:
                    song_name_cleaned = _remove_all_special_chars(song_name)
                    artist_name_cleaned = _remove_all_special_chars(artist_name)
                    query4 = _build_search_query(song_name_cleaned, artist_name_cleaned, "")

                    if query4 and query4 not in tried_queries:
                        tried_queries.append(query4)
                        try:
                            search_url = _build_search_url(query4)
                            logger.info(f"[GENIE] [4단계] 특수기호 제거 검색: '{query4}'")
                            html = fetcher.fetch_html(search_url)
                            song_id = _extract_song_id(html)
                            if song_id:
                                logger.info(f"[GENIE] ✅ [4단계] 성공 - song_id={song_id}")
                        except Exception as e:
                            logger.error(f"[GENIE] [4단계] 검색 중 오류: {e}")

                # 5단계: 곡명/아티스트명 괄호 제거 (aggressive)
                if not song_id:
                    song_name_aggressive = _preprocess_song_name(song_name, aggressive=True)
                    artist_name_aggressive = _preprocess_artist_name(artist_name, aggressive=True)
                    query5 = _build_search_query(song_name_aggressive, artist_name_aggressive, "")

                    if query5 and query5 not in tried_queries:
                        tried_queries.append(query5)
                        try:
                            search_url = _build_search_url(query5)
                            logger.info(f"[GENIE] [5단계] 괄호 제거 검색: '{query5}'")
                            html = fetcher.fetch_html(search_url)
                            song_id = _extract_song_id(html)
                            if song_id:
                                logger.info(f"[GENIE] ✅ [5단계] 성공 - song_id={song_id}")
                        except Exception as e:
                            logger.error(f"[GENIE] [5단계] 검색 중 오류: {e}")

                # 6단계: 곡명만으로 검색 (아티스트 제외)
                if not song_id:
                    song_name_aggressive = _preprocess_song_name(song_name, aggressive=True)
                    query6 = _build_search_query(song_name_aggressive, "", "")

                    if query6 and query6 not in tried_queries:
                        tried_queries.append(query6)
                        try:
                            search_url = _build_search_url(query6)
                            logger.info(f"[GENIE] [6단계] 곡명만 검색: '{query6}'")
                            html = fetcher.fetch_html(search_url)
                            song_id = _extract_song_id(html)
                            if song_id:
                                logger.info(f"[GENIE] ✅ [6단계] 성공 - song_id={song_id}")
                        except Exception as e:
                            logger.error(f"[GENIE] [6단계] 검색 중 오류: {e}")

                # 7단계: 특수기호 제거 + 곡명만
                if not song_id:
                    song_name_cleaned = _remove_all_special_chars(song_name)
                    query7 = _build_search_query(song_name_cleaned, "", "")

                    if query7 and query7 not in tried_queries:
                        tried_queries.append(query7)
                        try:
                            search_url = _build_search_url(query7)
                            logger.info(f"[GENIE] [7단계] 특수기호 제거 + 곡명만: '{query7}'")
                            html = fetcher.fetch_html(search_url)
                            song_id = _extract_song_id(html)
                            if song_id:
                                logger.info(f"[GENIE] ✅ [7단계] 성공 - song_id={song_id}")
                            else:
                                logger.warning(f"[GENIE] ❌ 모든 단계 실패 (7단계까지): {song_name} - {artist_name}")
                        except Exception as e:
                            logger.error(f"[GENIE] [7단계] 검색 중 오류: {e}")
                
                # song_id를 찾은 경우에만 리스트에 추가
                if song_id:
                    # 모든 필드를 포함하여 추가 (새로운 명세 20개 필드)
                    song_data_list.append({
                        "platform_song_id": song_id,  # 플랫폼별 song_id
                        "platform_seq": row.get("platform_seq", ""),
                        "platform_name": row.get("platform_name", ""),
                        "song_type_txt": row.get("song_type_txt", ""),
                        "album_cd": row.get("album_cd", ""),
                        "album_name_kor": row.get("album_name_kor", ""),
                        "album_name_eng": row.get("album_name_eng", ""),
                        "song_cd": row.get("song_cd", ""),
                        "song_name_kor": row.get("song_name_kor", ""),
                        "song_name_eng": row.get("song_name_eng", ""),
                        "song_release_date": row.get("song_release_date", ""),
                        "artist_cd": row.get("artist_cd", ""),
                        "artist_name_kor": row.get("artist_name_kor", ""),
                        "artist_name_eng": row.get("artist_name_eng", ""),
                        "mem_cd": row.get("mem_cd", ""),
                        "mem_name": row.get("mem_name", ""),
                        "track_cd": row.get("track_cd", ""),
                        "isrc_cd": row.get("isrc_cd", ""),
                        "interest_yn": row.get("interest_yn", "n"),
                    })
                else:
                    # 실패한 곡 정보 저장
                    failed_songs.append({
                        "song_name": song_name,
                        "artist_name": artist_name,
                        "album_name": album_name,
                        "track_cd": row.get("track_cd", ""),
                        "isrc_cd": row.get("isrc_cd", ""),
                        "song_type_text": row.get("song_type_text", "")
                    })

            # 결과 저장
            duplicates = []
            if song_data_list:
                duplicates = _write_song_ids_csv(platform, song_data_list, resource_dir)
            else:
                logger.warning(f"[{platform}] 검색 결과에서 song_id를 전혀 찾지 못했습니다.")
            
            # 통계 출력
            total_count = len(rows)
            success_count = len(song_data_list)
            failed_count = len(failed_songs)
            duplicate_count = len(duplicates)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"[{platform}] 검색 완료 - 총 {total_count}곡 중 {success_count}곡 성공, {failed_count}곡 실패")
            if duplicate_count > 0:
                logger.info(f"[{platform}] 중복 제거: {duplicate_count}곡 (동일한 track_cd)")
            logger.info(f"{'='*80}")
            
            # 실패한 곡 목록 출력
            if failed_songs:
                logger.warning(f"\n[{platform}] ❌ 검색 실패한 곡 목록 ({failed_count}곡):")
                logger.warning(f"{'-'*80}")
                for idx, failed in enumerate(failed_songs, 1):
                    logger.warning(
                        f"{idx}. [{failed['track_cd']}] "
                        f"{failed['song_name']} - {failed['artist_name']} "
                        f"(앨범: {failed['album_name'][:30]}{'...' if len(failed['album_name']) > 30 else ''})"
                    )
                logger.warning(f"{'-'*80}\n")
            
            # 중복된 곡 목록 출력
            if duplicates:
                logger.warning(f"\n[{platform}] 🔄 중복 제거된 곡 목록 ({duplicate_count}곡):")
                logger.warning(f"{'-'*80}")
                for idx, dup in enumerate(duplicates, 1):
                    logger.warning(
                        f"{idx}. [track_cd={dup['track_cd']}] "
                        f"{dup['song_name']} - {dup['artist_name']}"
                    )
                    logger.warning(
                        f"   첫 번째: song_id={dup['first_song_id']}, "
                        f"중복: song_id={dup['duplicate_song_id']}"
                    )
                logger.warning(f"{'-'*80}\n")
    finally:
        fetcher.close()


def main():
    """검색용 CSV를 기반으로 song_data.csv를 생성하는 CLI."""
    parser = argparse.ArgumentParser(description="search_data.csv를 기반으로 song_id 자동 생성")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="설정 파일 경로 (기본값: config.yaml)",
    )

    args = parser.parse_args()
    config_path = args.config

    if not Path(config_path).exists():
        logger.error(f"설정 파일을 찾을 수 없습니다: {config_path}")
        sys.exit(1)

    generate_song_ids(config_path)


if __name__ == "__main__":
    main()


