# TODO - yt-w 후속 작업

2026-04-06 세션 클로징에서 도출. 2026-04-08 8인 리뷰 반영하여 갱신.

## P0 (Critical)

- [ ] **Docker EXPOSE 포트 불일치 수정** — `Dockerfile`의 `EXPOSE 8088`을 `EXPOSE 8011`로 변경 (앱 실제 포트와 일치)
- [ ] **README CLI 진입점 오류 수정** — README가 `python main.py --add-channel`을 안내하지만 채널 관리 CLI는 `monitoring.py`에 있음
- [x] **cookie_helper 스레드 안전성** — `threading.Lock` 추가 완료 (2026-04-08)
- [x] **FFmpeg stderr 캡처** — `capture_output=True` + stderr 로깅 완료 (2026-04-08)
- [ ] **장애 알림 webhook** — 연속 N회 감지 실패 시 Telegram/Discord 알림 (8인 리뷰 ROI 1순위)

## P1 (Important)

- [x] **youtube_client + stream_downloader regression 테스트** — 18개 추가 완료 (2026-04-08)
- [ ] **Health check 엔드포인트** — `/api/health` + docker-compose healthcheck (P2→P1 승격, 8인 리뷰)
- [ ] **yt-dlp 응답 어댑터 DTO** — Pydantic 모델로 변환 레이어 추가, 키 변경 시 ValidationError (8인 리뷰)
- [ ] **MonitorStatus 확장** — 채널별 last_checked_at, consecutive_failures, last_error 추가 (8인 리뷰)
- [ ] **web_api.py 테스트 추가** — FastAPI TestClient 통합 테스트
- [ ] **cookie_helper.py 테스트 추가** — 쿠키 검증, 캐시 무효화, Docker 감지 단위 테스트
- [ ] **file_cleaner.py 테스트 추가** — 클린업 로직, 빈 디렉토리 삭제, 라이브 파일 보존
- [ ] **sanitize_url.py 테스트 추가** — 엣지 케이스 (쿼리 파라미터 없음, 비-YouTube URL 등)
- [ ] **다운로드 동시성 제한** — `web_api.py`에 `asyncio.Semaphore` 추가 (최대 2-3 동시 다운로드)
- [ ] **Graceful shutdown** — FastAPI lifespan 이벤트로 cleanup scheduler, monitor 스레드 정리
- [ ] **환경변수 문서화** — `.env.example` 추가

## P2 (Nice-to-have)

- [ ] **테마 토글 수정/제거** — `web/index.html`의 toggleTheme()이 동작하지 않음
- [ ] **다운로드 진행률 UI** — WebSocket/SSE로 다운로드 progress 표시
- [ ] **print() → Logger 교체** — `video_downloader.py` lines 156-182
- [ ] **Any 타입 제거** — `web_api.py`, `cookie_helper.py`, `channel_manager.py`에서 구체적 타입으로 교체
- [ ] **쿠키 파일 검증 개선** — `os.path.exists()` → `os.path.isfile()`
- [ ] **UI 에러 상태 추가** — 다운로드 실패 시 persistent 에러 + 재시도 옵션
- [ ] **YouTube Data API v3 하이브리드** — 라이브 감지를 공식 API로 분리, 단일 의존성 분산
- [ ] **런북(Runbook) 작성** — 장애 유형별 대응 절차 문서화
- [ ] **pot-provider 장애 전파 테스트** — 사이드카 다운 시 시스템 동작 검증
