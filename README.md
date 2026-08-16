# yt-w

YouTube 라이브 방송 자동 모니터링 + 일반 동영상 다운로드·비공개 업로드. Docker 기반 셀프호스팅.

## 주요 기능

### 웹 인터페이스
- 브라우저에서 채널 관리, 모니터 상태 확인, 일반 다운로드, 영상 병합·분할·YouTube 업로드 사용
- `yt-monitor` 컨테이너의 실제 모니터링 상태 확인
- 방송 장비 랙과 인디 스튜디오 포스터를 결합한 콘솔 테마. 전기 보라는 선택, 애시드 라임은 실행, 핫 핑크는 녹화·경고에 사용
- 파일·그룹·YouTube 옵션은 정돈된 checkbox와 radio 선택 마크를 사용하면서 실제 `input`과 키보드 포커스 동작을 유지
- 반응형 디자인 (모바일/태블릿/PC)

### 멀티 채널 라이브 모니터링
- 여러 YouTube 채널 동시 모니터링
- 라이브 방송 감지 시 자동 다운로드
- 채널별 다운로드 포맷 설정
- 실시간 영상 분할 (시간/크기 기준)
- 실행 중 `channels.json` 변경을 감지해 채널 worker 추가·중지·재시작
- 방송 종료 감지 후 완료된 녹화 파일을 이름순으로 자동 병합
- 병합 성공 후 Windows host helper가 원본을 실제 Windows 휴지통으로 이동

### Discord 알림
- 라이브 감지 / 다운로드 완료·실패 / 쿠키 만료 / 모니터 시작·종료 알림
- `.env`에 Webhook URL 설정만으로 활성화 (외부 라이브러리 불필요)

### 일반 동영상 다운로드
- 화질 선택 (2160p ~ 360p)
- 오디오 전용 다운로드 (MP3)
- 자동 파일 정리 (retention 정책)

### 영상 병합·분할
- 다운로드 폴더의 영상을 원하는 순서로 빠른 concat 또는 재인코딩 병합
- 로컬 PC 영상을 업로드하거나 기존 파일을 선택해 시간 간격/N등분 분할
- 병합·분할 작업 상태 조회, 취소, 결과 다운로드
- File System Access API 지원 브라우저에서는 병합 결과를 선택한 PC 폴더에 저장

### YouTube 비공개 업로드
- Google OAuth로 연결한 단일 YouTube 계정에 기존 영상 업로드
- resumable upload 진행률, 작업 상태 조회, 취소 지원
- MVP에서는 모든 영상을 `private`로만 업로드
- 업로드 작업은 메모리에서 관리하므로 `yt-web` 재시작 후 자동 복구하지 않음

## 기술 스택

- **Python 3.15 RC** + **uv** (패키지 매니저) — 컨테이너는 `python:3.15-rc-alpine`, 소스 하한은 3.13
- **FastAPI** + **Uvicorn** (웹 서버)
- **yt-dlp** (YouTube 다운로드 엔진)
- **YouTube Data API v3** + **Google OAuth 2.0** (비공개 영상 업로드)
- **Node.js** (yt-dlp JavaScript challenge solver)
- **ffmpeg** (비디오 변환)
- **Docker Compose** (배포)

## 환경변수 (.env)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DISCORD_WEBHOOK_URL` | Discord 알림 Webhook URL | (미설정 시 알림 비활성화) |
| `YT_WEB_PORT` | 웹 서버 내부 포트 | `8011` |
| `YT_WEB_HOST` | 웹 서버 bind 주소. 로컬 실행은 loopback, Compose 내부만 전체 interface 사용 | `127.0.0.1` |
| `YT_POT_PROVIDER_URL` | PO Token provider 주소 | Compose가 `http://pot-provider:4416` 설정 |
| `FIREFOX_PROFILE_PATH` | Docker에서 read-only로 마운트할 호스트 Firefox 프로필 | Docker Compose 실행 시 입력 |
| `YT_COOKIE_BROWSER` | 로컬 실행에서 사용할 브라우저 | `firefox` |
| `YT_YOUTUBE_CLIENT_SECRETS_FILE` | OAuth Web client JSON 경로 (`yt-web` 전용) | `/run/secrets/youtube-client.json` |
| `YT_YOUTUBE_TOKEN_FILE` | Google OAuth token 저장 경로 (`yt-web` 전용) | `/app/data/youtube-oauth/token.json` |
| `YT_YOUTUBE_REDIRECT_URI` | Google OAuth callback URI | `http://localhost:8088/api/youtube/oauth/callback` |
| `YT_WEB_ALLOWED_HOSTS` | `yt-web`이 허용할 Host 헤더 목록 | `localhost,127.0.0.1` |

