# 프로젝트 아키텍처

## 개요

YouTube 라이브 방송 자동 모니터링, 일반 동영상 다운로드, 영상 병합·분할,
단일 사용자용 YouTube 비공개 업로드 시스템.
두 개의 애플리케이션 프로세스(`yt-monitor`, `yt-web`), PO Token 사이드카
(`pot-provider`), health 보조 서비스(`autoheal`)가 Docker Compose로 함께 동작한다.

- **yt-monitor**: `monitoring.py` 진입점. 채널마다 스레드를 띄워 라이브를 감지하고 ffmpeg로 녹화한다.
- **yt-web**: `main.py` 진입점. FastAPI로 채널 관리 / 모니터 상태 확인 / 일반 동영상 다운로드 / 파일 병합·분할 / 쿠키 검증 / Google OAuth / YouTube 비공개 업로드 API를 제공하고 정적 웹 UI를 호스팅한다.
- **pot-provider**: bgutil PO Token 사이드카. yt-dlp가 YouTube 봇 감지를 우회할 PO Token을 받아 온다.

## 컨테이너 구성 (`docker-compose.yml`)

| 서비스 | 책임 | healthcheck | autoheal label |
|--------|------|-------------|----------------|
| `pot-provider` | PO Token 발급 | `node -e "fetch(/ping)"` | yes |
| `yt-monitor` | 채널 모니터 데몬 | `pgrep -f monitoring.py` | (autoheal 미지정 — `restart: unless-stopped`) |
| `yt-web` | FastAPI + 웹 UI | `wget /health` (IPv4 강제) | (autoheal 미지정) |
| `autoheal` | unhealthy 컨테이너 자동 재시작 | — | — |

`yt-monitor`와 `yt-web`은 모두 호스트의 Firefox 프로필을 `/app/firefox_profile`로 read-only 마운트해, yt-dlp가 `cookiesfrombrowser`로 최신 YouTube 쿠키를 직접 읽는다.
`autoheal=true` label은 현재 `pot-provider`에만 있으며, `yt-monitor`와 `yt-web`은
`restart: unless-stopped` 정책만 사용한다.

OAuth client JSON은 YouTube OAuth 전용인 host의 `./secrets`를 `/run/secrets:ro`로
bind mount해 `yt-web`만 읽는다. 다른 서비스의 비밀은 이 디렉터리에 두지 않는다.
발급된 OAuth token은 `yt-web`에만 연결된 `youtube-oauth-data` named volume의
`/app/data/youtube-oauth/token.json`에 저장한다. `yt-web` port는
`127.0.0.1:8088`에만 publish하며, OAuth callback도
`http://localhost:8088/api/youtube/oauth/callback`으로 고정한다.
로컬 `uv run python main.py` 실행도 기본적으로 `127.0.0.1`에만 bind한다. Compose는
컨테이너 내부 통신을 위해 `YT_WEB_HOST=0.0.0.0`을 명시하되 host publish 경계는
loopback으로 유지한다.

## 프로젝트 구조

```
yt-w/
├── src/yt_monitor/                      # 메인 패키지
│   ├── channels/                        # DTO + channels.json 저장소
│   │   ├── models.py
│   │   └── repository.py                # CRUD (RLock 직렬화)
│   ├── youtube/                         # 라이브 감지, cookie/PO-Token, OAuth/upload
│   ├── monitoring/                      # 멀티 채널 service, 채널 worker, heartbeat
│   ├── media/                           # 다운로드, ffmpeg 명령, 병합·분할
│   ├── notifications/discord.py         # Discord webhook (urllib + rate-limit)
│   ├── maintenance/                     # retention 정리 + 백그라운드 스케줄러
│   ├── web/                             # FastAPI 웹 서버
│   │   ├── app.py                       # 앱 조립 + 라우트 등록 + 스케줄러 시작
│   │   ├── entrypoint.py                # 웹 서버 실행 진입점
│   │   ├── schemas.py                   # Pydantic 요청/응답 스키마
│   │   ├── converters.py                # ChannelDTO → API dict 변환
│   │   └── routes/                      # 채널/상태/미디어/OAuth/upload 라우트
│   ├── entrypoint.py                    # 모니터 데몬 실행 진입점
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
│   ├── youtube/                         # 라이브 감지, cookie, 실제 응답 fixture
│   └── test_logging.py                  # 일별 회전 로거
├── web/
│   ├── index.html                       # Operator console markup
│   ├── app.css                          # Operator console styles
│   ├── app.js                           # Operator console client logic
│   ├── merge_output_name.js             # 기본 병합 파일명 계산
│   └── merge_download_directory.js      # PC 저장 폴더 기억/쓰기
├── scripts/                             # Windows 시작/휴지통 helper와 pre-commit 도구
├── docs/                                # 이 문서, v0 개발 이력, 실측 검증 리포트(verify/)
├── main.py                              # 웹 서버 엔트리
├── monitoring.py                        # 모니터 데몬 엔트리
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml                       # 의존성과 pytest 설정
├── uv.lock                              # 고정 의존성
└── channels.json                        # 채널 설정 (Compose volume)
```

