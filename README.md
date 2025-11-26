#  YouTube 다운로더 (라이브 + 일반 동영상)

YouTube 라이브 방송 자동 모니터링 및 일반 동영상 다운로드를 지원하는 프로그램입니다.

## 주요 기능

### 웹 인터페이스 (NEW!)
- **직관적인 웹 UI**: 브라우저에서 모든 기능을 쉽게 사용
- **실시간 모니터링 상태**: 실행 중인 모니터링 상태를 실시간으로 확인
- **채널 관리**: 웹에서 채널 추가/삭제/활성화/비활성화
- **원클릭 시작/중지**: 버튼 하나로 모니터링 시작/중지
- **반응형 디자인**: 모바일, 태블릿, PC에서 모두 사용 가능

### 멀티 채널 라이브 방송 모니터링
- **여러 채널 동시 모니터링**: 여러 YouTube 채널을 동시에 모니터링
- **채널 관리**: CLI 또는 웹을 통한 채널 추가/삭제/활성화/비활성화
- **채널별 설정**: 각 채널마다 다운로드 포맷 설정 가능
- **자동 다운로드**: 라이브 방송 감지 시 자동 다운로드 시작
- **채널별 디렉토리**: 각 채널의 다운로드를 별도 폴더에 저장

### 일반 동영상 다운로드
- YouTube 링크로 즉시 다운로드
- 화질 선택 (2160p, 1440p, 1080p, 720p, 480p, 360p)
- 오디오 전용 다운로드 (MP3 추출)
- CLI 인터페이스

### 공통 기능
- 로그 기록 기능
- MP4 형식으로 자동 변환
- 실시간 영상 분할 (시간/크기 기준)
- 모듈화된 아키텍처

## 필요 사항

- Python 3.13 이상
- yt-dlp
- ffmpeg (비디오 변환을 위해 필요)

## 설치 방법

1. 저장소 클론 또는 다운로드

2. 의존성 설치:
```bash
uv sync
```

3. ffmpeg 설치 (아직 설치하지 않은 경우):
   - Windows: https://ffmpeg.org/download.html 에서 다운로드
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg` 또는 `sudo yum install ffmpeg`

## 사용 방법

### 모드 1: 웹 인터페이스 (가장 쉬움, 권장!)

웹 브라우저에서 모든 기능을 사용할 수 있습니다.

#### 1. 웹 서버 시작

```bash
python web_server.py
```

또는 포트 변경:

```bash
python web_server.py --port 3000
```

#### 2. 브라우저에서 접속

```
http://localhost:8000
```

#### 3. 웹 인터페이스 사용법

1. **채널 추가**: 오른쪽 상단의 "채널 추가" 버튼 클릭
2. **모니터링 시작**: "시작" 버튼 클릭
3. **채널 관리**: 각 채널의 활성화/비활성화/삭제 버튼 사용
4. **모니터링 중지**: "중지" 버튼 클릭

웹 인터페이스에서 실시간으로 모니터링 상태와 등록된 채널을 확인할 수 있습니다!

---

### 모드 2: CLI - 멀티 채널 모니터링

#### 1. 채널 추가

```bash
# 첫 번째 채널 추가
python main.py --add-channel "침착맨" "https://www.youtube.com/@chimchakman_vod"

# 두 번째 채널 추가
python main.py --add-channel "우왁굳" "https://www.youtube.com/@woowakgood"

# 추가 채널들...
python main.py --add-channel "채널이름" "채널URL"
```

#### 2. 채널 목록 확인

```bash
python main.py --list-channels
```

출력 예시:
```
등록된 채널 목록 (2개):
================================================================================
  [활성화] 침착맨
    ID: 3ba22a1c-aba7-401c-9abd-3779b508c929
    URL: https://www.youtube.com/@chimchakman_vod
    포맷: bestvideo[height<=720]+bestaudio/best[height<=720]
--------------------------------------------------------------------------------
  [활성화] 우왁굳
    ID: 7cd8f2b9-1234-5678-90ab-cdef12345678
    URL: https://www.youtube.com/@woowakgood
    포맷: bestvideo[height<=720]+bestaudio/best[height<=720]