```bash
cp .env.example .env
# DISCORD_WEBHOOK_URL= 에 Discord Webhook URL 입력
# Discord 서버 설정 → 연동 → 웹후크 → 새 웹후크 → URL 복사
```

## YouTube 비공개 업로드용 OAuth 설정

이 설정은 업로드 기능을 사용할 때만 필요합니다. yt-dlp의 Firefox cookie나 PO Token과
Google OAuth는 서로 다른 인증 경계입니다. YouTube 업로드는 YouTube Data API의
OAuth 권한을 별도로 받아야 합니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 만들거나 선택합니다.
2. **YouTube Data API v3**를 사용 설정합니다.
3. OAuth 동의 화면을 구성합니다. 앱이 테스트 상태라면 업로드할 Google 계정을 test user로 추가합니다.
4. **OAuth client ID**를 만들고 application type은 **Web application**을 선택합니다.
5. **Authorized redirect URI**에 아래 값을 정확히 등록합니다. scheme, host, port, path와 trailing slash 유무가 모두 일치해야 합니다.

```text
http://localhost:8088/api/youtube/oauth/callback
```

6. OAuth client JSON을 다운로드한 뒤 파일명을 `youtube-client.json`으로 바꿔
   저장소의 `secrets/` 아래에 둡니다.

PowerShell:

```powershell
Copy-Item "C:\path\to\downloaded-client-secret.json" ".\secrets\youtube-client.json"
```

Git Bash/Linux/macOS:

```bash
cp /path/to/downloaded-client-secret.json ./secrets/youtube-client.json
```

`secrets/`의 실제 파일은 Git과 Docker build context에서 제외됩니다. 이 JSON은
client secret이므로 다른 사람과 공유하거나 이미지에 복사하지 마세요. 자세한 OAuth
흐름은 [YouTube Data API의 Web server OAuth 안내](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps)를 참고하세요.

## 빠른 시작

### Docker (권장)

Windows PowerShell에서는 최초 한 번 Windows 휴지통 helper를 현재 사용자 로그인
Scheduled Task로 등록한 뒤 Docker를 시작합니다.

```powershell
Copy-Item .env.example .env
Copy-Item channels.example.json channels.json
# .env의 FIREFOX_PROFILE_PATH에 로그인된 Firefox 프로필 경로 입력
# 업로드를 사용한다면 .\secrets\youtube-client.json이 있는지 확인

.\scripts\install-windows-recycle-task.ps1
.\scripts\start-windows.ps1
```

설치된 Task는 매일 현지 시각 오전 3시에 helper를 `-Once`로 실행합니다. 설치 직후나
Docker 시작 시에는 즉시 실행하지 않으며, 예약 시각에 PC를 사용할 수 없었던 경우에만
다음 사용 가능 시점에 한 번 실행합니다. Task는 `wscript.exe` hidden launcher를 사용해
PowerShell console을 표시하지 않습니다. Task를 설치하지 않은 상태에서
`docker compose up`만 실행하면 병합은 완료되지만 원본은 안전을 위해 `live/`에 남고,
`.recycle-requests/`의 요청이 대기합니다.

Windows 휴지통 연동이 필요 없는 환경에서는 Docker Compose를 직접 실행할 수 있습니다.

```bash
# 환경 설정
cp .env.example .env
cp channels.example.json channels.json
# .env의 FIREFOX_PROFILE_PATH에 로그인된 Firefox 프로필 경로 입력
# 업로드를 사용한다면 ./secrets/youtube-client.json이 있는지 확인

# 실행
docker compose up -d --build
```

웹 UI: `http://localhost:8088`

업로드를 사용할 때는 웹 UI의 YouTube 업로드 화면에서 OAuth 연결을 시작하고 Google
계정을 승인한 뒤, 기존 영상과 메타데이터를 선택해 제출합니다. MVP는 YouTube
`videos.insert`에 `privacyStatus=private`만 전송합니다.
OAuth 연결은 state cookie와 callback host가 일치하도록 `127.0.0.1` 주소가 아니라
`http://localhost:8088`에서 시작하세요.

### 로컬 실행

```bash
# 의존성 설치
uv sync

# 웹 서버 시작 (터미널 1)
uv run python main.py

# 모니터링 데몬 (터미널 2)
uv run python monitoring.py
```

`.env.example`의 OAuth 파일 경로는 Docker 컨테이너 기준입니다. Docker 없이 OAuth
callback까지 로컬에서 검증하려면 웹 서버를 callback과 같은 `8088` 포트로 실행하고
파일 경로를 호스트 경로로 바꿉니다.