## 핵심 흐름

### 1. 라이브 모니터링 (yt-monitor)

```
monitoring.py → yt_monitor.entrypoint
  └─ monitoring.service.MultiChannelMonitor.start()
       ├─ ChannelManager.list_channels(enabled_only=True)
       ├─ for channel: ChannelMonitorThread(...).start()
       │    └─ _monitor_loop (per-channel daemon thread)
       │         ├─ YouTubeClient.check_if_live(url)
       │         │    └─ DetectionStrategy: /streams 탭 → 채널 페이지 → /live
       │         │         (세 방식 모두 extract_flat="in_playlist")
       │         │         └─ yt-dlp + cookie_options + PO Token
       │         └─ _handle_live_stream
       │              ├─ DiscordNotifier.notify_live_detected
       │              └─ StreamDownloader.download
       │                   ├─ NoSplit: yt-dlp 직접 다운로드
       │                   └─ Time/Size: yt-dlp로 stream URL 추출 → ffmpeg Popen + segment
       │         └─ 방송 종료 감지
       │              └─ 완료 파일을 이름순 병합한 뒤 host recycle 요청을 원자적으로 기록
       ├─ _sync_channel_monitors()로 channels.json 변경 반영
       └─ SIGTERM handler (메인 스레드일 때만 등록)
```

세 탐지 방식은 모두 `extract_flat="in_playlist"`와 `ignoreerrors=True`를 사용한다.
`/streams`와 채널 페이지에서 라이브를 찾지 못하면 `/live`를 마지막 fallback으로
조회한다. 각 응답은 `is_live=True` 또는 `live_status="is_live"`인 현재 항목만
`LiveStreamInfo`로 변환한다. 세 방식 중 인증/봇 감지 오류가 하나라도 발생했고
라이브를 찾지 못한 경우 `YouTubeAuthError`를 올려 알림 경로로 보낸다.

`MultiChannelMonitor`의 메인 루프는 매초 `channels.json`을 다시 읽는다. 활성화된 채널은
worker를 추가하고, 비활성화·삭제된 채널은 중지하며, 채널 이름·URL·다운로드 포맷 또는
전역 설정이 바뀐 worker는 재시작한다. 따라서 채널 관리 API 변경은 `yt-monitor`
컨테이너 재시작 없이 반영된다.

분할 다운로드의 ffmpeg가 종료돼도 YouTube가 같은 URL을 계속 라이브로 표시할 수 있다.
따라서 `ChannelMonitorThread`는 같은 방송 URL에서 성공적으로 완료된 파일을 누적하고,
`check_if_live()`가 비라이브를 반환하거나 새 방송 URL이 감지될 때 한 번만 자동 병합한다.
실패한 다운로드가 남긴 partial 파일은 자동 병합 대상에 포함하지 않는다.
병합이 성공한 경우에만 입력 상대 경로와 결과 경로를
`downloads/.recycle-requests/*.json`에 원자적으로 기록한다. Windows host의
`scripts/windows-recycle-helper.ps1`은 `merged/` 결과 파일이 존재하고 source가
`live/` 아래에 있는지 검증한 뒤 Windows 휴지통 API로 원본을 이동한다. helper가
중지됐거나 요청 처리에 실패하면 manifest와 원본을 그대로 유지한다.

