# "다시는 이런 문제가 발생하지 않는다고 보증할 수 있는가?"

**아니요. 보증할 수 없어요.**

yt-dlp는 YouTube의 비공식 리버스 엔지니어링 클라이언트예요. YouTube가 내부 API 응답 구조를 바꾸거나, 새로운 인증 레이어를 추가하거나, BotGuard 로직을 변경하면 — 우리 코드와 무관하게 시스템이 깨져요. 2026-04-06 사건이 정확히 그 패턴이었어요. 쿠키도 멀쩡하고 코드도 문제없었는데, YouTube가 PO Token을 필수로 요구하기 시작하면서 전체 감지 파이프라인이 무너졌어요.

**보증할 수 있는 것은 이거예요:**

- 장애가 발생하면 **5분 안에 감지**하고
- **30분 안에 원인을 파악**하고
- **1시간 안에 복구하거나 fallback으로 전환**하는 것

예원 제의 말이 정확해요. 장애를 예방하는 것이 아니라, 장애를 빠르게 감지하고 복구하는 구조를 만드는 것이 핵심이에요.

---

## 1. 종합 등급 테이블

| 리뷰어 | 등급 | 핵심 관점 | 가장 날카로운 지적 |
|--------|------|----------|------------------|
| 토니 스타크 | B+ | 실행력/구현 | TODO에 적었지만 코드에 안 넣으면 희망사항 |
| 예원 제 | B | 아키텍처/복원력 | "다시는 안 일어난다"는 보증 불가, 어댑터 레이어 필요 |
| 이상 | C | 운영/지속성 | 1년 무인 운영 불가능한 구조 |
| 발루 | B+ | 코드 품질/계약 | yt-dlp 응답을 직접 쓰는 구조 자체가 문제 |
| 프랭크 | C | 문서/프로세스 | 기록된 전략과 실행 가능한 문서 사이의 간극 |
| 페이지 | D | UX/가시성 | 모니터 상태 API가 "실행 중"만 보여줌 |
| 파후 | B | 테스트/안전망 | 버그 픽스를 지켜주는 테스트가 0개 |
| 초록문어 | B | 비용/ROI | 장애를 막는 것보다 장애를 아는 것이 먼저 |

**종합 등급: C+**

전략의 방향은 맞아요. 3중 감지 fallback, cookie_helper 분리, PO Token 사이드카 — 각각 올바른 판단이에요. 하지만 **전략이 코드에 반영되지 않았고, 테스트가 없고, 알림이 없고, 문서가 죽어있어요.** 설계도만 그려놓고 건물을 안 지은 상태예요.

---

## 2. 공통 평가 (8명 중 다수 동의)

### 8/8 동의: yt-dlp 응답을 직접 사용하는 구조가 근본 취약점

`youtube_client.py`의 `_is_entry_live`가 `entry.get("is_live")`, `entry.get("live_status")`를 직접 참조해요. yt-dlp가 응답 키 이름을 바꾸거나 구조를 변경하면 — **아무런 에러 없이 조용히 감지를 실패**해요. `False`를 반환할 뿐이니까요.

토니, 예원, 발루, 파후가 공통으로 지적: **yt-dlp 응답 → 내부 DTO 변환 레이어(어댑터)**가 없으면 다음 yt-dlp 업데이트 때 동일한 패턴으로 터져요.

### 7/8 동의: 알림 채널이 없음

장애가 발생해도 Docker 로그를 직접 뒤져야 인지할 수 있어요. Telegram/Discord/Slack webhook 하나면 해결되는 문제인데, 현재 **장애 감지 → 사람에게 전달하는 경로가 0개**예요. 초록문어가 ROI 1순위로 꼽은 이유가 여기 있어요.

### 7/8 동의: 테스트가 사실상 없음

`tests/` 디렉토리 자체가 존재하지 않아요. `_is_entry_live`, `_build_ffmpeg_headers`, `get_cookie_options` — 버그가 발생했던 정확히 그 함수들에 단위 테스트가 0개예요. 파후의 말이 맞아요: "버그 픽스를 지켜주는 테스트가 없어서 다음 yt-dlp 업데이트 때 똑같이 뚫린다."

### 6/8 동의: FFmpeg stderr 캡처 안 됨