```powershell
$env:YT_WEB_PORT = "8088"
$env:YT_WEB_HOST = "127.0.0.1"
$env:YT_YOUTUBE_CLIENT_SECRETS_FILE = (Resolve-Path ".\secrets\youtube-client.json").Path
$env:YT_YOUTUBE_TOKEN_FILE = Join-Path (Resolve-Path ".\secrets").Path "youtube-token.json"
$env:YT_YOUTUBE_REDIRECT_URI = "http://localhost:8088/api/youtube/oauth/callback"
$env:YT_WEB_ALLOWED_HOSTS = "localhost,127.0.0.1"
uv run python main.py
```

## Docker 서비스 구성

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `yt-web` | 웹 API + UI, `yt-monitor` 상태 표시, OAuth·업로드 | `127.0.0.1:8088` → 8011 |
| `yt-monitor` | 채널 모니터링 데몬 | - |
| `pot-provider` | PO Token provider (YouTube 봇 감지 우회) | - |
| `autoheal` | `autoheal=true` 컨테이너의 unhealthy 상태 감시 | - |

```bash
docker compose ps          # 상태 확인
docker compose logs -f     # 실시간 로그
docker compose down        # 정지
docker compose up -d --build  # 재빌드 + 실행
```

### Healthcheck

`yt-web`은 `/health` 엔드포인트, `yt-monitor`는 프로세스 생존 여부로 상태를 확인합니다.
웹 UI의 모니터링 화면은 `yt-monitor`가 공유 `logs/monitor_status.json`에 쓰는 heartbeat를 읽어 실제 데몬 상태를 표시합니다. 웹에서 모니터를 직접 시작/중지하지 않습니다.
현재 `autoheal=true` label은 `pot-provider`에만 설정되어 있습니다. `yt-web`과
`yt-monitor`는 `restart: unless-stopped` 정책을 사용합니다.

`yt-web`의 host port는 OAuth token을 가진 개인용 API를 외부 네트워크에 노출하지 않도록
`127.0.0.1`에만 publish합니다. 다른 기기에서 접속시키거나 공개 reverse proxy 뒤에
두는 구성은 이 single-user MVP의 보안 범위 밖입니다.

```bash
# 헬스 상태 확인
docker inspect --format='{{.State.Health.Status}}' yt-web
docker inspect --format='{{.State.Health.Status}}' yt-monitor

# 직접 확인
curl http://localhost:8088/health
# → {"status": "ok"}
```

## 설정

### channels.json

```json
{
  "channels": [
    {
      "id": "auto-generated-uuid",
      "name": "채널이름",
      "url": "https://www.youtube.com/@channel",
      "enabled": true,
      "download_format": "bestvideo[height<=720]+bestaudio/best[height<=720]"
    }
  ],
  "global_settings": {
    "check_interval_seconds": 60,
    "download_directory": "./downloads",
    "log_file": "./logs/live_monitor.log",
    "split_mode": "time",
    "split_time_minutes": 30,
    "split_size_mb": 500
  }
}
```

### 설정 항목

| 항목 | 설명 | 기본값 |
|------|------|--------|
| `check_interval_seconds` | 라이브 체크 주기 (초) | 60 |
| `download_directory` | 다운로드 경로 | `./downloads` |
| `log_file` | 모니터 로그 파일과 heartbeat 디렉터리 기준 경로 | `./logs/live_monitor.log` |
| `split_mode` | 분할 모드 (`time` / `size` / `none`) | `time` |
| `split_time_minutes` | 시간 분할 단위 (분) | 30 |
| `split_size_mb` | 크기 분할 단위 (MB) | 500 |

### YouTube 로그인 인증 및 봇 감지 대응

PO Token과 브라우저 쿠키는 역할이 다르며 함께 사용할 수 있습니다.

**1. PO Token Provider**
- `pot-provider` 컨테이너가 PO Token을 자동으로 제공
- Docker Compose로 자동 실행됨 (별도 설정 불필요)
- 환경변수: `YT_POT_PROVIDER_URL=http://pot-provider:4416`
- YouTube의 봇 감지 대응 수단이며 로그인 권한을 대신하지 않음

**2. Firefox 로그인 프로필**
- Docker는 `.env`의 `FIREFOX_PROFILE_PATH`를 `/app/firefox_profile`에 read-only로 마운트
- `yt-dlp`가 Firefox의 최신 YouTube 로그인 쿠키를 직접 읽으므로 수동 추출 불필요
- 멤버십·비공개 등 인증된 계정 권한이 필요한 영상은 해당 권한이 있는 Firefox 프로필 필요
- 로컬 실행은 기본적으로 Firefox 쿠키를 사용하며, 다른 브라우저는 `YT_COOKIE_BROWSER` 환경변수로 선택 가능