`scripts/install-windows-recycle-task.ps1`은 helper를 현재 Windows 사용자의 Scheduled
Task로 등록한다. Task는 매일 현지 시각 오전 3시에 helper를 `-Once`로 실행하고,
설치 직후나 Docker 시작 시에는 실행하지 않는다. 예약 시각을 놓친 경우에는 다음 사용
가능 시점에 한 번 실행하며, 한 실행은 최대 10분으로 제한하고 중복 인스턴스는 무시한다.
Windows 휴지통의 사용자 소유권을 유지하기 위해 `SYSTEM`
계정이나 Docker 컨테이너에서는 실행하지 않는다. Task action은 GUI형 `wscript.exe`로
`scripts/run-windows-recycle-helper-hidden.vbs`를 실행하고, 이 launcher가 PowerShell을
window style `0`으로 시작해 console을 표시하지 않는다.
`scripts/start-windows.ps1`은 Task가 없거나 비활성 상태면 경고만 출력하고 helper를
직접 시작하지 않는다.

`downloads/.trash/`는 이전 버전에서 만든 복구 자료다. 새 병합은 이 경로를 사용하지
않으며 기존 자료도 자동으로 Windows 휴지통에 이관하지 않는다. `.trash/`와
`.recycle-requests/`는 파일 목록과 retention 정리 대상에서 제외한다.

### 2. 웹 API (yt-web)

```
main.py → web.entrypoint → web.app.WebAPI → uvicorn
  ├─ YouTubeOAuthManager
  ├─ YouTubeUploadJobManager
  ├─ register_*_routes
  │    (channels / monitor / video / cookies / merge / split / youtube_upload / system / meta)
  └─ CleanupScheduler.start()
```

`yt-web`은 모니터를 직접 시작하거나 중지하지 않는다. 실제 자동 녹화는 `yt-monitor` 컨테이너의 `monitoring.py`가 담당한다.

`yt-monitor`는 공유 `logs/monitor_status.json`에 heartbeat를 기록한다. `/api/monitor/status`와 `/api/system/status`는 이 파일을 읽어 `yt-monitor` 데몬이 실제로 살아 있는지 표시한다. heartbeat가 없거나 오래되면 `is_running=false`로 본다. Docker socket을 `yt-web`에 마운트하지 않기 위한 의도적인 구조다.

`/api/monitor/start`와 `/api/monitor/stop`은 405를 반환한다. 운영자가 모니터 데몬을 제어해야 할 때는 Docker Compose에서 `yt-monitor` 컨테이너를 시작/중지한다.

`meta` 라우트는 `/`에서 `web/index.html`을 반환하고, `/static`으로 `web/` 디렉터리의 CSS/JS 정적 자산을 서빙한다.

#### API 소유권

| 라우트 모듈 | 주요 경로 | 책임 |
|-------------|-----------|------|
| `channels.py` | `/api/channels` | 채널 조회·추가·수정·삭제와 URL 정규화 |
| `monitor.py` | `/api/monitor/status` | heartbeat 기반 모니터 상태 조회 |
| `video.py` | `/api/video/info`, `/api/download` | 일반 영상 정보 조회와 다운로드 |
| `cookies.py` | `/api/cookie/status` | 실제 yt-dlp 호출 기반 쿠키 검증 |
| `merge.py` | `/api/files`, `/api/merge/*` | 미디어 목록·삭제와 병합 job |
| `split.py` | `/api/split/*` | 업로드, 분할 job, 결과 다운로드 |
| `youtube_upload.py` | `/api/youtube/oauth/*`, `/api/youtube/uploads*` | Google OAuth 연결과 YouTube 비공개 업로드 job |
| `system.py` | `/api/system/*` | 디스크·다운로드·Discord·모니터 통합 상태 |
| `meta.py` | `/`, `/health`, `/static` | 웹 UI, 정적 파일, healthcheck |

### 3. YouTube OAuth와 비공개 업로드 (yt-web)

OAuth와 upload는 다운로드용 Firefox cookie/PO Token 경로를 재사용하지 않는다.
`YouTubeOAuthManager`가 OAuth Web client JSON과 token 파일을 소유하고,
`YouTubeUploadJobManager`가 기존 다운로드 영상을 YouTube Data API의 resumable upload로
전송한다.

```
브라우저
  ├─ POST /api/youtube/oauth/start
  │    └─ Google OAuth 동의
  │         └─ GET /api/youtube/oauth/callback
  │              └─ YouTubeOAuthManager → token.json
  └─ POST /api/youtube/uploads
       └─ YouTubeUploadJobManager
            └─ videos.insert(privacyStatus=private, resumable=True)
                 └─ progress / done / failed / cancelled
```

OAuth route 계약:

