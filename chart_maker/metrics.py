"""파생 지표(증가량, 증가율 등)를 계산하는 모듈."""

from __future__ import annotations

import logging
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def add_metrics(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    곡별 시계열에 파생 지표를 추가한다.

    추가 컬럼:
        - delta_plays
        - delta_listeners
        - delta_minutes
        - rate_plays_per_min
        - rate_listeners_per_min
        - is_anomaly_negative_diff (음수 diff 여부)

    Returns:
        (지표가 추가된 DataFrame, 음수 diff 이상치 개수)
    """
    if df.empty:
        return df.copy(), 0

    df = df.copy()

    df = df.sort_values(["platform", "song_id", "timestamp"])

    df["delta_plays"] = (
        df.groupby(["platform", "song_id"])["total_plays"].diff()
    )
    df["delta_listeners"] = (
        df.groupby(["platform", "song_id"])["total_listeners"].diff()
    )

    # 분 단위 시간 차이
    df["delta_minutes"] = (
        df.groupby(["platform", "song_id"])["timestamp"]
        .diff()
        .dt.total_seconds()
        .div(60.0)
    )

    # 증가율 (분당)
    # delta_minutes <= 0 인 경우는 NaN 처리
    valid_time = df["delta_minutes"] > 0
    df["rate_plays_per_min"] = pd.NA
    df["rate_listeners_per_min"] = pd.NA

    df.loc[valid_time, "rate_plays_per_min"] = (
        df.loc[valid_time, "delta_plays"] / df.loc[valid_time, "delta_minutes"]
    )
    df.loc[valid_time, "rate_listeners_per_min"] = (
        df.loc[valid_time, "delta_listeners"] / df.loc[valid_time, "delta_minutes"]
    )

    # 누적값이 감소하는 경우 이상치로 표시
    anomaly_mask = (df["delta_plays"] < 0) | (df["delta_listeners"] < 0)
    df["is_anomaly_negative_diff"] = anomaly_mask
    num_anomalies = int(anomaly_mask.sum())

    if num_anomalies > 0:
        logger.warning("누적값 감소 이상치 %d건 발견 (음수 diff)", num_anomalies)

    return df, num_anomalies



