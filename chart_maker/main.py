"""chart_maker CLI 엔트리포인트.

예시:
    # 디렉토리 내 모든 JSONL 파일 재귀적 로드
    python -m chart_maker.main render \
        --input data/logs \
        --outdir output \
        --topn 10 \
        --platform GENIE
    
    # 특정 파일만 로드
    python -m chart_maker.main render \
        --input data/logs/2025-12-17_GENIE.jsonl \
        --outdir output \
        --topn 10
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from . import charts, io, metrics, report, transform, utils


logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="플랫폼 스트리밍 지표 차트 생성기")

    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="JSONL 입력으로부터 차트/리포트 생성")
    render.add_argument(
        "--input",
        required=True,
        help="입력 JSONL 파일 경로 또는 디렉토리 (디렉토리인 경우 재귀적으로 모든 *.jsonl 파일 로드)",
    )
    render.add_argument(
        "--outdir",
        default="output",
        help="출력 루트 디렉토리 (기본: output)",
    )
    render.add_argument(
        "--platform",
        default=None,
        help="특정 플랫폼만 필터 (예: GENIE). 생략 시 전체.",
    )
    render.add_argument(
        "--song-id",
        dest="song_id",
        default=None,
        help="특정 곡(song_id)만 필터. 생략 시 전체.",
    )
    render.add_argument(
        "--topn",
        type=int,
        default=10,
        help="플랫폼 요약 차트에서 상위 N곡 (기본: 10)",
    )
    render.add_argument(
        "--export-html",
        action="store_true",
        default=True,
        help="plotly HTML 리포트 생성 여부 (기본: true)",
    )
    render.add_argument(
        "--no-export-html",
        dest="export_html",
        action="store_false",
        help="HTML 리포트 생성을 비활성화",
    )
    render.add_argument(
        "--export-png",
        action="store_true",
        default=True,
        help="matplotlib PNG 생성 여부 (기본: true)",
    )
    render.add_argument(
        "--no-export-png",
        dest="export_png",
        action="store_false",
        help="PNG 생성을 비활성화",
    )

    return parser.parse_args()


def cmd_render(
    input_path: Path,
    outdir: Path,
    platform: Optional[str],
    song_id: Optional[str],
    topn: int,
    export_html: bool,
    export_png: bool,
) -> None:
    utils.setup_logging()

    logger.info("입력 JSONL 로드 시작: %s", input_path)
    df_raw = io.load_jsonl(input_path)
    if df_raw.empty:
        logger.error("입력 데이터가 비어 있습니다. 종료합니다.")
        return

    # 정규화/정제
    df_norm, dup_count = transform.normalize(df_raw)
    logger.info("정규화 완료. 중복 충돌 건수: %d", dup_count)

    # 필터링
    if platform:
        df_norm = df_norm[df_norm["platform"] == platform]
    if song_id:
        df_norm = df_norm[df_norm["song_id"] == str(song_id)]

    if df_norm.empty:
        logger.error("필터링 후 데이터가 없습니다. 종료합니다.")
        return

    # 파생 지표 계산
    df_metrics, num_anomalies = metrics.add_metrics(df_norm)
    logger.info("파생 지표 계산 완료. 음수 diff 이상치: %d건", num_anomalies)

    # 요약 테이블 생성
    df_summary, anomalies_per_platform = report.build_summary_table(df_metrics)

    outdir = Path(outdir)
    png_dir = outdir / "png"
    html_dir = outdir / "reports"
    csv_dir = outdir / "csv"

    # 곡별 차트 생성 (PNG)
    if export_png:
        for (plat, sid), g in df_metrics.groupby(["platform", "song_id"]):
            charts.plot_song_totals(g, png_dir, plat, sid)
            charts.plot_song_deltas(g, png_dir, plat, sid)

        # 플랫폼 요약 차트
        plats = [platform] if platform else sorted(df_metrics["platform"].unique())
        for plat in plats:
            charts.plot_platform_summary(df_metrics, png_dir, plat, topn=topn)

    # 곡별 HTML 리포트
    if export_html:
        for (plat, sid), g in df_metrics.groupby(["platform", "song_id"]):
            row = df_summary[
                (df_summary["platform"] == plat) & (df_summary["song_id"] == sid)
            ]
            if row.empty:
                continue
            summary_row = row.iloc[0]
            out_path = html_dir / f"{plat}_{sid}_report.html"
            report.generate_song_report_html(g, summary_row, out_path)

    # 요약 CSV 저장
    io.save_summary_csv(df_summary, csv_dir)

    logger.info("렌더링 완료. 출력 디렉토리: %s", outdir)


def main() -> None:
    args = _parse_args()

    if args.command == "render":
        cmd_render(
            input_path=Path(args.input),
            outdir=Path(args.outdir),
            platform=args.platform,
            song_id=args.song_id,
            topn=args.topn,
            export_html=args.export_html,
            export_png=args.export_png,
        )


if __name__ == "__main__":
    main()


