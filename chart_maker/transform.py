"""JSONL 원본 데이터를 정규화/정제하는 모듈."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = [
    "platform",
    "song_id",
    "song_name",
    "artist_name",
    "date",
    "hour",
    "minute",
    "total_plays",
    "total_listeners",
]


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """필수 컬럼이 없으면 생성하고, 타입을 가능한 한 맞춰준다."""
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # 날짜/시간 관련
    df["date"] = df["date"].astype(str)
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(0).astype(int)
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce").fillna(0).astype(int)

    # 지표는 숫자로
    df["total_plays"] = pd.to_numeric(df["total_plays"], errors="coerce")
    df["total_listeners"] = pd.to_numeric(df["total_listeners"], errors="coerce")

    # 문자열 컬럼
    for col in ["platform", "song_id", "song_name", "artist_name", "album_name", "song_type", "track_code", "isrc"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    return df


def _build_timestamp(df: pd.DataFrame) -> pd.Series:
    """date + hour + minute 로 timestamp 컬럼 생성."""
    # "YYYY-MM-DD HH:MM" 형식 문자열 생성 후 to_datetime
    ts_str = df["date"].astype(str) + " " + df["hour"].astype(str).str.zfill(2) + ":" + df[
        "minute"
    ].astype(str).str.zfill(2)
    ts = pd.to_datetime(ts_str, errors="coerce")
    return ts


def normalize(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    원본 DataFrame을 정규화/정제한다.

    - 필수 컬럼 보정
    - timestamp 생성
    - (platform, song_id, timestamp) 중복 처리
    - 정렬

    Returns:
        (정제된 DataFrame, 중복 충돌 건수)
    """
    if df_raw.empty:
        return df_raw.copy(), 0

    df = df_raw.copy()
    df = _ensure_columns(df)

    # timestamp 생성
    df["timestamp"] = _build_timestamp(df)

    # 고유 키 정의
    df["key"] = df["platform"] + "::" + df["song_id"] + "::" + df["timestamp"].astype(str)

    # 중복 처리: 같은 키가 여러 번 나오면 마지막 레코드 채택
    dup_counts = df.duplicated("key").sum()
    if dup_counts > 0:
        logger.info("중복 키 %d건 발견 (마지막 레코드만 사용)", dup_counts)

    # groupby로 마지막 레코드 선택
    df = df.sort_values(["key"]).groupby("key", as_index=False).tail(1)

    # 정렬: platform, song_id, timestamp
    df = df.sort_values(["platform", "song_id", "timestamp"]).reset_index(drop=True)

    # key 컬럼은 더 이상 필요 없으므로 제거
    df = df.drop(columns=["key"])

    # 잘못된 timestamp(파싱 실패)는 제거
    before = len(df)
    df = df[df["timestamp"].notna()].copy()
    removed = before - len(df)
    if removed > 0:
        logger.warning("timestamp 파싱 실패로 %d개 레코드를 제거했습니다.", removed)

    return df, int(dup_counts)



