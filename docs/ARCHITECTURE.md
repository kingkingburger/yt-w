# 프로젝트 아키텍처

## 개요

YouTube 라이브 방송 자동 모니터링 + 일반 동영상 다운로드 시스템. 두 개의 장기 실행 프로세스(yt-monitor, yt-web)와 한 개의 사이드카(pot-provider)가 Docker Compose로 함께 동작한다.

- **yt-monitor**: `monitoring.py` 진입점. 채널마다 스레드를 띄워 라이브를 감지하고 ffmpeg로 녹화한다.
- **yt-web**: `main.py` 진입점. FastAPI로 채널 관리 / 모니터 제어 / 일반 동영상 다운로드 / 쿠키 검증 API를 제공하고 정적 웹 UI를 호스팅한다.
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
│   ├── multi_channel_monitor.py         # 멀티 채널 모니터 + 채널별 스레드
│   ├── channel_manager.py               # channels.json CRUD (RLock 직렬화)
│   ├── youtube_client.py                # 라이브 감지 (DetectionStrategy 2종)
│   ├── stream_downloader.py             # 라이브 녹화 (yt-dlp + ffmpeg Popen)
│   ├── video_downloader.py              # 일반 동영상 다운로드
│   ├── ffmpeg_command.py                # ffmpeg 세그먼트 커맨드 빌더 (순수)
│   ├── split_strategy.py                # 시간/크기/없음 분할 전략
│   ├── file_cleaner.py                  # retention 기반 정리
│   ├── discord_notifier.py              # Discord webhook (urllib + rate-limit)
│   ├── alert_cooldown.py                # 쿨다운 값 객체 (알림 폭주 방지)
│   ├── cookie_options.py                # yt-dlp cookie/PO-Token 옵션 빌더
│   ├── cookie_validator.py              # 쿠키 유효성 검증 + 캐시
│   ├── cookie_browser.py                # 브라우저에서 쿠키 추출
│   ├── logger.py                        # TimedRotatingFileHandler 로거
│   ├── web_api/                         # FastAPI 웹 서버
│   │   ├── api.py                       # 앱 조립 + 라우트 등록 + 스케줄러 시작
│   │   ├── state.py                     # 실행 중 모니터 상태 컨테이너
│   │   ├── schemas.py                   # Pydantic 요청/응답 스키마
│   │   ├── dto_converters.py            # internal DTO → dict
│   │   ├── cleanup_scheduler.py         # 백그라운드 자동 정리 스케줄러
│   │   └── routes/                      # 라우트 모듈 (channels/monitor/video/cookies/cleanup/meta)
│   └── util/sanitize_url.py             # URL 정규화
├── test/                                # pytest 단위/회귀 테스트
├── web/index.html                       # Tailwind 웹 UI
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
monitoring.py
  └─ MultiChannelMonitor.start()
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
main.py → uvicorn → web_api.api.create_app()
  ├─ MonitorState 생성 (라우트 간 공유)
  ├─ register_*_routes (channels / monitor / video / cookies / cleanup / meta)
  └─ CleanupScheduler.start_in_background()
```

`/api/monitor/start`는 `MultiChannelMonitor.start()`를 데몬 스레드에서 호출한다. 이 경우 `MultiChannelMonitor`는 `signal.signal()` 등록을 건너뛴다(메인 스레드가 아니므로 `ValueError` 회피). 컨테이너의 SIGTERM 처리는 호스트 프로세스(uvicorn)가 담당한다.

### 3. 다운로드 라이프사이클 종료

`ChannelMonitorThread.stop()`은:
1. `is_running = False`로 모니터 루프 정지를 신호.
2. `downloader.stop()`을 호출해 진행 중인 ffmpeg subprocess를 `terminate → wait(5s) → kill` 순으로 정리.
3. 모니터 스레드를 `join(timeout=5)`.

이전에는 `subprocess.run`으로 ffmpeg를 블로킹 호출했기 때문에 stop이 5초 안에 반환되지 못하고 좀비를 남기는 문제가 있었다.

### 4. 쿠키 인증 우선순위

`cookie_options.get_cookie_options()`가 환경에 따라 분기:

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

`ChannelManager`의 file lock은 단일 프로세스 내 한정. yt-monitor 컨테이너는 `channels.json`을 read-only로만 쓰므로 yt-web의 RLock으로 충분하다.

## 테스트 전략

- **단위**: 각 모듈 독립 테스트 (`test/test_*.py`).
- **회귀**: `test/test_regression_20260408.py`에 과거 P0 버그(`is_live`/`live_status` 누락, ffmpeg HTTP 헤더 누락) 보존.
- **알림**: `test_discord_notifier.py` + `test_cookie_notifications.py`에서 webhook patch 대상은 `urllib.request.urlopen`이 아니라 모듈 내 import 경로.
- **동시성**: `test_channel_manager.py::test_concurrent_add_no_lost_updates` — 10개 스레드 동시 add 후 항목 유실 없음.
- **라이프사이클**: `test_multi_channel_monitor.py::TestMultiChannelMonitorBackgroundThread` — 백그라운드 스레드에서 start() 호출 시 SIGTERM 등록을 건너뛰는지 검증.

테스트 실행:

```bash
uv run pytest          # 전체
uv run pytest -v       # 상세
uv run pytest test/test_stream_downloader.py -k stop  # 특정
```

## 운영 주의

- **Firefox 프로필 마운트**가 read-only인지 확인 (`docker-compose.yml`의 `:ro`). yt-dlp가 cookiesdb를 쓰면 SQLite lock으로 호스트 Firefox와 충돌.
- **pot-provider hang**은 두 단계 안전망으로 대응: 컨테이너 healthcheck → autoheal 사이드카가 강제 재시작. 그래도 봇 감지가 발생하면 `notify_bot_detection` Discord 알림.
- **ffmpeg 좀비**는 `downloader.stop()`이 막지만, kill까지 7초가 걸리므로 docker stop 시 `--time` 충분히(>10s) 줄 것.

## 변경 이력

자세한 사건/사고 노트는 `docs/history.md`와 `reviews/`를 참고한다.