Firefox 프로필에는 로그인 정보가 있으므로 공유하지 마세요. 격리가 필요하면 YouTube 전용 Firefox 프로필을 사용하는 것이 안전합니다.

### YouTube OAuth token과 업로드 작업 경계

- YouTube OAuth 전용인 host의 `./secrets`는 `/run/secrets:ro`로 `yt-web`에만
  마운트됩니다. `yt-monitor`와 Docker image에는 OAuth client secret이 들어가지
  않습니다. 이 디렉터리에는 다른 서비스의 비밀정보를 두지 마세요.
- OAuth refresh token은 `youtube-oauth-data` named volume의
  `/app/data/youtube-oauth/token.json`에 저장되며 `yt-web`만 마운트합니다. 컨테이너를
  다시 만들어도 연결은 유지됩니다. token 파일에는 refresh token과 scope만 저장하고
  client secret은 read-only client JSON에서 읽습니다. `docker compose down -v`는
  volume과 연결 정보를 삭제합니다.
- token 파일은 YouTube 채널 업로드 권한을 가진 민감 정보입니다. 백업하거나 복사할
  때도 client secret과 같은 수준으로 보호하고, 노출되면 Google 계정에서 권한을 철회합니다.
- resumable upload는 실행 중 네트워크 재시도와 진행률을 위한 기능입니다.
  `YouTubeUploadJobManager`의 job은 메모리에만 있으므로 `yt-web` 재시작 시
  queued/running job을 저장하거나 이어서 실행하지 않습니다. 재제출 전에 YouTube
  Studio에서 영상 생성 여부를 먼저 확인합니다.

## 프로젝트 구조

```
yt-w/
├── src/yt_monitor/              # Python 애플리케이션 본체
│   ├── channels/                # 채널 DTO와 원자적 JSON 저장소
│   ├── youtube/                 # 라이브 감지, 쿠키 검증, OAuth·비공개 업로드
│   ├── monitoring/              # 멀티 채널 조정, worker, heartbeat
│   ├── media/                   # yt-dlp/ffmpeg 다운로드, 병합, 분할
│   ├── notifications/           # Discord Webhook 알림
│   ├── maintenance/             # retention 정리와 스케줄러
│   ├── web/
│   │   ├── app.py               # FastAPI 앱 조립
│   │   ├── schemas.py           # Pydantic 요청/응답 모델
│   │   └── routes/              # 기능별 /api/* 라우트
│   ├── entrypoint.py            # 모니터 데몬 실행 진입점
│   └── logging.py               # 일별 회전 로그
├── web/
│   ├── index.html               # Operator console 화면
│   ├── app.css                  # 화면 스타일
│   ├── app.js                   # API 호출과 화면 상태
│   ├── merge_output_name.js     # 기본 병합 파일명 계산
│   └── merge_download_directory.js # PC 저장 폴더 기억/쓰기
├── tests/                       # pytest + Node 기반 frontend 회귀 테스트
├── main.py                      # 웹 서버 호환 엔트리포인트
├── monitoring.py                # 모니터 데몬 호환 엔트리포인트
├── scripts/
│   ├── check_orphan_pyc.py                # 고아 .pyc pre-commit 검사
│   ├── install-windows-recycle-task.ps1   # 매일 오전 3시 Task 등록
│   ├── run-windows-recycle-helper-hidden.vbs # console 없는 helper launcher
│   ├── start-windows.ps1                  # Task 상태 확인 + Docker 시작
│   ├── uninstall-windows-recycle-task.ps1 # helper Task 등록 해제
│   └── windows-recycle-helper.ps1         # 실제 Windows 휴지통 처리
├── docs/
│   ├── ARCHITECTURE.md          # 현재 구조와 운영 계약의 권위 문서
│   ├── history.md               # v0 프로토타입 개발 이력
│   └── verify/                  # 실측 검증 리포트와 스크린샷
├── secrets/
│   └── .gitkeep                 # 실제 OAuth client JSON은 Git에서 제외
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml               # Python 의존성과 pytest 설정
├── uv.lock                      # 고정 의존성
├── channels.json                # 실제 채널 설정
└── channels.example.json        # 예제 설정
```

## 다운로드 파일 구조

