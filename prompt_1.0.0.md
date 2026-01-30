아래 내용을 **Cursor.ai에 그대로 붙여넣으면** 됩니다. (플랫폼 구분 + 곡 코드값 입력 + 플랫폼별 수집/스케줄/DB 적재까지 포함)

---

### Cursor.ai 프롬프트

당신은 시니어 데이터 엔지니어/백엔드 엔지니어다. 다음 요구사항을 만족하는 파이썬 기반 “음원 플랫폼 멀티 수집기”를 설계/구현하라. 사용자는 config에 **플랫폼과 곡 코드(song_id)만** 입력하며, 수집기는 플랫폼별 PC 웹(공개 페이지)에서 가능한 지표를 추출해 **매일 1회** SQLite에 저장한다.

## 0) 핵심 목표

* 플랫폼 구분: `GENIE`, `BUGS`, `MELON` (확장 가능)
* 입력: platform + song_id
* 출력: 날짜(date)별 누적 지표 저장 (일별 증가량은 차분으로 계산 가능)

## 1) 준수사항(중요)

* 로그인/캡차 우회/봇 차단 회피/비공개 API 역공학/세션 탈취 등은 구현하지 않는다.
* 공개 웹페이지에 노출된 값만 수집한다.
* 하루 1회, 곡당 1~2 요청 수준으로 보수적으로 동작한다.
* 실패 시 프로세스를 중단하지 말고 해당 항목만 FAILED로 기록하고 진행한다.

## 2) 지원 지표(1차)

* GENIE(PC 곡 상세): total_plays(전체 재생수), total_listeners(전체 청취자수)
* BUGS(PC 곡 상세): total_plays(누적 재생수) (listeners는 NULL)
* MELON(PC 곡 상세): total_plays(누적 감상 수) (listeners는 NULL)
* 각 플랫폼별 “지원 지표”를 코드로 명시하고 미지원은 NULL 처리

## 3) 아키텍처 (플러그인/전략 패턴)

플랫폼별 Collector 클래스를 분리하고 팩토리로 선택한다.

* Collector가 책임지는 것:

  1. build_url(song_id)
  2. fetch_html(url)
  3. parse_metrics(html) -> 표준 모델 반환
* 공통 fetcher는 `requests` 우선, 파싱 실패/JS 렌더링 필요 시 `playwright`로 폴백(mode=auto)

## 4) 파일 구조 (필수 생성)

* README.md
* requirements.txt
* .env.example
* config.yaml
* music_metrics_collector/

  * **init**.py
  * main.py            # CLI entrypoint
  * scheduler.py       # APScheduler
  * factory.py         # CollectorFactory
  * fetcher.py         # requests/playwright 구현
  * normalizer.py      # 숫자 정규화 (1,234 / 12.3만 / 1.2M 등)
  * storage.py         # SQLite upsert
  * models.py          # dataclass/pydantic
  * collectors/

    * **init**.py
    * base.py
    * genie.py
    * bugs.py
    * melon.py
  * utils.py           # logging, retry, tz
* data/ (자동 생성)
* tests/

  * test_normalizer.py
  * test_parsers_genie.py
  * test_parsers_bugs.py
  * test_parsers_melon.py

## 5) Config 설계 (플랫폼별 곡코드 입력)

config.yaml 형식은 아래를 지원하라.

enabled_platforms:

* GENIE
* BUGS
* MELON

targets:

* platform: GENIE
  song_id: "12345678"
  alias: "optional"
* platform: BUGS
  song_id: "987654321"
* platform: MELON
  song_id: "54321098"

mode: auto   # requests | playwright | auto
schedule:
enabled: true
cron: "0 3 * * *"   # 매일 03:00 (Asia/Seoul)
storage:
sqlite_path: "data/music_metrics.sqlite"
export_csv: true
export_path: "data/export.csv"
http:
timeout_sec: 20
max_retries: 3
backoff_sec: 2

## 6) DB 스키마 (플랫폼 구분 포함)

SQLite 테이블 2개 생성

(1) tracks

* track_key TEXT PRIMARY KEY     # "{platform}:{song_id}"
* platform TEXT
* song_id TEXT
* alias TEXT NULL
* title TEXT NULL
* artist TEXT NULL
* album TEXT NULL
* release_date TEXT NULL
* source_url TEXT
* created_at TEXT
* updated_at TEXT

(2) track_metrics_daily

* track_key TEXT
* date TEXT (YYYY-MM-DD, Asia/Seoul)
* total_plays INTEGER NULL
* total_listeners INTEGER NULL
* collected_at TEXT (ISO8601)
* status TEXT           # OK | FAILED
* error_message TEXT NULL
* PRIMARY KEY (track_key, date)
* FOREIGN KEY (track_key) REFERENCES tracks(track_key)

동일 날짜 재수집 시 upsert로 최신값으로 갱신한다.

## 7) 파싱 요구사항

* 플랫폼별 DOM 구조가 다르므로 각 Collector에 selector 후보를 2~3개 두고 순차 시도
* 숫자 정규화:

  * "1,234,567" -> 1234567
  * "12.3만" -> 123000
  * "1.2M" -> 1200000
* 파싱 실패 시 예외로 전체 중단 금지. 해당 target만 FAILED 기록.

## 8) 스케줄/CLI

CLI 지원:

* python -m music_metrics_collector.main collect --config config.yaml

  * 즉시 1회 수집
* python -m music_metrics_collector.main run-scheduler --config config.yaml

  * APScheduler로 cron 실행

출력 요약:

* 총 targets 수
* 플랫폼별 성공/실패 건수
* 저장 레코드 수
* 수행 시간

## 9) 테스트

* normalizer 단위테스트
* 각 플랫폼 파서 테스트(HTML fixture)
* auto 모드에서 requests 실패 시 playwright 폴백되는지 mock 테스트

## 10) README

* 지원 플랫폼/지원 지표 표
* config.yaml 예시
* 실행 예시
* 스키마 설명
* 운영 주의사항(공개 데이터만, 빈도 최소화, 구조 변경 시 파서 업데이트)

## 11) 구현 팁(반드시 반영)

* enabled_platforms에 없는 target은 스킵 + 경고 로그
* mode=auto: requests 시도 → 지표가 비어 있으면 playwright 폴백
* timezone Asia/Seoul 고정
* logging 레벨은 .env로 제어

요구사항을 충족하는 전체 코드를 생성하고, 위 파일들을 실제로 작성하라. 또한 config.yaml, .env.example, requirements.txt, README.md까지 완성하라.

