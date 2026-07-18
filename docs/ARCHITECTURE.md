# 프로젝트 아키텍처

## 개요

YouTube 라이브 방송 자동 모니터링 + 일반 동영상 다운로드 시스템. 두 개의 장기 실행 프로세스(yt-monitor, yt-web)와 한 개의 사이드카(pot-provider)가 Docker Compose로 함께 동작한다.

- **yt-monitor**: `monitoring.py` 진입점. 채널마다 스레드를 띄워 라이브를 감지하고 ffmpeg로 녹화한다.
- **yt-web**: `main.py` 진입점. FastAPI로 채널 관리 / 모니터 상태 확인 / 일반 동영상 다운로드 / 병합 / 쿠키 검증 API를 제공하고 정적 웹 UI를 호스팅한다.
- **pot-provider**: bgutil PO Token 사이드카. yt-dlp가 YouTube 봇 감지를 우회할 PO Token을 받아 온다.

## 컨테이너 구성 (`docker-compose.yml`)

| 서비스 | 책임 | healthcheck | autoheal label |
|--------|------|-------------|----------------|
| `pot-provider` | PO Token 발급 | `node -e "fetch(/ping)"` | yes |
| `yt-monitor` | 채널 모니터 데몬 | `pgrep -f monitoring.py` | (autoheal 미지정 — `restart: unless-stopped`) |
| `yt-web` | FastAPI + 웹 UI | `wget /health` (IPv4 강제) | (autoheal 미지정) |
| `autoheal` | unhealthy 컨테이너 자동 재시작 | — | — |

`yt-monitor`와 `yt-web`은 모두 호스트의 Firefox 프로필을 `/app/firefox_profile`로 read-only 마운트해, yt-dlp가 `cookiesfrombrowser`로 최신 YouTube 쿠키를 직접 읽는다.

## 프로젝트 구조

```
yt-w/
├── src/yt_monitor/                      # 메인 패키지
│   ├── channels/                        # DTO + channels.json 저장소
│   │   ├── models.py
│   │   └── repository.py                # CRUD (RLock 직렬화)
│   ├── youtube/                         # 라이브 감지, cookie/PO-Token, URL 정규화
│   ├── monitoring/                      # 멀티 채널 service, 채널 worker, heartbeat
│   ├── media/                           # 다운로드, ffmpeg 명령, 병합·분할
│   ├── notifications/discord.py         # Discord webhook (urllib + rate-limit)
│   ├── maintenance/                     # retention 정리 + 백그라운드 스케줄러
│   ├── web/                             # FastAPI 웹 서버
│   │   ├── app.py                       # 앱 조립 + 라우트 등록 + 스케줄러 시작
│   │   ├── cli.py                       # 웹 서버 CLI
│   │   ├── schemas.py                   # Pydantic 요청/응답 스키마
│   │   ├── converters.py                # ChannelDTO → API dict 변환
│   │   └── routes/                      # 라우트 모듈
│   ├── cli.py                           # 모니터·다운로드·정리 CLI
│   └── logging.py                       # TimedRotatingFileHandler 로거
├── tests/                               # src 소유 경계를 따르는 pytest 테스트
│   ├── channels/                        # DTO, channels.json 저장소
│   ├── maintenance/                     # retention scheduler
│   ├── media/                           # 다운로드, ffmpeg, 병합·분할
│   ├── monitoring/                      # service, worker, cooldown
│   ├── notifications/                   # Discord webhook
│   ├── web/
│   │   ├── routes/                      # FastAPI 라우트별 계약
│   │   └── frontend/                    # 정적 UI와 Node 실행 회귀
│   └── youtube/                         # 라이브 감지, cookie, 실제 응답 fixture
├── web/
│   ├── index.html                       # Operator console markup
│   ├── app.css                          # Operator console styles
│   └── app.js                           # Operator console client logic
├── reviews/                             # 8인 리뷰 리포트 (히스토리)
├── main.py                              # 웹 서버 엔트리
├── monitoring.py                        # 모니터 데몬 + CLI 엔트리
├── docker-compose.yml
├── Dockerfile
└── channels.json                        # 채널 설정 (Compose volume)
```

## 핵심 흐름

### 1. 라이브 모니터링 (yt-monitor)

```
monitoring.py → yt_monitor.cli
  └─ monitoring.service.MultiChannelMonitor.start()
       ├─ ChannelManager.list_channels(enabled_only=True)
       ├─ for channel: ChannelMonitorThread(...).start()
       │    └─ _monitor_loop (per-channel daemon thread)
       │         ├─ YouTubeClient.check_if_live(url)
       │         │    └─ DetectionStrategy: /streams 탭 → 채널 페이지 (둘 다 extract_flat)
       │         │         └─ yt-dlp + cookie_options + PO Token
       │         └─ _handle_live_stream
       │              ├─ DiscordNotifier.notify_live_detected
       │              └─ StreamDownloader.download
       │                   ├─ NoSplit: yt-dlp 직접 다운로드
       │                   └─ Time/Size: yt-dlp로 stream URL 추출 → ffmpeg Popen + segment
       └─ SIGTERM handler (메인 스레드일 때만 등록)
```

