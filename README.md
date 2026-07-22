# yt-w

YouTube 라이브 방송 자동 모니터링 + 일반 동영상 다운로드. Docker 기반 셀프호스팅.

## 주요 기능

### 웹 인터페이스
- 브라우저에서 모든 기능 사용 (채널 관리, 다운로드, 모니터링)
- `yt-monitor` 컨테이너의 실제 모니터링 상태 확인
- 반응형 디자인 (모바일/태블릿/PC)

### 멀티 채널 라이브 모니터링
- 여러 YouTube 채널 동시 모니터링
- 라이브 방송 감지 시 자동 다운로드
- 채널별 다운로드 포맷 설정
- 실시간 영상 분할 (시간/크기 기준)

### Discord 알림
- 라이브 감지 / 다운로드 완료·실패 / 쿠키 만료 / 모니터 시작·종료 알림
- `.env`에 Webhook URL 설정만으로 활성화 (외부 라이브러리 불필요)

### 일반 동영상 다운로드
- 화질 선택 (2160p ~ 360p)
- 오디오 전용 다운로드 (MP3)
- 자동 파일 정리 (retention 정책)

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
| `YT_POT_PROVIDER_URL` | PO Token provider 주소 | `http://pot-provider:4416` |
| `FIREFOX_PROFILE_PATH` | Docker에서 읽을 호스트 Firefox 프로필 경로 | (필수 입력) |

```bash
cp .env.example .env
# DISCORD_WEBHOOK_URL= 에 Discord Webhook URL 입력
# Discord 서버 설정 → 연동 → 웹후크 → 새 웹후크 → URL 복사
```

## 빠른 시작

### Docker (권장)

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

# 웹 서버 시작
python main.py

# 모니터링 데몬
python monitoring.py
```

## Docker 서비스 구성

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `yt-web` | 웹 API + UI, `yt-monitor` 상태 표시 | 8088 (외부) → 8011 (내부) |
| `yt-monitor` | 채널 모니터링 데몬 | - |
| `pot-provider` | PO Token provider (YouTube 봇 감지 우회) | - |

```bash
docker compose ps          # 상태 확인
docker compose logs -f     # 실시간 로그
docker compose down        # 정지
docker compose up -d --build  # 재빌드 + 실행
```

### Healthcheck

`yt-web`은 `/health` 엔드포인트, `yt-monitor`는 프로세스 생존 여부로 상태를 확인합니다.
웹 UI의 모니터링 화면은 `yt-monitor`가 공유 `logs/monitor_status.json`에 쓰는 heartbeat를 읽어 실제 데몬 상태를 표시합니다. 웹에서 모니터를 직접 시작/중지하지 않습니다.

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
├── src/yt_monitor/              # 메인 패키지
│   ├── channels/                # 채널 DTO와 JSON 저장소
│   ├── youtube/                 # 라이브 감지, 쿠키, URL 처리
│   ├── monitoring/              # 멀티 채널 조정, 채널 worker, heartbeat
│   ├── media/                   # 다운로드, ffmpeg 명령, 병합·분할
│   ├── notifications/           # Discord Webhook 알림
│   ├── maintenance/             # 파일 정리와 자동 정리 스케줄러
│   ├── web/                     # FastAPI 앱, 스키마, /api/* 라우트
│   ├── entrypoint.py            # 모니터 데몬 실행 진입점
│   └── logging.py               # 로깅 (일별 로테이션)
├── web/
│   ├── index.html               # Operator console markup
│   ├── app.css                  # Operator console styles
│   └── app.js                   # Operator console client logic
├── main.py                      # 웹 서버 호환 엔트리포인트
├── monitoring.py                # 모니터 데몬 호환 엔트리포인트
├── docker-compose.yml
├── Dockerfile
├── channels.json                # 채널 설정
└── channels.example.json        # 예제 설정
```

## 다운로드 파일 구조

```
downloads/
├── live/
│   └── 채널이름/
│       ├── 채널이름_라이브_20250126_143000.mp4
│       └── 채널이름_라이브_20250126_200000.mp4
└── web_downloads/
    ├── video_20250126_150000.mp4
    └── audio_20250126_160000.mp3
```

## 문제 해결

| 증상 | 해결 |
|------|------|
| ffmpeg not found | `apt install ffmpeg` 또는 [다운로드](https://ffmpeg.org/download.html) |
| 라이브 감지 안됨 | 채널 URL 확인, `check_interval_seconds` 조정 |
| 다운로드 실패 | `docker compose logs -f` 확인, `uv add yt-dlp --upgrade` |
| 봇 차단 또는 로그인 실패 | `pot-provider` 상태, `FIREFOX_PROFILE_PATH`, Firefox의 YouTube 로그인 상태 확인 |
| Discord 알림 안 옴 | `.env`의 `DISCORD_WEBHOOK_URL` 확인, Webhook URL 유효성 확인 |

## 개발

```bash
uv run pytest                         # 전체 테스트 실행
uv run pytest -v                      # 상세 출력
uv run pytest tests/web/test_app.py   # 웹 콘솔/정적 자산 최소 검증
```

- [아키텍처 문서](docs/ARCHITECTURE.md)
- [변경 이력](docs/history.md)

## 라이선스

개인적인 용도로 자유롭게 사용하세요.
