# 검증 결과: 프로젝트 문서와 소스의 정합성 감사

**일시**: 2026-08-07 +09:00

**대상 타입**: 문서(README, ARCHITECTURE, history, .env.example)
**기준 커밋**: `d2c2bfc` (redesign(web): 콘솔을 라이트 작업대 테마로 전환하고 밀도를 높임)

---

## 요약: 검증 항목 18건 / 일치 13 / 불일치 5

문서의 서술 정확도 자체는 높다. 라우트 소유권, 쿠키 분기, retention 정책, 종료 타임아웃,
알림 쿨다운, 감지 순서 등 세부 수치까지 실제 소스와 맞았다. 불일치 5건은 모두
**최근 5개 커밋이 문서와 테스트를 함께 갱신하지 않아 생긴 지연**이며, 서술 오류가 아니다.

| # | 검증 항목 | 문서 위치 | 결과 |
|---|-----------|-----------|------|
| V01 | 라이브 감지 순서와 `extract_flat` 옵션 | `ARCHITECTURE.md:85-103` | 일치 |
| V02 | ffmpeg 종료 타임아웃 5s + 2s = 7초 | `ARCHITECTURE.md:167-172`, `:244` | 일치 |
| V03 | 봇 감지 알림 쿨다운 30분 | `ARCHITECTURE.md:190` | 일치 |
| V04 | retention 보존 디렉터리 3종 | `README.md:260-262` | 일치 |
| V05 | 쿠키 인증 우선순위 3분기 | `ARCHITECTURE.md:174-182` | 일치 |
| V06 | 라우트 소유권 표 (8개 모듈) | `README.md:266-278`, `ARCHITECTURE.md:154-163` | 일치 |
| V07 | `/api/monitor/start\|stop` 405 계약 | `README.md:277`, `ARCHITECTURE.md:148` | 일치 |
| V08 | Docker 서비스 4종과 포트 매핑 | `README.md:113-118` | 일치 |
| V09 | autoheal label이 `pot-provider`에만 존재 | `README.md:131-132` | 일치 |
| V10 | Scheduled Task 오전 3시 / 10분 제한 / 중복 무시 | `ARCHITECTURE.md:120-127` | 일치 |
| V11 | heartbeat 기반 모니터 상태 표시 | `ARCHITECTURE.md:146` | 일치 |
| V12 | 웹 UI 화질 옵션 2160p~360p와 MP3 | `README.md:26-27` | 일치 |
| V13 | File System Access API 저장 경로 | `README.md:34` | 일치 |
| V14 | **frontend 회귀 테스트가 실제로 통과** | `ARCHITECTURE.md:228` | **불일치** |
| V15 | **런타임 Python 버전** | `README.md:38` | **불일치** |
| V16 | **동시성 표의 lock 목록 완전성** | `ARCHITECTURE.md:194-203` | **불일치** |
| V17 | **구조 트리의 `docs/` 설명** | `README.md:232`, `ARCHITECTURE.md:64` | **불일치** |
| V18 | **`.env.example`의 환경변수 완전성** | `README.md:53` | **불일치** |

---

## 불일치 상세

### V14: 문서가 약속한 frontend 회귀 보호가 동작하지 않음 — 심각

**문서 주장** (`ARCHITECTURE.md:228`)

> 사용자 화면의 병합·분할 동작 | `tests/web/frontend/` | 별도 frontend test runner가 없으므로
> Node로 실제 함수를 실행하고, markup-only 계약은 필요한 DOM selector만 확인한다.

**실제**: `uv run pytest` → **6 failed, 285 passed**

| 실패 테스트 | 원인 |
|-------------|------|
| `test_merge_sequence.py::test_frontend_groups_part_runs_by_hash_like_token` | `formatPartRangeName`의 라벨이 group → 접두사 전체, 구분자 `-` → `·`로 변경 |
| `test_merge_sequence.py::test_frontend_source_tree_groups_by_hash_token` | `colorForGroup()` 삭제 — 테스트가 없는 함수를 주입 시도 |
| `test_merge_sequence.py::test_frontend_source_tree_hides_files_already_in_sequence` | 위와 동일 |
| `test_select_all_sequence.py::test_merge_page_exposes_select_all_and_deselect_all_controls` | 카드 제목 "소스 파일"→"합칠 영상 고르기", "합치기 순서"→"순서 정하고 합치기" |
| `test_select_all_sequence.py::test_frontend_select_all_keeps_part_files_compact_and_deselect_all_clears` | `colorForGroup()` 삭제 + 라벨 포맷 변경 |
| `test_split.py::test_split_tab_contains_search_and_upload_controls` | 버튼 라벨 "PC 영상 업로드"→"PC 영상 올리기" |