| 메서드와 경로 | 책임 |
|----------------|------|
| `GET /api/youtube/oauth/status` | client 설정 여부와 계정 연결 상태 조회 |
| `POST /api/youtube/oauth/start` | Google 승인 URL 생성 |
| `GET /api/youtube/oauth/callback` | authorization code를 token으로 교환하고 저장 |
| `DELETE /api/youtube/oauth/connection` | 저장된 OAuth 연결 제거 |

Upload route 계약:

| 메서드와 경로 | 책임 |
|----------------|------|
| `POST /api/youtube/uploads` | 기존 영상의 비공개 upload job 제출 |
| `GET /api/youtube/uploads` | 현재 프로세스의 job 목록 조회 |
| `GET /api/youtube/uploads/{job_id}` | 개별 job 상태와 진행률 조회 |
| `POST /api/youtube/uploads/{job_id}/cancel` | queued/running job 취소 요청 |

업로드 source는 `downloads/` 아래의 `merged`, `split`, `uploads`, `web_downloads`
디렉터리에 있는 video extension 파일만 허용한다. `live`, hidden 경로, audio-only 파일,
절대경로·상위경로·외부 symlink는 manager에서 거절한다. 같은 프로세스에서 병합 또는
분할 중인 출력 경로도 route에서 `409`로 거절한다. OAuth start/disconnect와 upload
submit/cancel 같은 쓰기 route는 `X-YT-Monitor-Request: 1`을 요구하고, callback은
10분 TTL의 one-time state와 `HttpOnly; SameSite=Lax` cookie를 함께 검증한다.

MVP의 `privacyStatus`는 `private`로 고정한다. resumable upload는 프로세스가 살아 있는
동안 chunk 진행률과 네트워크 재시도를 제공하지만 resumable session과 job 목록은
영속화하지 않는다. 따라서 `yt-web` 컨테이너가 재시작되면 queued/running job을 자동
복구하거나 이어서 실행하지 않는다. token named volume은 컨테이너 재생성과 별개로
유지되므로 계정 연결과 job 복구는 서로 다른 수명주기다. running job 취소는 현재
8 MiB chunk가 끝난 뒤 반영하며, 이미 생성된 원격 YouTube 영상은 자동 삭제하지 않는다.

`./secrets` bind mount와 `youtube-oauth-data` volume은 `yt-monitor`에 연결하지 않는다.
`docker compose down -v`는 token volume도 삭제하므로 다음 사용 시 OAuth 연결이 다시
필요하다. 이 API는 loopback에서 한 명이 사용하는 운영 UI를 전제로 하며 외부 공개나
다중 계정은 현재 신뢰 경계 밖이다.

### 4. 다운로드 라이프사이클 종료

`ChannelMonitorThread.stop()`은:
1. `is_running = False`로 모니터 루프 정지를 신호.
2. `downloader.stop()`을 호출해 진행 중인 ffmpeg subprocess를 `terminate → wait(5s) → kill` 순으로 정리.
3. 모니터 스레드를 `join(timeout=5)`.

이전에는 `subprocess.run`으로 ffmpeg를 블로킹 호출했기 때문에 stop이 5초 안에 반환되지 못하고 좀비를 남기는 문제가 있었다.

### 5. 쿠키 인증 우선순위

`youtube.cookies.get_cookie_options()`가 환경에 따라 분기:

1. **Docker + `/app/firefox_profile` 존재** → `cookiesfrombrowser=("firefox", profile, ...)` (호스트 Firefox 프로필 직접 사용)
2. **Docker + 프로필 없음** → 브라우저 쿠키 없이 실행
3. **로컬** → 시스템 브라우저 쿠키 사용 (`YT_COOKIE_BROWSER`, 기본값 `firefox`)

PO Token Provider URL이 설정돼 있으면 `extractor_args`에 추가된다. PO Token은 봇 감지 대응 수단이며 브라우저의 로그인 권한을 대신하지 않는다.

### 6. Discord 알림

이벤트별 메서드(`notify_live_detected`, `notify_download_complete`, ...)가 `DiscordNotifier.send()`를 통해 webhook으로 embed를 보낸다.

- Cloudflare가 기본 `python-urllib` UA를 차단하므로 `User-Agent: DiscordBot (...)` 강제.
- `X-RateLimit-Remaining`/`Retry-After` 헤더를 읽어 자체 슬립.
- 봇 감지(`YouTubeAuthError`) 알림은 `AlertCooldown`(기본 30분)으로 폭주 차단.

