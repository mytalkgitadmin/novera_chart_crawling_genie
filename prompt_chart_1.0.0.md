아래 프롬프트를 **Cursor.ai에 그대로 붙여넣으면**, 지금처럼 플랫폼별로 수집된 JSON(라인 단위 JSONL)을 입력으로 받아 **차트 생성 + 요약 리포트 + 파일 저장(HTML/PNG/CSV)**까지 가능한 파이썬 프로젝트를 생성하도록 지시합니다.

---

## Cursor.ai 프롬프트 (차트 생성기)

당신은 시니어 데이터 분석 엔지니어다. 아래 요구사항을 만족하는 파이썬 기반 “플랫폼 스트리밍 지표 차트 생성기”를 설계/구현하라. 입력 데이터는 라인 단위 JSON(JSONL)이며, 각 라인은 다음 필드를 가진다:

예시 레코드(모든 필드는 문자열/정수 혼합 가능):
{
"platform": "GENIE",
"song_id": "107944474",
"song_name": "Solution",
"artist_name": "최인희 & 오혜주",
"date": "2025-12-17",
"hour": 17,
"minute": 56,
"total_plays": 2689,
"total_listeners": 5779
}

### 0) 목표

* JSONL 파일을 읽어 정규화한 뒤, 시간축 기반 차트를 생성한다.
* 플랫폼별/곡별로 시간에 따른 `total_plays`, `total_listeners` 변화 추이를 시각화한다.
* 결과물을 `output/` 폴더에 HTML과 PNG로 저장한다.
* 데이터 품질 이슈(중복, 시간 정렬, 결측, 숫자 타입)를 안전하게 처리한다.

---

## 1) 기술 스택

* Python 3.11+
* pandas
* matplotlib (기본 차트)
* plotly (인터랙티브 HTML 리포트; 가능하면 추가)
* pydantic 또는 pandera(선택)로 스키마 검증
* typer 또는 argparse로 CLI 구성

---

## 2) 프로젝트 구조(필수)

* README.md
* requirements.txt
* chart_maker/

  * **init**.py
  * main.py               # CLI entrypoint
  * io.py                 # JSONL 로더/세이버
  * transform.py          # 정규화/정제 로직
  * metrics.py            # 파생지표(증가량, 증감률 등)
  * charts.py             # matplotlib/plotly 차트 생성
  * report.py             # 요약 테이블/리포트 HTML 생성
  * utils.py              # 로깅, 경로, 공통
* data/

  * sample.jsonl          # 샘플(사용자가 넣어 테스트 가능)
* output/

  * (생성) reports/
  * (생성) png/
  * (생성) csv/
* tests/

  * test_transform.py
  * test_metrics.py

---

## 3) 데이터 정규화 규칙

### 3-1) datetime 생성

* `date` + `hour` + `minute` 로 `timestamp` 생성
* 타임존은 Asia/Seoul로 간주하되, 내부 저장은 naive로 처리해도 된다(문서에 명시).

### 3-2) 키 정의 및 중복 제거

* 1개 측정치의 고유 키:

  * platform + song_id + timestamp
* 동일 키가 중복되면:

  * total_plays / total_listeners가 동일하면 1개만 유지
  * 값이 다르면 “가장 마지막에 등장한 레코드”를 채택하고, 충돌 건수 로그로 남긴다.

### 3-3) 정렬/결측 처리

* platform, song_id, timestamp 기준으로 정렬한다.
* 일부 레코드에 total_listeners가 없으면 NaN 처리 후 차트에서는 해당 값 라인을 끊어서 표현한다.

---

## 4) 파생지표 산출(필수)

곡별 시계열에서:

* delta_plays = total_plays.diff()
* delta_listeners = total_listeners.diff()
* delta_minutes = timestamp.diff()를 분 단위로 산출
* rate_plays_per_min = delta_plays / delta_minutes (0 또는 음수/결측은 NaN 처리)
* rate_listeners_per_min = delta_listeners / delta_minutes (동일)

주의:

* total_plays/total_listeners는 “누적값”이므로 diff가 음수면 데이터 이상치로 보고 별도 카운트 및 로그.
* delta_minutes가 0이면 분모 0이므로 NaN 처리.

---

## 5) 차트 요구사항(필수 출력)

### 5-1) 곡별 시계열 라인차트(기본)

* X축: timestamp
* Y축: total_plays, total_listeners
* 곡별로 파일 생성:

  * output/png/{platform}_{song_id}_totals.png
  * output/reports/{platform}_{song_id}_report.html (plotly 가능 시)

### 5-2) 곡별 “증가량” 차트

* X축: timestamp
* Y축: delta_plays, delta_listeners (bar 또는 line)
* 파일:

  * output/png/{platform}_{song_id}_delta.png

### 5-3) 플랫폼 단위 요약 차트(선택이 아닌 필수)

* 동일 플랫폼 내 여러 곡을 한 화면에서 비교:

  * (A) 총 재생수 최종값 상위 N곡 막대그래프
  * (B) 최근 구간(예: 마지막 3개 포인트) 평균 증가량 상위 N곡 막대그래프
* N은 CLI 옵션으로 기본 10

---

## 6) 요약 테이블(필수)

각 platform별로 아래 요약 CSV를 생성:

* output/csv/{platform}_summary.csv
  컬럼:
* platform, song_id, song_name, artist_name
* first_timestamp, last_timestamp
* first_total_plays, last_total_plays, net_plays (last-first)
* first_total_listeners, last_total_listeners, net_listeners
* avg_rate_plays_per_min, avg_rate_listeners_per_min
* num_points, num_anomalies_negative_diff

---

## 7) CLI 요구사항

다음 커맨드를 지원하라:

1. 단일 실행
   python -m chart_maker.main render 
   --input data/input.jsonl 
   --outdir output 
   --topn 10 
   --platform GENIE

옵션:

* --platform: 특정 플랫폼만 필터(없으면 전체)
* --song-id: 특정 곡만 필터(없으면 전체)
* --topn: 플랫폼 비교 차트 N
* --export-html: plotly HTML 리포트 생성 여부 (기본 true)
* --export-png: matplotlib PNG 생성 여부 (기본 true)

---

## 8) README에 포함할 내용

* 입력 포맷(JSONL) 설명
* 실행 방법
* 산출물 경로
* “누적값 기반이므로 diff/증가량은 샘플링 간격에 민감” 주의사항
* 데이터 중복/이상치 처리 규칙

---

## 9) 구현 세부 지침

* matplotlib 차트는 “곡별 파일 생성” 시 축 레이블/타이틀/범례 포함
* plotly HTML 리포트에는:

  * totals line chart
  * delta chart
  * 요약 테이블(HTML table)
  * 이상치 로그(음수 diff, 중복 충돌 건수) 요약을 포함
* 로깅은 logging 모듈 사용 (INFO 기본)

---

## 10) 샘플 데이터

data/sample.jsonl 파일에, 사용자가 제공한 예시 3~5개 레코드를 포함해 실행 확인 가능하게 하라.

---

위 요구사항을 만족하는 전체 코드를 생성하고, 모든 파일을 실제로 작성하라. 또한 실행 예시와 예상 출력물을 README에 구체적으로 문서화하라.

---

원하시면, 위 프롬프트에 “여러 플랫폼을 한 대시보드에서 비교(플랫폼별 탭)” 형태의 **단일 HTML 리포트** 생성까지 확장하는 요구사항도 추가해 드릴 수 있습니다.
