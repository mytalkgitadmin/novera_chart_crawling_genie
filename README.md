# GENIE Music Metrics Collector

GENIE 음원 플랫폼에서 곡별 감상수를 수집하여 JSONL 형식으로 저장하는 시스템입니다.

---

## 환경 설정

```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

---

## 데이터 파이프라인

```
search_data.csv (18개 컬럼)
  ↓ [1단계: song_id 검색]
song_data.csv (20개 컬럼)
  ↓ [2단계: 메트릭 수집]
{날짜}_GENIE.jsonl
  ↓ [3단계: 스케줄러로 매일 자동 수집]
시계열 데이터 축적
```

---

## 1단계: search_data.csv 준비

`resource/GENIE/search_data.csv` 파일을 생성합니다.

### 필수 컬럼 (18개)

| 컬럼명 | 설명 |
|--------|------|
| platform_seq | 플랫폼 시퀀스 (80) |
| platform_name | 플랫폼명 (지니뮤직) |
| song_type_text | 음원 타입 (대중음악/OST) |
| album_cd | 앨범 코드 |
| album_name_kor | 앨범명 (한글) |
| album_name_eng | 앨범명 (영문) |
| song_cd | 곡 코드 |
| song_name_kor | 곡명 (한글) - **검색에 사용** |
| song_name_eng | 곡명 (영문) |
| song_release_date | 발매일 |
| artist_cd | 아티스트 코드 |
| artist_name_kor | 아티스트명 (한글) - **검색에 사용** |
| artist_name_eng | 아티스트명 (영문) |
| mem_cd | 권리사 코드 |
| mem_name | 권리사명 |
| track_cd | 트랙 코드 (중복 제거용) |
| isrc_cd | ISRC 코드 |
| interest_yn | 관심 여부 (Y/N) |

### 예시

```csv
platform_seq,platform_name,song_type_text,album_cd,album_name_kor,album_name_eng,song_cd,song_name_kor,song_name_eng,song_release_date,artist_cd,artist_name_kor,artist_name_eng,mem_cd,mem_name,track_cd,isrc_cd,interest_yn
80,지니뮤직,대중음악,A1000001,Fun'ch,Fun'ch,A1000001T005,못된 여자,Bad Girl,39603,S123981,원투 (One Two),One Two,L20220049,바론 엔터,A1000001T005,QZEKE1873038,Y
```

---

## 2단계: song_data.csv 생성

GENIE에서 각 곡의 song_id를 검색하여 `song_data.csv`를 생성합니다.

```bash
python -m music_metrics_collector.generate_song_ids --config config.yaml
```

### 동작 방식

1. `search_data.csv`의 곡명/아티스트명으로 GENIE 검색
2. 7단계 Fallback 검색으로 98%+ 성공률 달성
3. `song_data.csv` 생성 (20개 컬럼)

### 7단계 Fallback 검색

1. 원본 검색: 곡명 + 아티스트명 + 앨범명
2. 전처리: OST/Part/Vol 키워드 제거
3. 앨범명 제외: 곡명 + 아티스트명만
4. 특수기호 제거: 한글/영문/숫자만
5. 괄호 제거: "정키 (정희웅)" → "정키"
6. 곡명만 검색
7. 곡명만 + 특수기호 제거

### 출력 파일

`resource/GENIE/song_data.csv` (20개 컬럼)
- 기존 18개 컬럼 + `platform_artist_ids` + `platform_song_ids`

```csv
...,platform_artist_ids,platform_song_ids
...,{},"{""GENIE"": ""59950541""}"
```

---

## 3단계: JSONL 생성 (1회 수집)

각 곡의 GENIE 페이지에서 감상수를 수집합니다.

```bash
python -m music_metrics_collector.main collect --config config.yaml
```

### 동작 방식

1. `song_data.csv`에서 song_id 추출
2. GENIE 곡 상세 페이지 접속 (`https://www.genie.co.kr/detail/songInfo?xgnm={song_id}`)
3. 전체 감상수(total_listeners) 수집
4. JSONL 파일 저장

