"""matplotlib/plotly 차트 생성 모듈."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from .utils import ensure_dir

logger = logging.getLogger(__name__)


def plot_song_totals(df: pd.DataFrame, outdir: Path, platform: str, song_id: str) -> None:
    """곡별 total_plays / total_listeners 시계열 라인 차트를 생성한다."""
    df_song = df[(df["platform"] == platform) & (df["song_id"] == song_id)].copy()
    if df_song.empty:
        return

    outdir = ensure_dir(outdir)
    plt.figure(figsize=(10, 6))

    plt.plot(df_song["timestamp"], df_song["total_plays"], label="total_plays", marker="o")
    if df_song["total_listeners"].notna().any():
        plt.plot(
            df_song["timestamp"],
            df_song["total_listeners"],
            label="total_listeners",
            marker="o",
        )

    title = f"{platform} - {song_id} (누적값)"
    plt.title(title)
    plt.xlabel("timestamp")
    plt.ylabel("count")
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    plt.tight_layout()

    out_path = outdir / f"{platform}_{song_id}_totals.png"
    plt.savefig(out_path)
    plt.close()
    logger.info("곡별 totals 차트 저장: %s", out_path)


def plot_song_deltas(df: pd.DataFrame, outdir: Path, platform: str, song_id: str) -> None:
    """곡별 delta_plays / delta_listeners 시계열 차트를 생성한다."""
    df_song = df[(df["platform"] == platform) & (df["song_id"] == song_id)].copy()
    if df_song.empty:
        return

    outdir = ensure_dir(outdir)
    plt.figure(figsize=(10, 6))

    if df_song["delta_plays"].notna().any():
        plt.plot(df_song["timestamp"], df_song["delta_plays"], label="delta_plays", marker="o")
    if df_song["delta_listeners"].notna().any():
        plt.plot(
            df_song["timestamp"],
            df_song["delta_listeners"],
            label="delta_listeners",
            marker="o",
        )

    title = f"{platform} - {song_id} (증가량)"
    plt.title(title)
    plt.xlabel("timestamp")
    plt.ylabel("delta")
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    plt.tight_layout()

    out_path = outdir / f"{platform}_{song_id}_delta.png"
    plt.savefig(out_path)
    plt.close()
    logger.info("곡별 delta 차트 저장: %s", out_path)


def plot_platform_summary(
    df: pd.DataFrame,
    outdir: Path,
    platform: str,
    topn: int = 10,
) -> None:
    """플랫폼 단위 요약 차트(최종 재생수 상위 N곡, 최근 증가량 상위 N곡)를 생성한다."""
    df_plat = df[df["platform"] == platform].copy()
    if df_plat.empty:
        return

    outdir = ensure_dir(outdir)

    # 최종 시점 기준 total_plays 상위 N곡
    last_points = (
        df_plat.sort_values("timestamp")
        .groupby("song_id", as_index=False)
        .tail(1)
    )
    top_totals = last_points.nlargest(topn, "total_plays")

    plt.figure(figsize=(10, 6))
    plt.bar(top_totals["song_id"].astype(str), top_totals["total_plays"])
    plt.title(f"{platform} - 최종 total_plays 상위 {topn}곡")
    plt.xlabel("song_id")
    plt.ylabel("total_plays")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out_path = outdir / f"{platform}_top{topn}_totals.png"
    plt.savefig(out_path)
    plt.close()
    logger.info("플랫폼 요약 totals 차트 저장: %s", out_path)

    # 최근 3포인트 기준 평균 delta_plays 상위 N곡
    df_plat = df_plat.sort_values("timestamp")
    last3 = df_plat.groupby("song_id").tail(3)
    avg_delta = (
        last3.groupby("song_id")["delta_plays"]
        .mean()
        .reset_index()
        .rename(columns={"delta_plays": "avg_delta_plays"})
    )
    top_delta = avg_delta.nlargest(topn, "avg_delta_plays")

    plt.figure(figsize=(10, 6))
    plt.bar(top_delta["song_id"].astype(str), top_delta["avg_delta_plays"])
    plt.title(f"{platform} - 최근 delta_plays 평균 상위 {topn}곡")
    plt.xlabel("song_id")
    plt.ylabel("avg_delta_plays")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out_path = outdir / f"{platform}_top{topn}_delta.png"
    plt.savefig(out_path)
    plt.close()
    logger.info("플랫폼 요약 delta 차트 저장: %s", out_path)