`/live` 엔드포인트 탐지는 매 분 `extract_flat=False`로 전체 메타데이터를 끌어오는 호출이라 봇 감지 트리거가 됐다 — 제거됨. 두 탐지 방식 모두 `extract_flat="in_playlist"`로 가벼운 playlist 스캔만 한다.

### 2. 웹 API (yt-web)

```
main.py → web.cli → web.app.WebAPI → uvicorn
  ├─ register_*_routes (channels / monitor / video / cookies / merge / system / meta)
  └─ CleanupScheduler.start_in_background()
```

`yt-web`은 모니터를 직접 시작하거나 중지하지 않는다. 실제 자동 녹화는 `yt-monitor` 컨테이너의 `monitoring.py`가 담당한다.

`yt-monitor`는 공유 `logs/monitor_status.json`에 heartbeat를 기록한다. `/api/monitor/status`와 `/api/system/status`는 이 파일을 읽어 `yt-monitor` 데몬이 실제로 살아 있는지 표시한다. heartbeat가 없거나 오래되면 `is_running=false`로 본다. Docker socket을 `yt-web`에 마운트하지 않기 위한 의도적인 구조다.

`/api/monitor/start`와 `/api/monitor/stop`은 405를 반환한다. 운영자가 모니터 데몬을 제어해야 할 때는 Docker Compose에서 `yt-monitor` 컨테이너를 시작/중지한다.

`meta` 라우트는 `/`에서 `web/index.html`을 반환하고, `/static`으로 `web/` 디렉터리의 CSS/JS 정적 자산을 서빙한다.

### 3. 다운로드 라이프사이클 종료

`ChannelMonitorThread.stop()`은:
1. `is_running = False`로 모니터 루프 정지를 신호.
2. `downloader.stop()`을 호출해 진행 중인 ffmpeg subprocess를 `terminate → wait(5s) → kill` 순으로 정리.
3. 모니터 스레드를 `join(timeout=5)`.

이전에는 `subprocess.run`으로 ffmpeg를 블로킹 호출했기 때문에 stop이 5초 안에 반환되지 못하고 좀비를 남기는 문제가 있었다.

### 4. 쿠키 인증 우선순위

`youtube.cookies.get_cookie_options()`가 환경에 따라 분기:

1. **Docker + `/app/firefox_profile` 존재** → `cookiesfrombrowser=("firefox", profile, ...)` (호스트 Firefox 프로필 직접 사용)
2. **Docker + 프로필 없음 + `cookies.txt` 존재** → 임시본 `cookiefile` (yt-dlp가 매 요청 덮어써서 원본 보호)
3. **로컬** → `cookies.txt` 우선, 없으면 시스템 기본 브라우저(`firefox` 기본값)

PO Token Provider URL이 설정돼 있으면 `extractor_args`에 추가된다.

### 5. Discord 알림

이벤트별 메서드(`notify_live_detected`, `notify_download_complete`, ...)가 `DiscordNotifier.send()`를 통해 webhook으로 embed를 보낸다.

- Cloudflare가 기본 `python-urllib` UA를 차단하므로 `User-Agent: DiscordBot (...)` 강제.
- `X-RateLimit-Remaining`/`Retry-After` 헤더를 읽어 자체 슬립.
- 봇 감지(`YouTubeAuthError`) 알림은 `AlertCooldown`(기본 30분)으로 폭주 차단.

## 동시성 / 스레드 모델

| 컴포넌트 | 동시성 보호 |
|----------|-------------|
| `ChannelManager` mutating 메서드 | `RLock` (read-modify-write 직렬화) |
| `StreamDownloader._proc` | `Lock` (set/clear/stop 보호) |
| `CookieValidator` 캐시 | `Lock` |
| `DiscordNotifier` rate-limit | `Lock` |
| `ChannelMonitorThread.is_downloading` | `bool` (단일 라이터 가정) |

`ChannelManager`의 file lock은 단일 프로세스 내 한정. `yt-web`은 `channels.json`을 수정하고, `yt-monitor`는 시작 시 설정을 읽어 실제 감시 스레드를 만든다. 실행 중인 데몬이 이미 띄운 스레드 수는 `monitor_status.json`의 `active_channels`가 기준이다.

## 테스트 전략