--------------------------------------------------------------------------------
```

#### 3. 모니터링 시작

```bash
# 모든 활성화된 채널 모니터링 시작
python main.py
```

프로그램이 실행되면:
1. 등록된 모든 활성화된 채널을 동시에 모니터링합니다
2. 각 채널에서 라이브 방송이 감지되면 자동으로 다운로드를 시작합니다
3. 다운로드된 파일은 `./downloads/채널이름/` 디렉토리에 저장됩니다
4. `Ctrl+C`를 눌러 프로그램을 종료할 수 있습니다

#### 4. 채널 관리

```bash
# 채널 비활성화 (모니터링 중지, 삭제하지 않음)
python main.py --disable-channel CHANNEL_ID

# 채널 활성화 (모니터링 재개)
python main.py --enable-channel CHANNEL_ID

# 채널 삭제
python main.py --remove-channel CHANNEL_ID
```

### 모드 3: 일반 동영상 다운로드

YouTube 링크로 즉시 동영상을 다운로드할 수 있습니다:

```bash
# 기본 다운로드 (최고 화질)
python main.py --url "https://youtube.com/watch?v=VIDEO_ID"

# 화질 선택 (720p)
python main.py --url "https://youtube.com/watch?v=VIDEO_ID" --quality 720

# 1080p 다운로드
python main.py -u "URL" -q 1080

# 오디오만 추출 (MP3)
python main.py --url "URL" --audio-only

