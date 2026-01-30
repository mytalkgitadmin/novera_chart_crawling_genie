# Chart Maker

음원 플랫폼 지표 데이터를 시각화하는 차트 생성 도구입니다. JSONL 로그 파일을 읽어서 차트(PNG), 리포트(HTML), 요약 테이블(CSV)을 자동으로 생성합니다.

## 주요 기능

- **시계열 차트 생성**: 곡별 재생수/청취자수 변화를 시각화
- **델타 차트**: 시간당 증가량 분석
- **플랫폼 요약**: Top N 곡 비교 차트
- **HTML 리포트**: 인터랙티브 Plotly 차트가 포함된 상세 리포트
- **요약 CSV**: 곡별 통계 데이터 (순증가량, 평균 증가율 등)

## 출력 형식

### 1. PNG 차트 (matplotlib)

- `{플랫폼}_{곡ID}_totals.png`: 누적 재생수/청취자수 시계열
- `{플랫폼}_{곡ID}_delta.png`: 시간당 증가량 시계열
- `{플랫폼}_top{N}_totals.png`: 상위 N곡 누적값 비교
- `{플랫폼}_top{N}_delta.png`: 상위 N곡 증가량 비교

### 2. HTML 리포트 (plotly)

- `{플랫폼}_{곡ID}_report.html`: 곡별 상세 리포트
  - 인터랙티브 차트 (줌, 팬, 호버 정보)
  - 곡 정보 및 통계 요약
  - 이상치 감지 결과

### 3. CSV 요약

- `{플랫폼}_summary.csv`: 플랫폼별 곡 통계
  - 순증가량 (net_plays, net_listeners)
  - 평균 증가율 (avg_rate_plays_per_min, avg_rate_listeners_per_min)
  - 데이터 포인트 수, 이상치 개수

## 설치

chart_maker는 music_metrics_collector와 동일한 가상환경을 사용합니다.

```bash
# 가상환경 활성화 (이미 설치되어 있다면 생략)
source venv/bin/activate

# 의존성 설치 (requirements.txt에 포함됨)
pip install -r requirements.txt
```

## 사용법

### 기본 사용법

```bash
# 전체 로그 디렉토리에서 차트 생성
python -m chart_maker.main render \
    --input data/logs \
    --outdir output
```

### 플랫폼 필터링

```bash
# GENIE 플랫폼만 처리
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --platform GENIE
```

### 특정 곡만 처리

```bash
# 특정 곡(song_id)만 차트 생성
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --platform GENIE \
    --song-id 87264570
```

### Top N 설정

```bash
# 상위 20곡 요약 차트 생성
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --platform GENIE \
    --topn 20
```

### 출력 형식 선택

```bash
# PNG만 생성 (HTML 비활성화)
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --no-export-html

# HTML만 생성 (PNG 비활성화)
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --no-export-png
```

### 특정 파일만 처리

```bash
# 단일 JSONL 파일 처리
python -m chart_maker.main render \
    --input data/logs/2026-01-14_GENIE.jsonl \
    --outdir output
```

## 명령어 옵션

### `render` 명령어

| 옵션               | 필수 | 기본값   | 설명                                    |
| ------------------ | ---- | -------- | --------------------------------------- |
| `--input`          | ✓    | -        | 입력 JSONL 파일 또는 디렉토리 경로      |
| `--outdir`         |      | `output` | 출력 루트 디렉토리                      |
| `--platform`       |      | 전체     | 특정 플랫폼만 필터 (GENIE, BUGS, MELON) |
| `--song-id`        |      | 전체     | 특정 곡(song_id)만 필터                 |
| `--topn`           |      | `10`     | 플랫폼 요약 차트에서 상위 N곡           |
| `--export-html`    |      | `true`   | HTML 리포트 생성 여부                   |
| `--no-export-html` |      | -        | HTML 리포트 생성 비활성화               |
| `--export-png`     |      | `true`   | PNG 차트 생성 여부                      |
| `--no-export-png`  |      | -        | PNG 차트 생성 비활성화                  |

## 출력 디렉토리 구조

```
output/
├── png/                    # matplotlib PNG 차트
│   ├── GENIE_87264570_totals.png
│   ├── GENIE_87264570_delta.png
│   ├── GENIE_top10_totals.png
│   └── GENIE_top10_delta.png
├── reports/                # plotly HTML 리포트
│   ├── GENIE_87264570_report.html
│   └── GENIE_87118757_report.html
└── csv/                    # 요약 CSV
    ├── GENIE_summary.csv
    ├── BUGS_summary.csv
    └── MELON_summary.csv
```

## 입력 데이터 형식

JSONL(JSON Lines) 형식의 로그 파일을 입력으로 받습니다. 각 줄은 하나의 JSON 객체입니다.

### 필수 필드

