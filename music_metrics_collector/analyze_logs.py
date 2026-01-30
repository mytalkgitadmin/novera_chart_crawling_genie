"""data/logs 디렉토리의 JSONL 로그를 읽어 플랫폼/곡별 차트를 생성하는 스크립트."""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import platform

from .main import load_config

logger = logging.getLogger(__name__)


def _setup_matplotlib_font() -> None:
    """Matplotlib에서 한글이 깨지지 않도록 폰트를 설정한다."""
    system = platform.system()

    # OS별 기본 한글 폰트 후보 목록
    if system == "Darwin":  # macOS
        candidates = ["AppleGothic", "NanumGothic", "Malgun Gothic"]
    elif system == "Windows":
        candidates = ["Malgun Gothic", "맑은 고딕", "MalgunGothic"]
    else:  # Linux 등
        candidates = ["NanumGothic", "Malgun Gothic", "DejaVu Sans"]

    for name in candidates:
        try:
            if any(f.name == name for f in fm.fontManager.ttflist):
                plt.rcParams["font.family"] = name
                logger.info(f"Matplotlib 한글 폰트 사용: {name}")
                break
        except Exception:
            # 폰트 조회 중 오류가 나더라도 전체 흐름에는 영향 주지 않음
            continue

    # 마이너스 기호(-)가 깨지지 않도록 설정
    plt.rcParams["axes.unicode_minus"] = False


def _load_logs(base_dir: Path) -> List[Dict]:
    """data/logs/{date}/{platform}.jsonl 구조의 모든 로그를 읽어 리스트로 반환한다."""
    records: List[Dict] = []
    if not base_dir.exists():
        logger.warning(f"로그 디렉토리가 없습니다: {base_dir}")
        return records

    for date_dir in sorted(base_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        for jsonl_file in sorted(date_dir.glob("*.jsonl")):
            try:
                with jsonl_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            records.append(rec)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON 파싱 실패 ({jsonl_file}): {e} / line={line[:80]}")
            except Exception as e:
                logger.error(f"로그 파일 읽기 실패: {jsonl_file} - {e}")
    logger.info(f"총 {len(records)}개의 로그 레코드를 읽었습니다.")
    return records


def _aggregate_by_song(
    records: List[Dict],
    metric_key: str,
    platform_filter: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    """
    (플랫폼, 곡)별로 날짜/메트릭을 집계한다.

    반환 구조:
        { "<platform>::<song_name>": { "YYYY-MM-DD": value_sum, ... }, ... }
    """
    agg: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for rec in records:
        platform = rec.get("platform")
        if platform_filter and platform != platform_filter:
            continue
        song_name = rec.get("song_name") or "(제목없음)"
        date = rec.get("date")
        value = rec.get(metric_key)
        if date is None:
            continue
        if value is None:
            continue
        key = f"{platform}::{song_name}"
        agg[key][date] += float(value)

    return agg


def _plot_metric_by_song(
    agg: Dict[str, Dict[str, float]],
    metric_label: str,
    output_dir: Path,
    platform: Optional[str] = None,
):
    """곡별로 날짜-메트릭 선 그래프를 그려 PNG로 저장한다."""
    if not agg:
        logger.warning(f"{metric_label}에 대한 집계 데이터가 없습니다.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # 플랫폼별로 파일 나누기
    per_platform: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(dict)
    for key, date_map in agg.items():
        plat, song = key.split("::", 1)
        per_platform[plat][song] = date_map

    for plat, songs in per_platform.items():
        if platform and plat != platform:
            continue

        plt.figure(figsize=(10, 6))
        for song_name, date_map in sorted(songs.items()):
            dates = sorted(date_map.keys())
            values = [date_map[d] for d in dates]
            plt.plot(dates, values, marker="o", label=song_name)

        plt.title(f"{plat} - {metric_label} (곡별)")
        plt.xlabel("날짜 (YYYY-MM-DD)")
        plt.ylabel(metric_label)
        plt.xticks(rotation=45, ha="right")
        plt.legend(fontsize=8)
        plt.tight_layout()

        out_path = output_dir / f"{plat}_{metric_label}.png"
        plt.savefig(out_path)
        plt.close()
        logger.info(f"차트 저장 완료: {out_path}")


def analyze_logs(config_path: str, platform: Optional[str] = None):
    """JSON 로그를 읽어 날짜/플랫폼/곡별 차트를 생성한다."""
    # Matplotlib 한글 폰트 설정 (한 번만 수행)
    _setup_matplotlib_font()

    config = load_config(config_path)
    log_config = config.get("log", {})
    base_dir = Path(log_config.get("base_dir", "data/logs"))
    output_dir = Path("data/charts")

    records = _load_logs(base_dir)
    if not records:
        return

    # total_plays 차트
    plays_agg = _aggregate_by_song(records, "total_plays", platform_filter=platform)
    _plot_metric_by_song(plays_agg, "total_plays", output_dir, platform=platform)

    # total_listeners 차트 (값이 있는 경우에만)
    listeners_agg = _aggregate_by_song(records, "total_listeners", platform_filter=platform)
    # 값이 전부 0/없으면 스킵
    if any(v > 0 for song in listeners_agg.values() for v in song.values()):
        _plot_metric_by_song(listeners_agg, "total_listeners", output_dir, platform=platform)


def main():
    """CLI 엔트리포인트: JSON 로그 기반 차트 생성."""
    parser = argparse.ArgumentParser(description="data/logs/ JSONL 로그로부터 플랫폼/곡별 차트 생성")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="설정 파일 경로 (기본값: config.yaml)",
    )
    parser.add_argument(
        "--platform",
        default=None,
        help="특정 플랫폼만 분석 (예: GENIE). 생략 시 전체 플랫폼 분석.",
    )
    args = parser.parse_args()

    analyze_logs(args.config, platform=args.platform)


if __name__ == "__main__":
    main()