`stream_downloader.py` line 165의 `subprocess.run(cmd)`가 stderr를 캡처하지 않아요. FFmpeg가 실패해도 **왜 실패했는지 알 수 없어요.** TODO.md P0에 적혀있지만 코드에 미적용.

### 6/8 동의: Docker healthcheck 없음

`docker-compose.yml`에 healthcheck 설정이 없어요. 컨테이너가 올라가 있지만 내부적으로 죽어있는 상태를 감지할 수 없어요. `Dockerfile`의 `EXPOSE 8088`도 실제 앱 포트 `8011`과 불일치 — TODO.md P0이지만 미적용.

### 5/8 동의: MonitorStatus가 빈약함

현재 `/api/monitor/status`가 반환하는 정보: `is_running`, `active_channels`, `total_channels`. 이게 전부예요. 채널별 마지막 체크 시각, 감지 성공/실패 이력, 현재 다운로드 상태 — 아무것도 없어요. 페이지의 표현이 정확해요: "모니터가 '실행 중'만 보여주는 건 대시보드가 아니야."

---

## 3. 우선순위 개선 목록

### Critical (장애 재발 시 즉시 인지/복구 불가)

| # | 항목 | 예상 공수 | 근거 |
|---|------|----------|------|
| C1 | **장애 알림 채널 구축** (Telegram/Discord webhook) | 2-3시간 | 알림 없으면 장애 인지가 Docker 로그 확인에 의존. 초록문어 ROI 1순위 |
| C2 | **FFmpeg stderr 캡처 + 에러 로깅** | 1시간 | `subprocess.run(cmd, capture_output=True)` 한 줄. TODO P0 미적용 상태 |
| C3 | **yt-dlp 응답 어댑터 레이어** (Pydantic DTO) | 4-6시간 | `entry.get("live_status")` 직접 참조를 DTO 변환으로 교체. 키 변경 시 ValidationError로 즉시 감지 |
| C4 | **`_is_entry_live` + `_build_ffmpeg_headers` 단위 테스트** | 3-4시간 | 버그 발생 함수에 regression 테스트. 실제 yt-dlp 응답 fixture 기반 |
| C5 | **cookie_helper 스레드 안전성** (`threading.Lock`) | 1시간 | `_cookie_temp_path`, `_cookie_valid` 전역 변수 race condition. TODO P0 미적용 |

### Important (운영 안정성/가시성)

| # | 항목 | 예상 공수 | 근거 |
|---|------|----------|------|
| I1 | **Docker healthcheck 추가** | 1시간 | `/api/health` 엔드포인트 + docker-compose healthcheck. TODO P2이지만 실제로는 P1 |
| I2 | **Dockerfile EXPOSE 포트 수정** (8088 → 8011) | 5분 | TODO P0. 가장 쉬운 수정인데 아직 안 함 |
| I3 | **MonitorStatus 확장** (채널별 감지 이력, 마지막 체크 시각, 연속 실패 카운트) | 4-6시간 | 현재 is_running만 반환. 채널별 상태 블라인드 |
| I4 | **yt-dlp contract test** (응답 스냅샷 비교) | 4-8시간 | yt-dlp 업데이트 시 응답 구조 변경을 CI에서 사전 감지 |
| I5 | **연속 실패 시 알림 + 재시도 로직** | 3-4시간 | N회 연속 감지 실패 → 알림 발송 + 지수 백오프 재시도 |
| I6 | **Graceful shutdown** (FastAPI lifespan) | 2-3시간 | 모니터 스레드, cleanup 스케줄러 정리. TODO P1 |

### Nice-to-have (장기 안정성/확장성)