### 출력 파일

`data/logs/{YYYY-MM-DD}_GENIE.jsonl`

각 라인은 하나의 곡 데이터 (JSON 형식):

```json
{
  "platform_seq": "80",
  "platform_name": "지니뮤직",
  "song_name_kor": "못된 여자",
  "artist_name_kor": "원투 (One Two)",
  "track_cd": "A1000001T005",
  "isrc_cd": "QZEKE1873038",
  "platform_song_ids": "59950541",
  "req_date": "2026-01-27",
  "res_listeners": 12345,
  "res_listeners_ko": 12345
}
```

### JSONL 필드 구조

**song_data.csv 기반 (20개)**
- 기본 정보: platform_seq, platform_name, song_type_txt, album_cd, album_name_kor/eng
- 곡 정보: song_cd, song_name_kor/eng, song_release_date
- 아티스트: artist_cd, artist_name_kor/eng
- 권리사: mem_cd, mem_name
- 식별자: track_cd, isrc_cd, interest_yn, platform_artist_ids, platform_song_ids

**수집 결과 (19개)**
- req_date: 수집일
- res_listeners: 전체 감상수
- res_listeners_ko/jp/cn/us/eu/ea/etc: 국가별 감상수 (GENIE는 ko만 사용)
- res_sex_m_rate, res_sex_w_rate: 성별 비율 (null)
- res_age_10~60_rate: 연령별 비율 (null)
- etc0, etc1: 예비 필드
- error: 오류 메시지

---

## 4단계: 스케줄러 실행 (자동 수집)

GENIE는 **누적 데이터만 제공**하므로 과거 데이터 소급이 불가능합니다.
시계열 데이터를 축적하려면 스케줄러를 실행하여 매일 자동 수집해야 합니다.

```bash
python -m music_metrics_collector.main run-scheduler --config config.yaml
```

### 동작 방식

1. `config.yaml`의 `schedule.cron` 설정에 따라 주기적 실행
2. 설정된 시간마다 3단계(JSONL 생성)를 자동 수행
3. 백그라운드에서 계속 실행 (Ctrl+C로 종료)

### 스케줄 설정 (config.yaml)

```yaml
schedule:
  enabled: true
  cron: "0 9 * * *"  # 매일 오전 9시 실행
```

### cron 표현식 예시

| 표현식 | 설명 |
|--------|------|
| `0 9 * * *` | 매일 오전 9시 |
| `0 0 * * *` | 매일 자정 |
| `0 */6 * * *` | 6시간마다 (0시, 6시, 12시, 18시) |
| `0 * * * *` | 매시간 정각 |

### 백그라운드 실행 (권장)

```bash
# nohup으로 백그라운드 실행
nohup python -m music_metrics_collector.main run-scheduler --config config.yaml > scheduler.log 2>&1 &

# 로그 확인
tail -f scheduler.log

# 프로세스 종료
pkill -f "run-scheduler"
```

---

## 디렉토리 구조

```
aurora_muz_data_crawling/
├── config.yaml
├── requirements.txt
├── resource/
│   └── GENIE/
│       ├── search_data.csv     # 입력
│       └── song_data.csv       # 2단계 출력
├── data/
│   └── logs/
│       └── 2026-01-27_GENIE.jsonl  # 3단계 출력
└── music_metrics_collector/
    ├── main.py
    ├── generate_song_ids.py
    └── collectors/
        └── genie.py
```

---

## 설정 파일 (config.yaml)

```yaml
enabled_platforms:
  - GENIE

resource_dir: resource

platforms:
  GENIE:
    resource_csv: true
    metrics:
      total_plays: ".daily-chart .total div:nth-child(1) p"
      total_listeners: ".daily-chart .total div:nth-child(2) p"

mode: auto  # requests | playwright | auto

schedule:
  enabled: true
  cron: "0 9 * * *"  # 매일 오전 9시

log:
  base_dir: data/logs

http:
  timeout_sec: 20
```
