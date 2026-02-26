"""음원 메트릭 수집기 - CLI 엔트리포인트."""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from .factory import CollectorFactory
from .fetcher import Fetcher
from .models import TrackInfo, MetricsResult
from .utils import get_seoul_date, get_current_hour, get_current_minute
from .scheduler import Scheduler

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """YAML 설정 파일을 로드한다."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_songs_from_csv(platform: str, resource_dir: str = "resource") -> List[Dict[str, str]]:
    """
    CSV 파일에서 곡 정보를 로드한다.
    새로운 명세의 17개 컬럼 구조를 지원한다.

    Args:
        platform: 플랫폼 이름 (GENIE)
        resource_dir: 리소스 디렉토리 경로

    Returns:
        'song_id', 'track_code', 'isrc_cd' 키를 가진 딕셔너리 리스트
    """
    import json
    
    csv_path = Path(resource_dir) / platform / "song_data.csv"
    
    if not csv_path.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return []
    
    songs = []
    try:
        # utf-8-sig를 사용하여 BOM(Byte Order Mark)을 자동으로 제거
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # BOM이 남아있을 수 있으므로 컬럼명에서도 제거
            reader.fieldnames = [name.strip('\ufeff') if name else name for name in (reader.fieldnames or [])]
            for row in reader:
                # BOM이 포함된 키도 처리
                row_cleaned = {}
                for key, value in row.items():
                    cleaned_key = key.strip('\ufeff') if key else key
                    row_cleaned[cleaned_key] = value
                
                # 새로운 컬럼 구조 지원
                track_cd = row_cleaned.get('track_cd', '').strip()
                isrc_cd = row_cleaned.get('isrc_cd', '').strip()
                
                # platform_song_ids에서 해당 플랫폼의 song_id 추출
                platform_song_ids_str = row_cleaned.get('platform_song_ids', '{}').strip()
                song_id = ''
                try:
                    platform_song_ids = json.loads(platform_song_ids_str)
                    song_id = platform_song_ids.get(platform.upper(), '')
                except (json.JSONDecodeError, AttributeError):
                    # JSON 파싱 실패 시 빈 문자열
                    logger.warning(f"Failed to parse platform_song_ids for track_cd={track_cd}: {platform_song_ids_str}")
                
                if song_id:
                    # 20개 컬럼 전체 포함 (song_data.csv 명세 준수)
                    songs.append({
                        # 플랫폼 song_id (platform_song_ids JSON에서 추출)
                        'song_id': song_id,
                        
                        # song_data.csv의 20개 컬럼 전체
                        'platform_seq': row_cleaned.get('platform_seq', '').strip(),
                        'platform_name': row_cleaned.get('platform_name', '').strip(),
                        'song_type_txt': row_cleaned.get('song_type_txt', '').strip(),
                        'album_cd': row_cleaned.get('album_cd', '').strip(),
                        'album_name_kor': row_cleaned.get('album_name_kor', '').strip(),
                        'album_name_eng': row_cleaned.get('album_name_eng', '').strip(),
                        'song_cd': row_cleaned.get('song_cd', '').strip(),
                        'song_name_kor': row_cleaned.get('song_name_kor', '').strip(),
                        'song_name_eng': row_cleaned.get('song_name_eng', '').strip(),
                        'song_release_date': row_cleaned.get('song_release_date', '').strip(),
                        'artist_cd': row_cleaned.get('artist_cd', '').strip(),
                        'artist_name_kor': row_cleaned.get('artist_name_kor', '').strip(),
                        'artist_name_eng': row_cleaned.get('artist_name_eng', '').strip(),
                        'mem_cd': row_cleaned.get('mem_cd', '').strip(),
                        'mem_name': row_cleaned.get('mem_name', '').strip(),
                        'track_cd': track_cd,
                        'isrc_cd': isrc_cd,
                        'interest_yn': row_cleaned.get('interest_yn', 'n').strip(),
                        'platform_artist_ids': row_cleaned.get('platform_artist_ids', '').strip(),
                        'platform_song_ids': row_cleaned.get('platform_song_ids', '{}').strip(),
                        # 새로 추가된 b2b / new_date 필드
                        'b2b_artist_cd_spotify': row_cleaned.get('b2b_artist_cd_spotify', '').strip(),
                        'b2b_artist_cd_apple': row_cleaned.get('b2b_artist_cd_apple', '').strip(),
                        'b2b_artist_cd_melon': row_cleaned.get('b2b_artist_cd_melon', '').strip(),
                        'b2b_asset_ids_youtube': row_cleaned.get('b2b_asset_ids_youtube', '').strip(),
                        'new_date': row_cleaned.get('new_date', '').strip(),
                        
                        # 호환성 필드 (기존 코드 호환용)
                        'track_code': track_cd,
                        'isrc': isrc_cd,
                    })
        
        logger.info(f"Loaded {len(songs)} songs from {csv_path}")
        return songs
    except Exception as e:
        logger.error(f"Failed to load songs from {csv_path}: {e}")
        return []


def build_targets_from_config(config: dict) -> List[Dict]:
    """
    설정을 기반으로 수집 대상(target) 리스트를 구성한다.

    - 플랫폼 설정에 `resource_csv: true` 가 있으면 CSV에서 곡 목록을 읽어온다.
    - 그렇지 않으면 레거시 형식(`targets`)을 그대로 사용한다.

    Args:
        config: 설정 딕셔너리

    Returns:
        수집 대상 딕셔너리 리스트
    """
    targets = []
    
    # 새 형식(platforms)이 있는지 확인
    platforms_config = config.get('platforms', {})
    
    if platforms_config:
        # 새 형식: 플랫폼별 metrics 설정 + CSV에서 곡 목록 로드
        for platform_name, platform_config in platforms_config.items():
            platform = platform_name.upper()
            metrics = platform_config.get('metrics')
            use_csv = platform_config.get('resource_csv', False)
            
            if use_csv:
                # CSV에서 곡 목록 로드
                resource_dir = config.get('resource_dir', 'resource')
                songs = load_songs_from_csv(platform, resource_dir)
                
                for song in songs:
                    # song_data.csv의 모든 필드를 target에 포함
                    targets.append({
                        'platform': platform,
                        'song_id': song['song_id'],
                        'metrics': metrics,
                        # song_data.csv의 17개 컬럼 전체
                        'song_data': song  # 전체 데이터를 포함
                    })
            else:
                # 레거시 형식: config 안의 songs 리스트 사용
                songs = platform_config.get('songs', [])
                for song in songs:
                    targets.append({
                        'platform': platform,
                        'song_id': song.get('song_id'),
                        'alias': song.get('alias'),
                        'metrics': metrics
                    })
    else:
        # 레거시 형식: 개별 targets 사용
        targets = config.get('targets', [])
    
    return targets


def collect_metrics(config: dict) -> Dict[str, int]:
    """
    설정된 모든 대상에 대해 메트릭을 수집하고 JSON 로그에 기록한다.

    Returns:
        통계 요약 딕셔너리
    """
    enabled_platforms = set(config.get('enabled_platforms', []))
    
    # 설정으로부터 타깃 목록 생성 (CSV/레거시 형식 모두 지원)
    targets = build_targets_from_config(config)
    
    mode = config.get('mode', 'auto')
    timeout = config.get('http', {}).get('timeout_sec', 20)
    
    fetcher = Fetcher(mode=mode, timeout_sec=timeout)
    
    # JSON 로그 파일 기본 디렉토리 (날짜/플랫폼별 파일 생성)
    log_config = config.get('log', {})
    log_base_dir = log_config.get('base_dir', 'data/logs')
    Path(log_base_dir).mkdir(parents=True, exist_ok=True)
    
    stats = {
        'total': len(targets),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'platform_stats': {}
    }
    
    today = get_seoul_date()
    current_hour = get_current_hour()
    current_minute = get_current_minute()
    
    try:
        for target in targets:
            platform = target['platform'].upper()
            song_id = target['song_id']
            song_data = target.get('song_data', {})  # song_data.csv의 전체 데이터
            requested_metrics = target.get('metrics')  # 선택: 지표 이름 → JS 선택자 딕셔너리 또는 지표 이름 리스트
            
            # 호환성을 위해 일부 필드 추출
            track_code = song_data.get('track_cd', '')
            isrc = song_data.get('isrc_cd', '')
            song_type = song_data.get('song_type', '')
            
            # 플랫폼별 song_name / artist_name / album_name 선택자 읽기
            platforms_config = config.get('platforms', {})
            platform_config = platforms_config.get(platform, {})
            song_name_selector = platform_config.get('song_name')
            artist_name_selector = platform_config.get('artist_name')
            album_name_selector = platform_config.get('album_name')
            
            # 플랫폼 사용 여부 확인
            if platform not in enabled_platforms:
                logger.warning(f"Skipping {platform}:{song_id} - platform not enabled")
                stats['skipped'] += 1
                continue
            
            # Collector가 지원하는 플랫폼인지 확인
            if not CollectorFactory.is_supported(platform):
                logger.warning(f"Skipping {platform}:{song_id} - platform not supported")
                stats['skipped'] += 1
                continue
            
            # metrics 설정이 있으면 지원 여부 검증
            if requested_metrics:
                collector_class = CollectorFactory._collectors.get(platform)
                if collector_class:
                    supported = collector_class.SUPPORTED_METRICS
                    # 딕셔너리(선택자 포함)와 리스트(레거시 형식) 모두 지원
                    if isinstance(requested_metrics, dict):
                        metric_names = list(requested_metrics.keys())
                    elif isinstance(requested_metrics, list):
                        metric_names = requested_metrics
                    else:
                        logger.warning(f"Invalid metrics format for {platform}:{song_id}. Expected dict or list.")
                        requested_metrics = None
                        metric_names = []
                    
                    if metric_names:
                        invalid = [m for m in metric_names if m not in supported]
                        if invalid:
                            logger.warning(
                                f"Unsupported metrics for {platform}: {invalid}. "
                                f"Supported: {supported}. Will collect all supported metrics."
                            )
                            requested_metrics = None  # 지원하지 않는 값이 있으면 해당 플랫폼의 모든 지원 지표를 수집
            
            track_info = TrackInfo(
                platform=platform,
                song_id=song_id,
                alias=None,  # 현재는 사용하지 않음
                requested_metrics=requested_metrics
            )
            
            # 플랫폼별 통계 초기화
            if platform not in stats['platform_stats']:
                stats['platform_stats'][platform] = {'success': 0, 'failed': 0}
            

            # 날짜_플랫폼명.jsonl 형식의 JSON 로그 파일 경로 구성
            Path(log_base_dir).mkdir(parents=True, exist_ok=True)
            log_file_path = Path(log_base_dir) / f"{today}_{platform}.jsonl"

            try:
                # Collector 생성
                collector = CollectorFactory.create(platform, fetcher)
                
                # 메트릭과 곡 제목/아티스트명/앨범명 수집
                metrics_result, song_name, artist_name, album_name = collector.collect(
                    track_info,
                    song_name_selector=song_name_selector,
                    artist_name_selector=artist_name_selector,
                    album_name_selector=album_name_selector,
                )
                
                # auto 모드에서 메트릭이 비어 있으면 playwright로 재시도
                if mode == 'auto' and metrics_result.is_empty():
                    logger.warning(f"Metrics empty for {platform}:{song_id}, trying playwright fallback...")
                    playwright_fetcher = Fetcher(mode='playwright', timeout_sec=timeout)
                    playwright_collector = CollectorFactory.create(platform, playwright_fetcher)
                    metrics_result, song_name, artist_name, album_name = playwright_collector.collect(
                        track_info,
                        song_name_selector=song_name_selector,
                        artist_name_selector=artist_name_selector,
                        album_name_selector=album_name_selector,
                    )
                    playwright_fetcher.close()
                

                # JSON 로그 파일에 쓰기 (song_data.csv 전체 필드 + 수집 결과)
                log_entry = {
                    # song_data.csv의 20개 컬럼 전체
                    'platform_seq': song_data.get('platform_seq', ''),
                    'platform_name': song_data.get('platform_name', ''),
                    'song_type_txt': song_data.get('song_type_txt', ''),
                    'album_cd': song_data.get('album_cd', ''),
                    'album_name_kor': song_data.get('album_name_kor', ''),
                    'album_name_eng': song_data.get('album_name_eng', ''),
                    'song_cd': song_data.get('song_cd', ''),
                    'song_name_kor': song_data.get('song_name_kor', ''),
                    'song_name_eng': song_data.get('song_name_eng', ''),
                    'song_release_date': song_data.get('song_release_date', ''),
                    'artist_cd': song_data.get('artist_cd', ''),
                    'artist_name_kor': song_data.get('artist_name_kor', ''),
                    'artist_name_eng': song_data.get('artist_name_eng', ''),
                    'mem_cd': song_data.get('mem_cd', ''),
                    'mem_name': song_data.get('mem_name', ''),
                    'track_cd': song_data.get('track_cd', ''),
                    'isrc_cd': song_data.get('isrc_cd', ''),
                    'interest_yn': song_data.get('interest_yn', 'n'),
                    'platform_artist_ids': song_data.get('platform_artist_ids', ''),
                    'platform_song_ids': song_id,  # JSON 문자열이 아닌 song_id 값만
                    # 새로 추가된 b2b / new_date 필드
                    'b2b_artist_cd_spotify': song_data.get('b2b_artist_cd_spotify', ''),
                    'b2b_artist_cd_apple': song_data.get('b2b_artist_cd_apple', ''),
                    'b2b_artist_cd_melon': song_data.get('b2b_artist_cd_melon', ''),
                    'b2b_asset_ids_youtube': song_data.get('b2b_asset_ids_youtube', ''),
                    'new_date': song_data.get('new_date', ''),
                    
                    # 수집 결과 필드
                    'req_date': today,  # 데이터 수집일
                    'res_listeners': metrics_result.total_listeners,  # 전체 감상수
                    
                    # 국가별 (GENIE는 국내 플랫폼이므로 한국 100%, 나머지 null)
                    'res_listeners_ko': metrics_result.total_listeners if platform == 'GENIE' else None,
                    'res_listeners_jp': None,
                    'res_listeners_cn': None,
                    'res_listeners_us': None,
                    'res_listeners_eu': None,
                    'res_listeners_ea': None,
                    'res_listeners_etc': None,
                    
                    # 성별 비율 (확장 예정)
                    'res_sex_m_rate': getattr(metrics_result, 'sex_m_rate', None),
                    'res_sex_w_rate': getattr(metrics_result, 'sex_w_rate', None),
                    
                    # 연령별 비율 (확장 예정)
                    'res_age_10_rate': getattr(metrics_result, 'age_10_rate', None),
                    'res_age_20_rate': getattr(metrics_result, 'age_20_rate', None),
                    'res_age_30_rate': getattr(metrics_result, 'age_30_rate', None),
                    'res_age_40_rate': getattr(metrics_result, 'age_40_rate', None),
                    'res_age_50_rate': getattr(metrics_result, 'age_50_rate', None),
                    'res_age_60_rate': getattr(metrics_result, 'age_60_rate', None),
                    
                    # 기타 예비 필드
                    'etc0': None,
                    'etc1': None,
                }
                
                # 기존 저장
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

                # 추가 저장 (crawler-share)
                share_dir = Path(f"~/project/crawler-share/genie/date={today.replace('-', '')}").expanduser()
                share_dir.mkdir(parents=True, exist_ok=True)
                share_file_path = share_dir / f"{today}_{platform}.jsonl"
                with open(share_file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
                stats['success'] += 1
                stats['platform_stats'][platform]['success'] += 1
                logger.info(f"✓ Successfully collected {platform}:{song_id} (song: {song_name})")
                
            except Exception as e:
                logger.error(f"✗ Failed to collect {platform}:{song_id}: {e}")
                
                # 실패한 항목도 JSON 로그 파일에 기록
                log_entry = {
                    # song_data.csv의 20개 컬럼 전체
                    'platform_seq': song_data.get('platform_seq', ''),
                    'platform_name': song_data.get('platform_name', ''),
                    'song_type_txt': song_data.get('song_type_txt', ''),
                    'album_cd': song_data.get('album_cd', ''),
                    'album_name_kor': song_data.get('album_name_kor', ''),
                    'album_name_eng': song_data.get('album_name_eng', ''),
                    'song_cd': song_data.get('song_cd', ''),
                    'song_name_kor': song_data.get('song_name_kor', ''),
                    'song_name_eng': song_data.get('song_name_eng', ''),
                    'song_release_date': song_data.get('song_release_date', ''),
                    'artist_cd': song_data.get('artist_cd', ''),
                    'artist_name_kor': song_data.get('artist_name_kor', ''),
                    'artist_name_eng': song_data.get('artist_name_eng', ''),
                    'mem_cd': song_data.get('mem_cd', ''),
                    'mem_name': song_data.get('mem_name', ''),
                    'track_cd': song_data.get('track_cd', ''),
                    'isrc_cd': song_data.get('isrc_cd', ''),
                    'interest_yn': song_data.get('interest_yn', 'n'),
                    'platform_artist_ids': song_data.get('platform_artist_ids', ''),
                    'platform_song_ids': song_id,  # JSON 문자열이 아닌 song_id 값만
                    # 새로 추가된 b2b / new_date 필드
                    'b2b_artist_cd_spotify': song_data.get('b2b_artist_cd_spotify', ''),
                    'b2b_artist_cd_apple': song_data.get('b2b_artist_cd_apple', ''),
                    'b2b_artist_cd_melon': song_data.get('b2b_artist_cd_melon', ''),
                    'b2b_asset_ids_youtube': song_data.get('b2b_asset_ids_youtube', ''),
                    'new_date': song_data.get('new_date', ''),
                    
                    # 수집 결과 필드 (모두 null)
                    'req_date': today,
                    'res_listeners': None,
                    'res_listeners_ko': None,
                    'res_listeners_jp': None,
                    'res_listeners_cn': None,
                    'res_listeners_us': None,
                    'res_listeners_eu': None,
                    'res_listeners_ea': None,
                    'res_listeners_etc': None,
                    'res_sex_m_rate': None,
                    'res_sex_w_rate': None,
                    'res_age_10_rate': None,
                    'res_age_20_rate': None,
                    'res_age_30_rate': None,
                    'res_age_40_rate': None,
                    'res_age_50_rate': None,
                    'res_age_60_rate': None,
                    'etc0': None,
                    'etc1': None,
                    'error': str(e)
                }
                
                # 기존 저장
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

                # 추가 저장 (crawler-share)
                share_dir = Path(f"~/project/crawler-share/genie/date={today.replace('-', '')}").expanduser()
                share_dir.mkdir(parents=True, exist_ok=True)
                share_file_path = share_dir / f"{today}_{platform}.jsonl"
                with open(share_file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
                stats['failed'] += 1
                stats['platform_stats'][platform]['failed'] += 1
                
    finally:
        fetcher.close()
    
    logger.info(f"Metrics logged under {log_base_dir} (format: YYYY-MM-DD_PLATFORM.jsonl)")
    
    return stats


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description='Music Metrics Collector')
    parser.add_argument('command', choices=['collect', 'run-scheduler'], 
                       help='Command to execute')
    parser.add_argument('--config', default='config.yaml', 
                       help='Path to config file (default: config.yaml)')
    
    args = parser.parse_args()
    
    # Load config
    if not Path(args.config).exists():
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
    
    config = load_config(args.config)
    
    if args.command == 'collect':
        # One-time collection
        start_time = time.time()
        logger.info("Starting metric collection...")
        
        stats = collect_metrics(config)
        
        elapsed = time.time() - start_time
        
        # Print summary
        print("\n" + "="*50)
        print("Collection Summary")
        print("="*50)
        print(f"Total targets: {stats['total']}")
        print(f"Success: {stats['success']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped: {stats['skipped']}")
        print("\nPlatform breakdown:")
        for platform, platform_stats in stats['platform_stats'].items():
            print(f"  {platform}: ✓{platform_stats['success']} ✗{platform_stats['failed']}")
        print(f"\nElapsed time: {elapsed:.2f}s")
        print("="*50)
        
    elif args.command == 'run-scheduler':
        # Run scheduler
        scheduler = Scheduler(config)
        scheduler.start()
        try:
            print("Scheduler started. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping scheduler...")
            scheduler.stop()


if __name__ == '__main__':
    main()