| # | 항목 | 예상 공수 | 근거 |
|---|------|----------|------|
| N1 | **YouTube Data API v3 하이브리드 감지** | 8-12시간 | 라이브 감지를 공식 API로 분리. 단일 의존성(yt-dlp) 분산 |
| N2 | **런북(Runbook) 작성** | 2-3시간 | 장애 유형별 대응 절차 문서화. 프랭크 지적 |
| N3 | **의존성 변경 체크리스트** | 1시간 | yt-dlp, bgutil 업데이트 시 확인 항목 |
| N4 | **web_api.py / cookie_helper.py 통합 테스트** | 6-8시간 | FastAPI TestClient 기반. TODO P1 |
| N5 | **디스크 모니터링** | 2시간 | 다운로드 디렉토리 용량 임계치 알림. 이상 지적 |
| N6 | **pot-provider 장애 전파 분석 + fallback** | 3-4시간 | pot-provider 다운 시 yt-dlp가 어떻게 동작하는지 테스트 필요. 예원 지적 |
| N7 | **장시간 방송 중 URL 만료 대응** | 4-6시간 | 3시간+ 방송에서 ffmpeg 입력 URL 만료 시나리오. 예원 지적 |

---

## 4. 충돌 해소

### 충돌 1: TODO.md 우선순위 vs 실제 우선순위

**TODO.md**에서 Health check를 P2(Nice-to-have)로 분류했어요. 하지만 토니, 이상, 초록문어 모두 healthcheck를 **운영 필수**로 판단했어요.

**판단:** healthcheck는 **Important(I1)**로 승격해요. 컨테이너가 좀비 상태인지 아닌지 판별할 수단이 없으면 `restart: unless-stopped`도 무의미해요.

### 충돌 2: contract test 스냅샷 갱신 주체

파후는 "yt-dlp 실제 응답을 fixture로 저장하고 CI에서 비교"를 제안했고, 발루는 "스냅샷 갱신 주체가 불명확하면 오히려 false positive로 CI가 무력화된다"고 반박했어요.

**판단:** 스냅샷은 **수동 갱신 + PR 리뷰** 방식으로 운영해요. CI가 불일치를 감지하면 실패 처리하되, `uv run pytest --update-snapshots` 명령으로 갱신하고 diff를 사람이 확인해요. 자동 갱신은 하지 않아요.

### 충돌 3: YouTube Data API v3 도입 시점

초록문어는 "단일 의존성 분산을 위해 도입 필요"라 했고, 토니는 "현재 3중 fallback이면 충분, API 쿼터 관리 복잡도가 늘어난다"고 했어요.

**판단:** Nice-to-have(N1)로 유지해요. 현재 3중 fallback(`/live` → `/streams` → channel page)이 동작하고 있고, 세 곳 모두 실패하는 경우는 yt-dlp 자체 장애인데 그건 API v3로도 커버 안 돼요. 다만, **yt-dlp 의존성 제거가 목표라면** 장기적으로 검토할 가치는 있어요.

### 충돌 4: ARCHITECTURE.md 관리

프랭크는 "죽은 문서"라 했고, 이상은 "문서 관리 자체가 오버헤드"라 했어요.

**판단:** ARCHITECTURE.md를 별도로 관리하지 않아요. README.md의 "프로젝트 구조" 섹션이 이미 같은 역할을 하고 있어요. 중복 문서를 유지하는 비용 > 가치.

---

## 5. 빠진 관점 종합

### 아무도 언급하지 않은 것들

1. **yt-dlp 버전 고정(pinning) 전략이 없어요.** `pyproject.toml`에서 yt-dlp 버전을 어떻게 관리하는지 논의가 빠졌어요. 최신 버전 자동 추적 vs 특정 버전 고정 — 이 판단이 contract test보다 먼저 와야 해요.

2. **pot-provider 이미지 버전 고정이 없어요.** `docker-compose.yml`에서 `brainicism/bgutil-ytdlp-pot-provider:latest`를 사용 중이에요. latest 태그는 예고 없이 breaking change가 들어올 수 있어요.

3. **로그 로테이션/보존 정책이 불명확해요.** `Logger`가 일별 로테이션을 한다고 하는데, Docker 환경에서 로그 볼륨이 무한정 커질 수 있어요. `--log-opt max-size` 설정이 없어요.

4. **yt-monitor와 yt-web 간 상태 공유가 없어요.** 페이지가 부분적으로 언급했지만, 두 컨테이너가 `channels.json` 파일을 동시에 읽고 쓸 때의 race condition을 아무도 분석하지 않았어요.

5. **보안 리뷰가 빠졌어요.** `cookies.txt`가 Docker 볼륨으로 마운트되는데, 컨테이너 내부에서 평문으로 노출돼요. `web_api.py`의 CORS가 `allow_origins=["*"]`로 열려있어요.

