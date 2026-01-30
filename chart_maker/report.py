"""요약 테이블 및 HTML 리포트 생성."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import plotly.graph_objs as go
from plotly.offline import plot as plot_offline

from .utils import ensure_dir

logger = logging.getLogger(__name__)


def build_summary_table(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """플랫폼별 요약 테이블을 생성한다."""
    if df.empty:
        return pd.DataFrame(), {}

    records = []
    anomalies_per_platform: Dict[str, int] = {}

    for (platform, song_id), g in df.groupby(["platform", "song_id"]):
        g = g.sort_values("timestamp")
        first = g.iloc[0]
        last = g.iloc[-1]

        net_plays = (last["total_plays"] or 0) - (first["total_plays"] or 0)
        net_listeners = (last["total_listeners"] or 0) - (first["total_listeners"] or 0)

        avg_rate_plays = g["rate_plays_per_min"].dropna().mean()
        avg_rate_listeners = g["rate_listeners_per_min"].dropna().mean()

        num_points = len(g)
        num_anomalies = int(g["is_anomaly_negative_diff"].sum())

        anomalies_per_platform.setdefault(platform, 0)
        anomalies_per_platform[platform] += num_anomalies

        records.append(
            {
                "platform": platform,
                "song_id": song_id,
                "song_name": str(last.get("song_name") or first.get("song_name") or ""),
                "artist_name": str(
                    last.get("artist_name") or first.get("artist_name") or ""
                ),
                "first_timestamp": first["timestamp"],
                "last_timestamp": last["timestamp"],
                "first_total_plays": first["total_plays"],
                "last_total_plays": last["total_plays"],
                "net_plays": net_plays,
                "first_total_listeners": first["total_listeners"],
                "last_total_listeners": last["total_listeners"],
                "net_listeners": net_listeners,
                "avg_rate_plays_per_min": avg_rate_plays,
                "avg_rate_listeners_per_min": avg_rate_listeners,
                "num_points": num_points,
                "num_anomalies_negative_diff": num_anomalies,
            }
        )

    df_summary = pd.DataFrame(records)
    return df_summary, anomalies_per_platform


def generate_song_report_html(
    df_song: pd.DataFrame,
    summary_row: pd.Series,
    out_path: Path,
) -> None:
    """단일 곡에 대한 HTML 리포트를 생성한다."""
    if df_song.empty:
        return

    out_dir = ensure_dir(out_path.parent)

    # totals line chart
    fig_totals = go.Figure()
    fig_totals.add_trace(
        go.Scatter(
            x=df_song["timestamp"],
            y=df_song["total_plays"],
            mode="lines+markers",
            name="total_plays",
        )
    )
    if df_song["total_listeners"].notna().any():
        fig_totals.add_trace(
            go.Scatter(
                x=df_song["timestamp"],
                y=df_song["total_listeners"],
                mode="lines+markers",
                name="total_listeners",
            )
        )
    fig_totals.update_layout(
        title="누적 지표 (total_plays / total_listeners)",
        xaxis_title="timestamp",
        yaxis_title="count",
    )

    # delta line chart
    fig_delta = go.Figure()
    if df_song["delta_plays"].notna().any():
        fig_delta.add_trace(
            go.Scatter(
                x=df_song["timestamp"],
                y=df_song["delta_plays"],
                mode="lines+markers",
                name="delta_plays",
            )
        )
    if df_song["delta_listeners"].notna().any():
        fig_delta.add_trace(
            go.Scatter(
                x=df_song["timestamp"],
                y=df_song["delta_listeners"],
                mode="lines+markers",
                name="delta_listeners",
            )
        )
    fig_delta.update_layout(
        title="증가량 (delta_plays / delta_listeners)",
        xaxis_title="timestamp",
        yaxis_title="delta",
    )

    # HTML 구성
    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="ko">')
    html_parts.append('<head>')
    html_parts.append('<meta charset="utf-8">')
    html_parts.append('<meta http-equiv="Content-Type" content="text/html; charset=utf-8">')
    html_parts.append('<title>곡 리포트</title>')
    html_parts.append('</head>')
    html_parts.append('<body>')

    html_parts.append("<h1>곡 리포트</h1>")
    html_parts.append("<h2>요약 정보</h2>")
    # escape=False로 설정하여 한글 등 특수문자가 HTML entities로 변환되지 않도록 함
    html_parts.append(summary_row.to_frame().to_html(header=False, border=1, escape=False))

    html_parts.append("<h2>누적 지표 차트</h2>")
    # 첫 번째 차트에서만 Plotly.js 포함
    html_parts.append(plot_offline(fig_totals, include_plotlyjs=True, output_type="div"))

    html_parts.append("<h2>증가량 차트</h2>")
    # 두 번째 차트부터는 Plotly.js 제외 (이미 포함됨)
    html_parts.append(plot_offline(fig_delta, include_plotlyjs=False, output_type="div"))

    html_parts.append("</body></html>")

    out_html = "\n".join(html_parts)
    out_path.write_text(out_html, encoding="utf-8")
    logger.info("곡 HTML 리포트 저장: %s", out_path)



