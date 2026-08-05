# yt-w

YouTube 라이브 방송 자동 모니터링 + 일반 동영상 다운로드. Docker 기반 셀프호스팅.

## 주요 기능

### 웹 인터페이스
- 브라우저에서 채널 관리, 모니터 상태 확인, 일반 다운로드, 영상 병합·분할 사용
- `yt-monitor` 컨테이너의 실제 모니터링 상태 확인
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

## 기술 스택

- **Python 3.13** + **uv** (패키지 매니저)
- **FastAPI** + **Uvicorn** (웹 서버)
- **yt-dlp** (YouTube 다운로드 엔진)
- **Node.js** (yt-dlp JavaScript challenge solver)
- **ffmpeg** (비디오 변환)
- **Docker Compose** (배포)

## 환경변수 (.env)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DISCORD_WEBHOOK_URL` | Discord 알림 Webhook URL | (미설정 시 알림 비활성화) |
| `YT_WEB_PORT` | 웹 서버 내부 포트 | `8011` |
| `YT_POT_PROVIDER_URL` | PO Token provider 주소 | Compose가 `http://pot-provider:4416` 설정 |
| `FIREFOX_PROFILE_PATH` | Docker에서 read-only로 마운트할 호스트 Firefox 프로필 | Docker Compose 실행 시 입력 |
| `YT_COOKIE_BROWSER` | 로컬 실행에서 사용할 브라우저 | `firefox` |

```bash
cp .env.example .env
# DISCORD_WEBHOOK_URL= 에 Discord Webhook URL 입력
# Discord 서버 설정 → 연동 → 웹후크 → 새 웹후크 → URL 복사
```

## 빠른 시작

### Docker (권장)

Windows PowerShell에서는 최초 한 번 Windows 휴지통 helper를 현재 사용자 로그인
Scheduled Task로 등록한 뒤 Docker를 시작합니다.

```powershell
Copy-Item .env.example .env
Copy-Item channels.example.json channels.json
# .env의 FIREFOX_PROFILE_PATH에 로그인된 Firefox 프로필 경로 입력

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

# 실행
docker compose up -d --build
```

웹 UI: `http://localhost:8088`

### 로컬 실행

```bash
# 의존성 설치
uv sync

# 웹 서버 시작 (터미널 1)
uv run python main.py

# 모니터링 데몬 (터미널 2)
uv run python monitoring.py
```

## Docker 서비스 구성

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `yt-web` | 웹 API + UI, `yt-monitor` 상태 표시 | 8088 (외부) → 8011 (내부) |
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

## 프로젝트 구조

```
yt-w/
├── src/yt_monitor/              # Python 애플리케이션 본체
│   ├── channels/                # 채널 DTO와 원자적 JSON 저장소
│   ├── youtube/                 # 라이브 감지, 쿠키 검증, URL 처리
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
├── docs/                         # 현재 아키텍처와 v0 개발 이력
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
| Discord 알림 안 옴 | `.env`의 `DISCORD_WEBHOOK_URL` 확인, Webhook URL 유효성 확인 |

## 개발

```bash
uv run pytest                         # 전체 테스트 실행
uv run pytest -v                      # 상세 출력
uv run pytest tests/web/test_app.py   # 웹 콘솔/정적 자산 최소 검증
uv run pre-commit run --all-files     # Ruff + 고아 .pyc 검사
```

- [아키텍처 문서](docs/ARCHITECTURE.md)
- [변경 이력](docs/history.md)

## 라이선스

개인적인 용도로 자유롭게 사용하세요.