---

## 6. 액션 아이템 체크리스트 (ROI 순서)

투자 대비 효과가 높은 순서대로 정렬했어요. "가장 적은 시간으로 가장 큰 위험을 줄이는 것"이 기준이에요.

### Phase 1: 즉시 실행 (1일, ~5시간)

> 장애를 **아는 것**이 먼저

- [ ] **C2. FFmpeg stderr 캡처** — `stream_downloader.py` line 165에 `capture_output=True` 추가, `result.stderr` 로깅 (1시간)
- [ ] **C5. cookie_helper 스레드 Lock** — `_cookie_temp_path`, `_cookie_valid` 접근에 `threading.Lock` 추가 (1시간)
- [ ] **I2. Dockerfile EXPOSE 수정** — `8088` → `8011` (5분)
- [ ] **C1. 장애 알림 webhook** — 연속 N회 감지 실패 시 Telegram/Discord 알림 발송. `logger.error` 호출 지점에 webhook 트리거 (2-3시간)

### Phase 2: 테스트 안전망 (2-3일, ~12시간)

> 버그 픽스를 **지켜주는** 울타리

- [ ] **C4. 핵심 함수 단위 테스트** — `_is_entry_live` (live_status 경로 포함), `_build_ffmpeg_headers`, `get_cookie_options` fixture 기반 테스트 (3-4시간)
- [ ] **I1. Docker healthcheck** — `/api/health` 엔드포인트 + docker-compose `healthcheck` 설정 (1시간)
- [ ] **C3. yt-dlp 응답 어댑터 DTO** — `YtDlpVideoInfo`, `YtDlpPlaylistEntry` Pydantic 모델. `entry.get("live_status")` 직접 참조를 DTO 변환으로 교체. 키 누락/변경 시 `ValidationError` (4-6시간)
- [ ] **I4. contract test 초안** — yt-dlp 실제 응답 1건을 fixture로 저장, DTO 파싱 테스트 (2-3시간)

### Phase 3: 운영 가시성 (1주, ~12시간)

> **보이지 않으면 고칠 수 없다**

- [ ] **I3. MonitorStatus 확장** — 채널별 `last_checked_at`, `consecutive_failures`, `last_live_detected_at`, `current_state` 추가 (4-6시간)
- [ ] **I5. 연속 실패 재시도 + 알림** — 지수 백오프, 3회 연속 실패 시 알림 (3-4시간)
- [ ] **I6. Graceful shutdown** — FastAPI lifespan 이벤트로 모니터/cleanup 스레드 정리 (2-3시간)
- [ ] **pot-provider, yt-dlp 버전 고정** — docker-compose.yml에 특정 태그, pyproject.toml에 버전 범위 제한 (1시간)

### Phase 4: 장기 안정화 (필요 시)

> 1년 무인 운영을 향해

- [ ] **N1. YouTube Data API v3 하이브리드** — yt-dlp 전면 장애 시 공식 API fallback (8-12시간)
- [ ] **N2. 런북 작성** — 장애 유형별 대응 절차 (2-3시간)
- [ ] **N6. pot-provider 장애 전파 테스트** — 사이드카 다운 시 시스템 동작 검증 (3-4시간)
- [ ] **N7. 장시간 방송 URL 만료 대응** — ffmpeg 입력 URL 재발급 메커니즘 (4-6시간)

---

## 기록 메타

- **작성일:** 2026-04-08
- **작성자:** 프랭크 (서기)
- **대상:** YouTube 라이브 모니터링 시스템 장애 방지 전략 — 8인 전문가 리뷰 통합
- **선행 문서:** 2026-04-06 쿠키 만료 사건 대응 기록, yt-dlp 통합 패턴 학습 메모

#장애방지 #아키텍처리뷰 #yt-dlp #모니터링 #운영안정성

### References

- [YouTube 쿠키 만료 대응 이력](../docs/history.md) — 2026-04-06 사건 기록
- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- TODO.md — P0/P1/P2 작업 목록
- 8인 전문가 리뷰 원본 (토니 스타크, 예원 제, 이상, 발루, 프랭크, 페이지, 파후, 초록문어)