테스트는 파일 수나 assertion 수가 아니라 실제 회귀 경계를 기준으로 유지한다. 생성자
인자가 그대로 대입되는지, 같은 분기를 다른 값으로 반복하는지, 다른 테스트가 이미 같은
계약을 더 강하게 검증하는지는 별도 테스트로 두지 않는다.

| 보호할 경계 | 소유 테스트 | 필요한 이유 |
|------------|-------------|-------------|
| 채널/전역 설정의 원자적 갱신 | `tests/channels/test_repository.py`, `tests/web/routes/test_channels.py` | 유효하지 않은 update나 중복 URL이 예외만 내고 `channels.json`을 이미 오염시키지 않도록, 검증 후 저장 순서와 API 400 계약을 함께 고정한다. |
| yt-dlp 라이브 메타데이터와 `/live` fallback | `tests/youtube/test_client.py`, `tests/youtube/test_client_fixtures.py` | `extract_flat` 응답은 `is_live` 대신 `live_status`를 주기도 하므로 실제 응답 형태와 탐지 순서를 함께 고정한다. |
| cookie source 선택과 임시본 수명 | `tests/youtube/test_cookies.py` | Docker Firefox profile, `cookies.txt`, browser fallback의 우선순위와 갱신된 임시 cookie 파일의 교체/정리를 보장한다. |
| ffmpeg HTTP header와 입력 순서 | `tests/media/test_ffmpeg.py`, `tests/media/test_stream_download.py` | YouTube HLS 요청에서 header가 빠지거나 `-i` 뒤에 놓이면 403이 발생하므로 순수 command와 downloader 전달 경계를 각각 한 번 검증한다. |
| 병합·분할 job 상태와 실패 정리 | `tests/media/test_merge.py`, `tests/media/test_split.py`, `tests/web/routes/test_merge.py`, `tests/web/routes/test_split.py` | queued/running/done/failed/cancelled 전이, concat 임시 파일, partial output, output reservation과 다운로드 준비 상태는 서로 다른 실패 경계다. |
| 알림 payload와 재전송 억제 | `tests/notifications/test_discord.py`, `tests/web/routes/test_cookies.py`, `tests/monitoring/test_worker.py` | webhook body, 호출 시점, cooldown은 서로 다른 경계이며 하나라도 빠지면 운영 알림이 누락되거나 폭주한다. |
| 설정 저장 동시성 | `tests/channels/test_repository.py::test_concurrent_add_no_lost_updates` | FastAPI 요청의 read-modify-write가 겹쳐도 `channels.json` 항목이 유실되지 않아야 한다. |
| retention 삭제와 live 보존 | `tests/maintenance/test_cleanup.py`, `tests/maintenance/test_scheduler.py` | 오래된 일반 파일만 지우고 `live/`, 최근 파일, dry-run 대상을 보존하며 개별 삭제 실패가 나머지 정리를 막지 않아야 한다. |
| heartbeat 신뢰성과 operator 상태 | `tests/monitoring/test_status.py`, `tests/web/routes/test_monitor.py`, `tests/web/routes/test_system.py` | stale 경계, 손상된 JSON, 잘못된 field type, 설정 기반 fallback과 disk/download 집계를 분리해 검증한다. |
| monitor thread 동시성·종료 | `tests/monitoring/test_service.py`, `tests/monitoring/test_worker.py` | 웹 요청과 감시 loop가 같은 thread map을 다루며, Docker SIGTERM과 background start도 별도 런타임 경계다. |
| 사용자 화면의 병합·분할 동작 | `tests/web/frontend/` | 별도 frontend test runner가 없으므로 Node로 실제 함수를 실행하고, markup-only 계약은 필요한 DOM selector만 확인한다. |

Node는 production image의 필수 runtime이므로 frontend 테스트에서 찾을 수 없으면 skip하지 않고 실패한다. FastAPI route 테스트는 실제 cleanup daemon을 시작하지 않아 HTTP test harness와 background thread의 생명주기를 분리한다.

테스트 실행:

```bash
uv run pytest          # 전체
uv run pytest -v       # 상세
uv run pytest tests/media/test_stream_download.py -k stop  # 특정
```

## 운영 주의

- **Firefox 프로필 마운트**가 read-only인지 확인 (`docker-compose.yml`의 `:ro`). yt-dlp가 cookiesdb를 쓰면 SQLite lock으로 호스트 Firefox와 충돌.
- **pot-provider hang**은 두 단계 안전망으로 대응: 컨테이너 healthcheck → autoheal 사이드카가 강제 재시작. 그래도 봇 감지가 발생하면 `notify_bot_detection` Discord 알림.
- **ffmpeg 좀비**는 `downloader.stop()`이 막지만, kill까지 7초가 걸리므로 docker stop 시 `--time` 충분히(>10s) 줄 것.

## 변경 이력

자세한 사건/사고 노트는 `docs/history.md`와 `reviews/`를 참고한다.