# 저장 경로 및 파일명 지정
python main.py -u "URL" -o "./my_videos" -f "my_video"
```

## 설정 파일

### channels.json

`channels.json` 파일은 자동으로 생성되며, CLI 명령어 또는 웹 인터페이스로 관리할 수 있습니다.

```json
{
  "channels": [
    {
      "id": "unique-channel-id-1",
      "name": "침착맨",
      "url": "https://www.youtube.com/@chimchakman_vod",
      "enabled": true,
      "download_format": "bestvideo[height<=720]+bestaudio/best[height<=720]"
    },
    {
      "id": "unique-channel-id-2",
      "name": "우왁굳",
      "url": "https://www.youtube.com/@woowakgood",
      "enabled": true,
      "download_format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    }
  ],
  "global_settings": {
    "check_interval_seconds": 60,
    "download_directory": "./downloads",
    "log_file": "./live_monitor.log",
    "split_mode": "time",
    "split_time_minutes": 30,
    "split_size_mb": 500
  }
}
```

### 설정 항목 설명

#### 채널별 설정
- `id`: 채널 고유 식별자 (자동 생성)
- `name`: 채널 표시 이름
- `url`: YouTube 채널 URL
- `enabled`: 모니터링 활성화 여부
- `download_format`: yt-dlp 다운로드 포맷

#### 전역 설정
- `check_interval_seconds`: 라이브 방송 체크 주기 (초 단위)
- `download_directory`: 다운로드 기본 디렉토리
- `log_file`: 로그 파일 경로
- `split_mode`: 비디오 분할 모드
  - `"time"`: 시간 기준 분할
  - `"size"`: 파일 크기 기준 분할
  - `"none"`: 분할하지 않음
- `split_time_minutes`: 시간 기준 분할 시 분 단위 (기본: 30분)
- `split_size_mb`: 크기 기준 분할 시 MB 단위 (기본: 500MB)

### 분할 설정 예제

**30분마다 분할:**
```json
{
  "split_mode": "time",
  "split_time_minutes": 30
}
```

**500MB마다 분할:**
```json
{
  "split_mode": "size",
  "split_size_mb": 500
}
```

**분할하지 않음:**
```json
{
  "split_mode": "none"
}
```

## 프로젝트 구조

```
yt-w/
├── src/
│   └── yt_monitor/          # 메인 패키지
│       ├── logger.py        # 로깅 설정
│       ├── youtube_client.py # YouTube API 클라이언트
│       ├── downloader.py    # 스트림 다운로더 (라이브용)
│       ├── video_downloader.py # 일반 동영상 다운로더
│       ├── channel_manager.py # 채널 관리
│       ├── multi_channel_monitor.py # 멀티 채널 모니터
│       └── web_api.py       # 웹 API
├── web/                     # 웹 인터페이스
│   └── index.html           # 웹 UI
├── test/                    # 테스트 디렉토리
├── docs/                    # 문서
├── main.py                  # CLI 엔트리포인트
├── web_server.py            # 웹 서버 엔트리포인트
├── channels.json            # 채널 설정 파일
└── channels.example.json    # 예제 채널 설정 파일
```

## 명령어 전체 목록

### 웹 서버
```bash
# 웹 서버 시작 (기본 포트: 8000)
python web_server.py

# 포트 변경
python web_server.py --port 3000

# 호스트 변경
python web_server.py --host 127.0.0.1 --port 8080
```

### CLI 명령어
```bash
# 채널 관리
python main.py --add-channel "이름" "URL"        # 채널 추가
python main.py --list-channels                   # 채널 목록
python main.py --enable-channel CHANNEL_ID       # 채널 활성화
python main.py --disable-channel CHANNEL_ID      # 채널 비활성화
python main.py --remove-channel CHANNEL_ID       # 채널 삭제

# 모니터링
python main.py                                   # 멀티 채널 모니터링 (기본)

# 동영상 다운로드
python main.py --url "URL"                       # 동영상 다운로드
python main.py --url "URL" --quality 720         # 화질 선택
python main.py --url "URL" --audio-only          # 오디오만 추출

# 설정 파일 지정
python main.py --channels channels.json          # 채널 설정 파일 지정
```

## 다운로드 파일 구조

### 라이브 방송 (멀티 채널)
```
downloads/
├── 침착맨/
│   ├── 침착맨_라이브_20250126_143000.mp4
│   └── 침착맨_라이브_20250126_200000.mp4
├── 우왁굳/
│   ├── 우왁굳_라이브_20250126_150000.mp4
│   └── 우왁굳_라이브_20250126_210000.mp4
└── ...
```

### 일반 동영상
- 파일명 지정 시: `지정한이름.mp4` 또는 `지정한이름.mp3`
- 자동 생성 시: `video_YYYYMMDD_HHMMSS.mp4` 또는 `.mp3`

## 로그

프로그램 실행 로그는 `live_monitor.log` 파일에 기록되며, 콘솔에도 동시에 출력됩니다.

## 주의사항

- 라이브 방송은 용량이 클 수 있으므로 충분한 저장 공간을 확보하세요
- 인터넷 연결이 안정적이어야 다운로드가 원활합니다
- 프로그램은 백그라운드에서 계속 실행되어야 라이브 방송을 감지할 수 있습니다
- YouTube의 이용 약관을 준수하여 개인적인 용도로만 사용하세요

## 문제 해결

### "ffmpeg not found" 에러
- ffmpeg를 설치해야 합니다 (위의 설치 방법 참조)

### 라이브 방송이 감지되지 않는 경우
- 채널 URL이 정확한지 확인하세요
- 인터넷 연결을 확인하세요
- `check_interval_seconds` 값을 조정해보세요

### 다운로드가 실패하는 경우
- 로그 파일 (`live_monitor.log`)을 확인하여 에러 메시지를 확인하세요
- yt-dlp를 최신 버전으로 업데이트해보세요: `uv add yt-dlp --upgrade`

### 채널이 모니터링되지 않는 경우
- `--list-channels`로 채널이 활성화되어 있는지 확인하세요
- 비활성화된 경우 `--enable-channel CHANNEL_ID`로 활성화하세요

## 개발자 가이드

### 코드 구조

이 프로젝트는 클린 코드 원칙을 따릅니다:

1. **단일 책임 원칙 (SRP)**: 각 모듈은 하나의 책임만 가집니다
   - `logger.py`: 로깅 설정
   - `youtube_client.py`: YouTube API 통신
   - `downloader.py`: 스트림 다운로드
   - `video_downloader.py`: 일반 동영상 다운로드
   - `channel_manager.py`: 채널 관리
   - `multi_channel_monitor.py`: 멀티 채널 모니터링
   - `web_api.py`: 웹 API

2. **의존성 주입 (DI)**: 테스트와 확장이 용이하도록 의존성을 주입합니다

3. **테스트 가능한 설계**: 모든 모듈이 독립적으로 테스트 가능합니다

### 새로운 기능 추가하기

1. 해당 모듈에 기능 구현
2. 테스트 코드 작성 (test/ 디렉토리)
3. 테스트 실행으로 검증
4. 문서 업데이트

### 테스트 실행

```bash
# 모든 테스트 실행
uv run pytest

# 상세 출력과 함께
uv run pytest -v

# 특정 테스트 파일만
uv run pytest test/test_channel_manager.py
```

### 문서

- [아키텍처 문서](docs/ARCHITECTURE.md): 전체 시스템 설계 설명
- [테스트 가이드](docs/TESTING.md): 테스트 작성 및 실행 방법
- [변경 이력](docs/history.md): 프로젝트 변경 이력

## 라이선스

개인적인 용도로 자유롭게 사용하세요.