## 운영 콘솔 시각·접근성 계약

`web/index.html`은 의미와 입력 요소, `web/app.js`는 화면 상태, `web/app.css`는 시각
표현을 소유한다. 콘솔은 방송 장비 랙의 정보 구조에 인디 스튜디오 포스터의 색과
오프셋 인쇄 질감을 결합한다. `--action`은 선택·포커스, `--acid`는 실행과 체크의
강조, `--hot`은 녹화·경고에만 사용해 장식 색이 상태 의미를 덮지 않게 한다.

선택 컨트롤은 다음 계약을 지킨다.

- `.selection-control` 안의 실제 checkbox/radio `input`을 투명하게 남겨 클릭, 키보드,
  `checked`/`indeterminate`, 접근성 트리 동작을 브라우저 표준에 맡긴다.
- 시각 표시는 형제 `.selection-mark`가 담당한다. 체크박스는
  `--studio-check-shape`의 굵은 실루엣과 비대칭 외곽, 라디오는 원형 마크를 사용한다.
- 병합 파일·그룹 선택, YouTube 업로드 source, 아동용 설정이 같은 컨트롤 계열을
  공유한다. 완료 화면의 큰 체크는 장식 요소이므로 `aria-hidden="true"`로 둔다.
- `:focus-visible`은 선택 여부와 관계없이 외곽 포커스 링을 남기고,
  `prefers-reduced-motion: reduce`에서는 체크를 포함한 위치 애니메이션을 사실상 끈다.

`tests/web/frontend/test_split.py`가 checkbox/radio/indeterminate 스타일 계약을,
`tests/web/frontend/test_youtube_upload.py`가 아동용 checkbox의 커스텀 마크와 실제
input 보존을 검증한다. 외부 이미지나 JavaScript UI 의존성은 추가하지 않는다.

## 동시성 / 스레드 모델

| 컴포넌트 | 동시성 보호 |
|----------|-------------|
| `ChannelManager` mutating 메서드 | `RLock` (read-modify-write 직렬화) |
| `MultiChannelMonitor._monitor_threads` | `Lock` (worker map 추가·중지·재시작 직렬화) |
| `StreamDownloader._proc` | `Lock` (set/clear/stop 보호) |
| `CookieValidator` 캐시 | `Lock` |
| `DiscordNotifier` rate-limit | `Lock` |
| `ChannelMonitorThread.is_downloading` | `bool` (단일 라이터 가정) |
| `MergeJobManager`, `SplitJobManager` | `Lock` (job/process/output 상태 보호) |
| `YouTubeOAuthManager` | `Lock` (one-time OAuth state 생성·소비 보호) |
| `YouTubeUploadJobManager` | `Lock` (job/progress/cancel 상태 보호) |
| 병합 파일 목록 캐시 | `asyncio.Lock` (동시 cache miss 스캔 1회) |
| 분할 업로드 경로 예약 | `asyncio.Lock` + 예약 경로 set |

`ChannelManager`의 lock은 단일 프로세스 내 한정이다. `yt-web`이 `channels.json`을
수정하고 `yt-monitor`가 같은 파일을 매초 다시 읽지만, 파일 저장은 임시 파일 작성 후
`os.replace()`로 교체해 reader가 중간 JSON을 보지 않도록 한다. 실행 중인 worker 수는
`monitor_status.json`의 `active_channels`가 운영 화면의 기준이다.

## 테스트 전략

테스트는 파일 수나 assertion 수가 아니라 실제 회귀 경계를 기준으로 유지한다. 생성자
인자가 그대로 대입되는지, 같은 분기를 다른 값으로 반복하는지, 다른 테스트가 이미 같은
계약을 더 강하게 검증하는지는 별도 테스트로 두지 않는다.

