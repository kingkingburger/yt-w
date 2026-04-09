# yt-w

YouTube 라이브 방송 자동 모니터링 + 일반 동영상 다운로드. Docker 기반 셀프호스팅.

## 주요 기능

### 웹 인터페이스
- 브라우저에서 모든 기능 사용 (채널 관리, 다운로드, 모니터링)
- 실시간 모니터링 상태 확인
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
| `YT_COOKIES_FILE` | 쿠키 파일 경로 | `./cookies.txt` |

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

# 실행
docker compose up -d --build
```

웹 UI: `http://localhost:8088`

### 로컬 실행

```bash
# 의존성 설치
uv sync

# 웹 서버 시작
python main.py --host 0.0.0.0 --port 8011

# 모니터링 데몬
python monitoring.py
```

## Docker 서비스 구성

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `yt-web` | 웹 API + UI | 8088 (외부) → 8011 (내부) |
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

```bash
# 헬스 상태 확인
docker inspect --format='{{.State.Health.Status}}' yt-web
docker inspect --format='{{.State.Health.Status}}' yt-monitor

# 직접 확인
curl http://localhost:8088/health
# → {"status": "ok"}
```

## CLI 사용법

### 채널 관리

```bash
python main.py --add-channel "채널이름" "https://www.youtube.com/@channel"
python main.py --list-channels
python main.py --enable-channel CHANNEL_ID
python main.py --disable-channel CHANNEL_ID
python main.py --remove-channel CHANNEL_ID
```

### 동영상 다운로드

```bash
python main.py --url "https://youtube.com/watch?v=VIDEO_ID"
python main.py --url "URL" --quality 720
python main.py --url "URL" --audio-only
python main.py -u "URL" -o "./output" -f "filename"
```

### 파일 정리

```bash
python main.py --cleanup              # 실행
python main.py --cleanup --dry-run    # 미리보기
python main.py --cleanup --days 14    # 보관 기간 변경
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

### 쿠키 인증 및 봇 감지 우회

YouTube 봇 차단 우회를 위해 두 가지 방식을 지원합니다.

**1. PO Token Provider (권장)**
- `pot-provider` 컨테이너가 PO Token을 자동으로 제공
- Docker Compose로 자동 실행됨 (별도 설정 불필요)
- 환경변수: `YT_POT_PROVIDER_URL=http://pot-provider:4416`

**2. 쿠키 파일 (선택사항)**
- `cookies.txt` 파일을 프로젝트 루트에 배치
- Docker: 자동으로 마운트됨
- 로컬: 환경변수 `YT_COOKIES_FILE` 설정 가능

## 프로젝트 구조

```
yt-w/
├── src/yt_monitor/              # 메인 패키지
│   ├── web_api.py               # FastAPI 웹 서버 + REST API
│   ├── multi_channel_monitor.py # 멀티 채널 모니터링
│   ├── channel_manager.py       # 채널 설정 관리
│   ├── youtube_client.py        # YouTube 라이브 감지 (3중 fallback)
│   ├── stream_downloader.py     # 라이브 스트림 다운로더
│   ├── video_downloader.py      # 일반 동영상 다운로더
│   ├── file_cleaner.py          # 자동 파일 정리
│   ├── discord_notifier.py      # Discord Webhook 알림
│   ├── cookie_helper.py         # 쿠키 인증 헬퍼
│   ├── logger.py                # 로깅 (일별 로테이션)
│   └── util/
│       └── sanitize_url.py      # URL 정규화
├── web/
│   └── index.html               # 웹 UI (Tailwind CSS)
├── main.py                      # CLI + 웹 서버 엔트리포인트
├── monitoring.py                # 모니터링 데몬 엔트리포인트
├── docker-compose.yml
├── Dockerfile
├── channels.json                # 채널 설정
├── channels.example.json        # 예제 설정
├── refresh_cookies.bat          # 쿠키 새로고침 (대화형)
└── update_cookies.bat           # 쿠키 새로고침 (스케줄러용)
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
| 봇 차단 | PO Token provider 실행 확인 (`docker compose logs pot-provider`), 또는 `cookies.txt` 갱신 |
| Discord 알림 안 옴 | `.env`의 `DISCORD_WEBHOOK_URL` 확인, Webhook URL 유효성 확인 |

## 개발

```bash
uv run pytest           # 테스트 실행
uv run pytest -v        # 상세 출력
```

- [아키텍처 문서](docs/ARCHITECTURE.md)
- [테스트 가이드](docs/TESTING.md)
- [변경 이력](docs/history.md)

## 라이선스

개인적인 용도로 자유롭게 사용하세요.