```
downloads/
├── .recycle-requests/            # Windows host helper가 처리할 원자적 요청
├── .trash/                       # 이전 버전의 앱 휴지통 자료(자동 이관하지 않음)
├── live/
│   └── 채널이름/
│       ├── 채널이름_라이브_20250126_143000_part000.mp4
│       └── 채널이름_라이브_20250126_143000_part001.mp4
├── merged/
│   └── 채널이름_라이브_20250126_143000.mp4
├── split/                        # 영상 분할 결과
├── uploads/                      # 분할 화면에서 업로드한 원본
└── web_downloads/                # 일반 영상/오디오 다운로드
    ├── video_20250126_150000.mp4
    └── audio_20250126_160000.mp3
```

`FileCleaner`는 기본 7일 retention을 적용하지만 `live/`, `.trash/`,
`.recycle-requests/`는 삭제하지 않습니다. `merged/`, `split/`, `uploads/`,
`web_downloads/`는 retention 대상입니다.

## API 영역

| 모듈 | 주요 엔드포인트 | 책임 |
|------|-----------------|------|
| `routes/channels.py` | `/api/channels` | 채널 조회·추가·수정·삭제 |
| `routes/monitor.py` | `/api/monitor/status` | heartbeat 기반 모니터 상태 조회 |
| `routes/video.py` | `/api/video/info`, `/api/download` | 일반 영상 정보 조회와 다운로드 |
| `routes/cookies.py` | `/api/cookie/status` | 실제 yt-dlp 추출 기반 쿠키 검증 |
| `routes/merge.py` | `/api/files`, `/api/merge/*` | 파일 목록·삭제와 병합 작업 |
| `routes/split.py` | `/api/split/*` | 파일 업로드와 분할 작업 |
| `routes/youtube_upload.py` | `/api/youtube/oauth/*`, `/api/youtube/uploads*` | OAuth 연결과 비공개 업로드 작업 |
| `routes/system.py` | `/api/system/*` | 디스크·다운로드·Discord·모니터 통합 상태 |
| `routes/meta.py` | `/`, `/health`, `/static` | UI와 정적 자산, healthcheck |

`POST /api/monitor/start`와 `POST /api/monitor/stop`은 `405`를 반환합니다.
모니터 데몬은 `docker compose start/stop yt-monitor`로 제어합니다.

## 문제 해결

| 증상 | 해결 |
|------|------|
| ffmpeg not found | `apt install ffmpeg` 또는 [다운로드](https://ffmpeg.org/download.html) |
| 라이브 감지 안됨 | 채널 URL 확인, `check_interval_seconds` 조정 |
| 다운로드 실패 | `docker compose logs -f` 확인, `uv add yt-dlp --upgrade` |
| 병합 후 원본이 `live/`에 남음 | `Get-ScheduledTask -TaskName yt-w-windows-recycle-helper`와 `logs/windows-recycle-helper.log` 확인 후 `.\scripts\install-windows-recycle-task.ps1` 실행 |
| 봇 차단 또는 로그인 실패 | `pot-provider` 상태, `FIREFOX_PROFILE_PATH`, Firefox의 YouTube 로그인 상태 확인 |
| OAuth에서 `redirect_uri_mismatch` | Google Cloud의 Authorized redirect URI가 `http://localhost:8088/api/youtube/oauth/callback`과 정확히 같은지 확인 |
| OAuth 연결을 시작할 수 없음 | `secrets/youtube-client.json` 존재 여부와 `yt-web`의 `/run/secrets/youtube-client.json` read-only mount 확인 |
| 재시작 뒤 업로드 job이 사라짐 | MVP는 job을 영속화하지 않음. YouTube Studio에서 생성 여부를 확인한 뒤 필요하면 다시 제출 |
| Discord 알림 안 옴 | `.env`의 `DISCORD_WEBHOOK_URL` 확인, Webhook URL 유효성 확인 |

## 개발

```bash
uv run pytest                         # 전체 테스트 실행
uv run pytest -v                      # 상세 출력
uv run pytest tests/web/test_app.py   # 웹 콘솔/정적 자산 최소 검증
uv run pytest tests/youtube tests/web/routes tests/web/frontend  # OAuth/upload 포함 기능별 검증
uv run pre-commit run --all-files     # Ruff + 고아 .pyc + frontend 회귀 검사
docker compose config --quiet         # Compose 문법과 env/mount interpolation 검증(값은 출력하지 않음)
```

`web/`이나 `tests/web/frontend/`를 stage하면 pre-commit이 frontend 회귀 테스트를
자동으로 실행합니다 (약 3초).

- [아키텍처 문서](docs/ARCHITECTURE.md)
- [변경 이력](docs/history.md)
- [검증 리포트](docs/verify/) — 실제 실행으로 확인한 회귀 검증과 문서 감사 기록

## 라이선스

개인적인 용도로 자유롭게 사용하세요.