```json
{
  "platform": "GENIE",
  "song_id": "87264570",
  "song_name": "곡 제목",
  "artist_name": "아티스트명",
  "date": "2026-01-14",
  "hour": 11,
  "minute": 26,
  "total_plays": 1234567,
  "total_listeners": 123456
}
```

### 선택 필드

- `album_name`: 앨범명
- `song_type`: 장르
- `track_code`: 트랙 코드
- `isrc`: ISRC 코드

## 데이터 처리 과정

1. **로드**: JSONL 파일(들)을 pandas DataFrame으로 로드
2. **정규화**:
   - 타임스탬프 생성 (`date` + `hour` + `minute`)
   - 중복 데이터 제거 (같은 시간에 여러 수집 시 최신 값 유지)
3. **파생 지표 계산**:
   - `delta_plays`: 이전 시점 대비 재생수 증가량
   - `delta_listeners`: 이전 시점 대비 청취자수 증가량
   - `rate_plays_per_min`: 분당 재생수 증가율
   - `rate_listeners_per_min`: 분당 청취자수 증가율
4. **이상치 감지**: 음수 증가량 감지 (데이터 오류 가능성)
5. **차트 생성**: 곡별/플랫폼별 차트 및 리포트 생성

## 이상치 처리

음수 증가량이 감지되면:

- 로그에 경고 메시지 출력
- 요약 테이블에 `num_anomalies` 컬럼에 기록
- HTML 리포트에서 해당 데이터 포인트 표시

음수 증가량이 발생하는 경우:

- 플랫폼에서 데이터 수정/삭제
- 수집 시간 순서가 뒤바뀜
- 네트워크 오류로 인한 잘못된 데이터

## 예제

### 1. 전체 플랫폼 차트 생성

```bash
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --topn 10
```

**결과:**

- 모든 플랫폼의 모든 곡 차트 생성
- 플랫폼별 상위 10곡 요약 차트
- 곡별 HTML 리포트
- 플랫폼별 요약 CSV

### 2. GENIE 플랫폼 Top 20 분석

```bash
python -m chart_maker.main render \
    --input data/logs \
    --outdir output/genie_analysis \
    --platform GENIE \
    --topn 20
```

**결과:**

- GENIE 플랫폼만 필터링
- 상위 20곡 요약 차트
- 출력: `output/genie_analysis/`

### 3. 특정 곡 상세 분석

```bash
python -m chart_maker.main render \
    --input data/logs/2026-01-14_GENIE.jsonl \
    --outdir output/song_analysis \
    --platform GENIE \
    --song-id 87264570
```

**결과:**

- 단일 곡만 분석
- 해당 곡의 차트와 리포트만 생성

### 4. 빠른 CSV 요약만 생성

```bash
python -m chart_maker.main render \
    --input data/logs \
    --outdir output \
    --no-export-html \
    --no-export-png
```

**결과:**

- 차트/리포트 생성 없이 CSV 요약만 생성
- 빠른 통계 확인용

## 문제 해결

### 1. 데이터가 비어있다는 오류

```
ERROR: 입력 데이터가 비어 있습니다. 종료합니다.
```

**원인:**

- JSONL 파일이 비어있음
- 잘못된 경로 지정

**해결:**

```bash
# 파일 확인
ls -la data/logs/
cat data/logs/2026-01-14_GENIE.jsonl
```

### 2. 필터링 후 데이터 없음

```
ERROR: 필터링 후 데이터가 없습니다. 종료합니다.
```

**원인:**

- `--platform` 또는 `--song-id` 필터가 데이터와 맞지 않음

**해결:**

```bash
# 필터 없이 실행해서 데이터 확인
python -m chart_maker.main render --input data/logs --outdir output

# CSV 요약에서 사용 가능한 platform/song_id 확인
cat output/csv/GENIE_summary.csv
```

### 3. 한글 깨짐

**원인:**

- 시스템 인코딩 문제

**해결:**

```bash
# 환경 변수 설정
export LANG=ko_KR.UTF-8
export LC_ALL=ko_KR.UTF-8
```

## 고급 사용법

### 여러 날짜 데이터 통합 분석

```bash
# data/logs/ 디렉토리의 모든 JSONL 파일 자동 로드
python -m chart_maker.main render \
    --input data/logs \
    --outdir output/monthly_report \
    --platform GENIE \
    --topn 30
```

### 배치 처리 스크립트

```bash
#!/bin/bash
# 플랫폼별로 개별 분석

for platform in GENIE BUGS MELON; do
    echo "Processing $platform..."
    python -m chart_maker.main render \
        --input data/logs \
        --outdir "output/${platform}_report" \
        --platform "$platform" \
        --topn 20
done
```

## 관련 문서

- [Music Metrics Collector README](../README.md): 데이터 수집 도구
- [config.yaml 설정 가이드](../README.md#설정-파일-구성): 수집 설정

## 라이선스

이 프로젝트는 Music Metrics Collector의 일부입니다.