| 보호할 경계 | 소유 테스트 | 필요한 이유 |
|------------|-------------|-------------|
| 채널/전역 설정의 원자적 갱신 | `tests/channels/test_repository.py`, `tests/web/routes/test_channels.py` | 유효하지 않은 update나 중복 URL이 예외만 내고 `channels.json`을 이미 오염시키지 않도록, 검증 후 저장 순서와 API 400 계약을 함께 고정한다. |
| yt-dlp 라이브 메타데이터와 `/live` fallback | `tests/youtube/test_client.py`, `tests/youtube/test_client_fixtures.py` | `extract_flat` 응답은 `is_live` 대신 `live_status`를 주기도 하므로 실제 응답 형태와 탐지 순서를 함께 고정한다. |
| 브라우저 cookie source 선택 | `tests/youtube/test_cookies.py` | Docker Firefox profile, 프로필 없는 Docker, 로컬 기본·사용자 지정 브라우저의 인증 옵션을 보장한다. |
| ffmpeg HTTP header와 입력 순서 | `tests/media/test_ffmpeg.py`, `tests/media/test_stream_download.py` | YouTube HLS 요청에서 header가 빠지거나 `-i` 뒤에 놓이면 403이 발생하므로 순수 command와 downloader 전달 경계를 각각 한 번 검증한다. |
| 병합·분할 job 상태와 실패 정리 | `tests/media/test_merge.py`, `tests/media/test_split.py`, `tests/web/routes/test_merge.py`, `tests/web/routes/test_split.py` | queued/running/done/failed/cancelled 전이, concat 임시 파일, partial output, output reservation과 다운로드 준비 상태는 서로 다른 실패 경계다. |
| 알림 payload와 재전송 억제 | `tests/notifications/test_discord.py`, `tests/web/routes/test_cookies.py`, `tests/monitoring/test_worker.py` | webhook body, 호출 시점, cooldown은 서로 다른 경계이며 하나라도 빠지면 운영 알림이 누락되거나 폭주한다. |
| 설정 저장 동시성 | `tests/channels/test_repository.py::test_concurrent_add_no_lost_updates` | FastAPI 요청의 read-modify-write가 겹쳐도 `channels.json` 항목이 유실되지 않아야 한다. |
| retention 삭제와 live 보존 | `tests/maintenance/test_cleanup.py`, `tests/maintenance/test_scheduler.py` | 오래된 일반 파일만 지우고 `live/`, 최근 파일, dry-run 대상을 보존하며 개별 삭제 실패가 나머지 정리를 막지 않아야 한다. |
| heartbeat 신뢰성과 operator 상태 | `tests/monitoring/test_status.py`, `tests/web/routes/test_monitor.py`, `tests/web/routes/test_system.py` | stale 경계, 손상된 JSON, 잘못된 field type, 설정 기반 fallback과 disk/download 집계를 분리해 검증한다. |
| monitor thread 동시성·종료 | `tests/monitoring/test_service.py`, `tests/monitoring/test_worker.py` | 웹 요청과 감시 loop가 같은 thread map을 다루며, Docker SIGTERM과 background start도 별도 런타임 경계다. |
| 사용자 화면의 병합·분할 동작 | `tests/web/frontend/` | 별도 frontend test runner가 없으므로 Node로 실제 함수를 실행하고, markup-only 계약은 필요한 DOM selector만 확인한다. |
| OAuth token 경계와 비공개 upload job | `tests/youtube/`, `tests/web/routes/`, `tests/web/frontend/` | OAuth 연결 상태·callback, token 저장, source path 검증, private metadata, progress/cancel과 재시작 비영속 계약을 분리해 고정한다. |

Node는 production image의 필수 runtime이므로 frontend 테스트에서 찾을 수 없으면 skip하지 않고 실패한다. FastAPI route 테스트는 실제 cleanup daemon을 시작하지 않아 HTTP test harness와 background thread의 생명주기를 분리한다.

`web/`이나 `tests/web/frontend/`가 stage되면 pre-commit의 `frontend-regression`
hook이 이 테스트를 실행한다(약 3초). 콘솔 리디자인 4개 커밋이 `web/`만 바꾸는 동안
6개가 조용히 깨진 적이 있어, 같은 유입 경로를 커밋 시점에 막는다. 이 경계는 CI가
아니라 hook이 지키므로 `--no-verify`로 우회하면 보호도 함께 사라진다.

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
- **OAuth secret/token**은 각각 `yt-web` 전용 read-only bind mount와 named volume에만 둔다. `secrets/youtube-client.json`을 commit하거나 image에 복사하지 않는다.
- **업로드 job 재시작 복구 없음**: `restart: unless-stopped`는 web process만 다시 띄우며 in-memory upload job을 복원하지 않는다. 재제출 전 YouTube Studio에서 결과를 확인한다.

## 변경 이력

초기 v0 프로토타입의 개발 기록은 `docs/history.md`를 참고한다. 현재 구조와 동작의
권위 문서는 이 파일과 실제 `src/yt_monitor/` 소스다.
