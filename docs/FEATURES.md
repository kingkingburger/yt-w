# YouTube Live Stream Monitor - 기능 문서

## 개요

YouTube 라이브 스트림을 자동으로 감지하고 다운로드하는 애플리케이션입니다. CLI와 웹 인터페이스를 모두 지원하며, Docker를 통한 배포가 가능합니다.

---

## 목차

1. [핵심 기능](#1-핵심-기능)
2. [채널 관리](#2-채널-관리)
3. [다운로드 기능](#3-다운로드-기능)
4. [웹 인터페이스](#4-웹-인터페이스)
5. [CLI 인터페이스](#5-cli-인터페이스)
6. [설정 옵션](#6-설정-옵션)
7. [Docker 배포](#7-docker-배포)

---

## 1. 핵심 기능

### 1.1 라이브 스트림 모니터링

여러 YouTube 채널을 동시에 모니터링하여 라이브 방송을 자동 감지합니다.

**감지 방식:**
- `/live` 엔드포인트 확인
- Streams 탭 감지
- 채널 페이지 비디오 감지

**특징:**
- 멀티 스레드 기반 동시 모니터링
- 설정 가능한 체크 간격 (기본: 60초)
- Graceful Shutdown 지원 (Ctrl+C)

### 1.2 자동 다운로드

라이브 스트림 감지 시 자동으로 다운로드를 시작합니다.

- 채널별 개별 폴더에 저장
- 날짜/시간 기반 파일명 생성
- 중단 시 자동 재시도

---

## 2. 채널 관리

### 2.1 채널 추가/삭제

```bash
# 채널 추가
python main.py --add-channel "채널이름" "https://www.youtube.com/@channelname"

# 채널 삭제
python main.py --remove-channel CHANNEL_ID
```

### 2.2 채널 활성화/비활성화

삭제하지 않고 모니터링을 일시 중지할 수 있습니다.

```bash
# 비활성화
python main.py --disable-channel CHANNEL_ID

# 활성화
python main.py --enable-channel CHANNEL_ID
```

### 2.3 채널 목록 조회

```bash
python main.py --list-channels
```

**출력 예시:**
```
=== 등록된 채널 목록 ===
1. [활성] 채널이름1 - https://www.youtube.com/@channel1
   ID: abc123-def456
2. [비활성] 채널이름2 - https://www.youtube.com/@channel2
   ID: ghi789-jkl012
```

---

## 3. 다운로드 기능

### 3.1 비디오 품질 선택

| 옵션 | 해상도 |
|------|--------|
| `2160` | 4K (2160p) |
| `1440` | 2K (1440p) |
| `1080` | Full HD |
| `720` | HD (기본값) |
| `480` | SD |
| `360` | 저화질 |
| `best` | 최고 품질 |

```bash
python main.py --url "URL" --quality 1080
```

### 3.2 오디오 전용 다운로드

MP3 형식으로 오디오만 추출합니다 (192kbps).

```bash
python main.py --url "URL" --audio-only
```

### 3.3 비디오 분할

긴 라이브 스트림을 자동으로 분할하여 저장합니다.

**시간 기반 분할:**
```json
{
  "split_mode": "time",
  "split_time_minutes": 10
}
```

**용량 기반 분할:**
```json
{
  "split_mode": "size",
  "split_size_mb": 500
}
```

**분할 없음:**
```json
{
  "split_mode": "none"
}
```

### 3.4 오디오 코덱 변환

Windows Media Player 호환성을 위해 Opus 코덱을 AAC로 자동 변환합니다.

---

## 4. 웹 인터페이스

### 4.1 웹 서버 실행

```bash
# 기본 포트 (8011)
python web_server.py

# 사용자 정의 포트
python web_server.py --port 3000

# 외부 접속 허용
python web_server.py --host 0.0.0.0 --port 8080
```

### 4.2 웹 UI 기능

| 기능 | 설명 |
|------|------|
| 대시보드 | 실시간 모니터링 상태 확인 |
| 채널 관리 | 추가/수정/삭제/활성화 |
| 비디오 다운로드 | URL 입력으로 즉시 다운로드 |
| 설정 관리 | 전역 설정 변경 |
| 모니터링 제어 | 시작/중지 버튼 |

### 4.3 REST API

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET` | `/api/channels` | 채널 목록 조회 |
| `POST` | `/api/channels` | 채널 추가 |
| `PATCH` | `/api/channels/{id}` | 채널 수정 |
| `DELETE` | `/api/channels/{id}` | 채널 삭제 |
| `GET` | `/api/settings` | 설정 조회 |
| `PATCH` | `/api/settings` | 설정 변경 |
| `GET` | `/api/monitor/status` | 모니터링 상태 |
| `POST` | `/api/monitor/start` | 모니터링 시작 |
| `POST` | `/api/monitor/stop` | 모니터링 중지 |
| `POST` | `/api/video/info` | 비디오 정보 조회 |
| `POST` | `/api/download` | 비디오 다운로드 |
| `GET` | `/api/download/file/{filename}` | 파일 다운로드 |

---

## 5. CLI 인터페이스

### 5.1 모니터링 모드

```bash
# 기본 실행
python main.py

# 사용자 정의 설정 파일
python main.py --channels mychannel.json
```

### 5.2 채널 관리 명령어

```bash
# 채널 추가
python main.py --add-channel "이름" "URL"

# 채널 목록
python main.py --list-channels

# 채널 활성화/비활성화
python main.py --enable-channel ID
python main.py --disable-channel ID

# 채널 삭제
python main.py --remove-channel ID
```

### 5.3 단일 비디오 다운로드

```bash
# 기본 다운로드
python main.py --url "https://youtube.com/watch?v=VIDEO_ID"

# 품질 지정
python main.py --url "URL" --quality 720

# 오디오만
python main.py --url "URL" --audio-only
```

---

## 6. 설정 옵션

### 6.1 channels.json 구조

```json
{
  "channels": [
    {
      "id": "uuid-string",
      "name": "채널 이름",
      "url": "https://www.youtube.com/@channelname",
      "enabled": true,
      "download_format": "bestvideo[height<=720]+bestaudio/best[height<=720]"
    }
  ],
  "global_settings": {
    "check_interval_seconds": 60,
    "download_directory": "./downloads",
    "log_file": "./live_monitor.log",
    "split_mode": "time",
    "split_time_minutes": 10,
    "split_size_mb": 500
  }
}
```

### 6.2 전역 설정 항목

| 설정 | 설명 | 기본값 |
|------|------|--------|
| `check_interval_seconds` | 라이브 체크 간격 (초) | 60 |
| `download_directory` | 다운로드 저장 경로 | `./downloads` |
| `log_file` | 로그 파일 경로 | `./live_monitor.log` |
| `split_mode` | 분할 모드 (time/size/none) | `time` |
| `split_time_minutes` | 시간 기반 분할 간격 (분) | 10 |
| `split_size_mb` | 용량 기반 분할 크기 (MB) | 500 |

### 6.3 환경 변수

```bash
# .env 파일
YT_WEB_PORT=8011  # 웹 서버 포트
```

---

## 7. Docker 배포

### 7.1 Docker Compose 실행

```bash
# 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

### 7.2 서비스 구성

| 서비스 | 설명 | 포트 |
|--------|------|------|
| `yt-monitor` | 모니터링 서비스 | - |
| `yt-web` | 웹 인터페이스 | 8011 (설정 가능) |

### 7.3 볼륨 마운트

- `channels.json` - 채널 설정
- `downloads/` - 다운로드 파일
- `live_monitor.log` - 로그 파일

---

## 파일 저장 구조

### 라이브 스트림 (채널별)

```
downloads/
├── 채널이름1/
│   ├── 채널이름1_라이브_20250126_143000.mp4
│   ├── 채널이름1_라이브_20250126_143000_part001.mp4
│   └── 채널이름1_라이브_20250126_143000_part002.mp4
├── 채널이름2/
│   └── ...
```

### 일반 비디오

```
downloads/
├── video_20250126_143000.mp4
├── web_downloads/
│   ├── video_20250126_143000.mp4
│   └── audio_20250126_143100.mp3
```

---

## 시스템 요구사항

### 필수 요구사항

- Python 3.13+
- FFmpeg (비디오 변환 및 분할)
- 인터넷 연결

### 의존성 패키지

| 패키지 | 용도 |
|--------|------|
| `fastapi` | 웹 API 프레임워크 |
| `uvicorn` | ASGI 서버 |
| `yt-dlp` | YouTube 다운로드 |

---

## 로깅

- **파일**: `live_monitor.log`
- **콘솔**: 실시간 출력
- **형식**: `YYYY-MM-DD HH:MM:SS - LEVEL - MESSAGE`

---

## 관련 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 시스템 아키텍처
- [TESTING.md](./TESTING.md) - 테스트 가이드
- [coding_rules.md](./coding_rules.md) - 코딩 규칙
