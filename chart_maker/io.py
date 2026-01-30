"""JSONL 로더/세이버 및 요약 CSV 저장."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .utils import ensure_dir

logger = logging.getLogger(__name__)


def load_jsonl(path: Path) -> pd.DataFrame:
    """JSONL 파일을 읽어서 pandas DataFrame으로 반환한다.
    
    디렉토리를 입력받으면 재귀적으로 모든 하위 디렉토리의 *.jsonl 파일을 로드합니다.
    """
    records: List[dict] = []

    if path.is_dir():
        # 디렉토리인 경우 재귀적으로 모든 하위 디렉토리의 *.jsonl 파일 로드
        files = sorted(path.rglob("*.jsonl"))
        logger.info("디렉토리에서 %d개의 JSONL 파일을 찾았습니다: %s", len(files), path)
    else:
        files = [path]

    if not files:
        logger.warning(f"JSONL 파일을 찾을 수 없습니다: {path}")
        return pd.DataFrame()

    for f in files:
        try:
            with f.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning("JSONL 파싱 실패 (%s): %s", f, e)
        except Exception as e:
            logger.error("JSONL 파일 읽기 실패 (%s): %s", f, e)

    if not records:
        logger.warning("JSONL에서 로드된 레코드가 없습니다.")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    logger.info("총 %d개의 레코드를 로드했습니다.", len(df))
    return df


def save_summary_csv(df_summary: pd.DataFrame, out_dir: Path) -> None:
    """플랫폼별 요약 정보를 CSV로 저장한다."""
    if df_summary.empty:
        logger.warning("요약 정보가 비어 있어 CSV를 생성하지 않습니다.")
        return

    out_dir = ensure_dir(out_dir)
    for platform, df_plat in df_summary.groupby("platform"):
        out_path = out_dir / f"{platform}_summary.csv"
        df_plat.to_csv(out_path, index=False, encoding="utf-8-sig")
        logger.info("요약 CSV 저장 완료: %s", out_path)