**판정 근거**
- 기능 소실이 아니다. `selectAllFiles`(`app.js:475`), `deselectAllFiles`(`app.js:487`),
  업로드 버튼(`index.html:383`)은 모두 살아 있고 id도 그대로다.
- `getPartInfo`의 라벨 변경은 `app.js:541-543` 주석에 의도가 명시된 개선이다
  ("`20260804_210000`만 보여주면 어느 채널의 녹화인지 알 수 없다").
- `d2c2bfc` 커밋 메시지가 두 변경을 모두 의도로 선언한다 — "의미 없이 해시로 뽑던
  그룹 8색을 걷어내고 선택 상태만 색으로 남김", "그룹 이름에 채널명 복원
  (20260804_210000 → 우왁굳_20260804_210000)".
- 따라서 회귀가 아니라 **테스트가 리디자인을 따라가지 못한 상태**이며,
  기대값을 현재 콘솔에 맞추는 것이 옳다.
- 유입 경로: `8469ed4`, `6f77265`, `d9ec22a`, `d2c2bfc` 4개 커밋이 `web/`만 변경하고
  `tests/web/frontend/`를 갱신하지 않았다.

### V15: README의 런타임 Python 버전이 낡음

| 출처 | 값 |
|------|-----|
| `README.md:38` (기술 스택) | **Python 3.13** |
| `.python-version` | 3.15 |
| `Dockerfile:1` | `python:3.15-rc-alpine` |
| `pyproject.toml:6` | `>=3.13` (하한만 명시, 모순 아님) |
| `docs/verify/2026-08-05-...-report.md:59` | 컨테이너 실측 Python 3.15.0b4 |

**유입 경로**: `aff8982`(문서 동기화)가 `7aa1449`(Python 3.15 RC 전환) **직전**에 위치해,
런타임 전환이 문서에 반영되지 못했다.

### V16: 동시성 표에 `MultiChannelMonitor`의 thread map lock 누락

`service.py:36`의 `_monitor_threads_lock: threading.Lock`이 `ARCHITECTURE.md:194-203`
동시성 표에 없다. 같은 문서의 테스트 전략 표(`:227`)는 "웹 요청과 감시 loop가 같은
thread map을 다루며"라고 이 경계를 전제하고 있어, 표 사이에 서술 공백이 있다.

### V17: 구조 트리가 `docs/verify/`를 설명하지 않음

두 문서 모두 `docs/`를 "현재 아키텍처와 v0 개발 이력"으로만 적는다. 실제로는
검증 리포트 2종과 스크린샷 4장이 있고, 이 감사 리포트가 세 번째다.

### V18: `.env.example`에 `YT_COOKIE_BROWSER` 없음

`README.md:53`은 환경변수 표에 `YT_COOKIE_BROWSER`(기본 `firefox`)를 싣고 있고
`cookies.py:60`이 실제로 읽지만, `.env.example`에는 항목이 없어 로컬 실행 사용자가
존재를 알기 어렵다.

---

## 참고: 문서 오류가 아니라고 판정한 항목

- **`docs/history.md`의 `config.json`·단일 `main.py`·미완료 체크리스트**: 문서 상단
  (`history.md:3-7`)이 v0 프로토타입 기록임을 명시하고 현재 구조를 안내하므로 정상이다.
- **`Dockerfile:37`의 HEALTHCHECK가 `localhost`**: `docker-compose.yml:81`이
  `127.0.0.1`로 override하므로 Compose 운영 경로에는 영향이 없다. 다만 Dockerfile
  단독 실행 시 BusyBox wget의 IPv6 우선 해석 문제가 재발할 수 있어 정합성 정리 대상이다.

## 후속 조치

| 항목 | 조치 | 상태 |
|------|------|------|
| V14 | `tests/web/frontend/` 3개 파일의 기대값을 현재 콘솔에 맞춰 복구 | `dc29c7e` — 291 passed |
| V15, V16, V17 | `README.md`, `docs/ARCHITECTURE.md` 동기화 | `a6fb0ab` |
| V18 + Dockerfile HEALTHCHECK | `.env.example` 보완, `Dockerfile`을 `127.0.0.1`로 정리 | `77fe762` — 단독 run healthy 확인 |
| V14 재발 방지 | `web/` 변경이 frontend 테스트를 앞지르지 못하도록 pre-commit hook 추가 | 이 리포트와 함께 갱신 |

V14는 기대값을 고치는 것만으로 닫히지 않는다. 테스트가 뒤처진 것이 원인이 아니라
**뒤처져도 아무도 막지 않은 것**이 원인이기 때문이다. `frontend-regression` hook이
`web/`·`tests/web/frontend/` stage 시 테스트를 실행해 같은 유입 경로를 차단한다.
훅 자체는 라벨을 일부러 되돌려 실패(exit 1)를 재현하는 방식으로 검증했다.
