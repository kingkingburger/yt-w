+  #  YouTube 다운로더 (라이브 + 일반 동영상)

YouTube 라이브 방송 자동 모니터링 및 일반 동영상 다운로드를 지원하는 프로그램입니다.

이 프로젝트는 **클린 코드 원칙**과 **SOLID 원칙**을 적용하여 설계되었으며,
모듈화된 구조로 유지보수와 확장이 용이합니다.

## 주요 기능

### 라이브 방송 모니터링
- 채널의 라이브 방송 자동 감지
- 라이브 방송 자동 다운로드 (시작부터 끝까지)
- 설정 가능한 체크 주기
- 실시간 영상 분할 (시간/크기 기준)

### 일반 동영상 다운로드 (NEW!)
- YouTube 링크로 즉시 다운로드
- 화질 선택 (2160p, 1440p, 1080p, 720p, 480p, 360p)
- 오디오 전용 다운로드 (MP3 추출)
- CLI 인터페이스

### 공통 기능
- 로그 기록 기능
- MP4 형식으로 자동 변환
- 완전한 테스트 커버리지 (51개 단위 테스트)
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

## 설정

`config.json` 파일을 수정하여 설정을 변경할 수 있습니다:

```json
{
  "channel_url": "https://www.youtube.com/@chimchakman_vod",
  "check_interval_seconds": 60,
  "download_directory": "./downloads",
  "log_file": "./live_monitor.log",
  "video_quality": "best",
  "download_format": "bestvideo+bestaudio/best",
  "split_mode": "time",
  "split_time_minutes": 30,
  "split_size_mb": 500
}
```

### 설정 항목 설명

- `channel_url`: 모니터링할 유튜브 채널 URL
- `check_interval_seconds`: 라이브 방송 체크 주기 (초 단위)
- `download_directory`: 다운로드한 영상을 저장할 디렉토리
- `log_file`: 로그 파일 경로
- `video_quality`: 비디오 품질 설정
- `download_format`: yt-dlp 다운로드 포맷
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

**100MB마다 분할:**
```json
{
  "split_mode": "size",
  "split_size_mb": 100
}
```

**분할하지 않음:**
```json
{
  "split_mode": "none"
}
```

### 실시간 분할 기능

시간 또는 크기 기반 분할을 선택하면, 프로그램은 다운로드와 동시에 실시간으로 비디오를 분할합니다:

- **시간 기반 분할**: 지정한 시간(예: 30분)이 지나면 자동으로 새 파일로 전환됩니다.
- **크기 기반 분할**: 현재 파일이 지정한 크기(예: 100MB)에 도달하면 자동으로 새 파일로 전환됩니다.

이 방식은 FFmpeg의 segment 기능을 사용하여 라이브 스트림을 다운로드하면서 동시에 분할하므로, 긴 라이브 방송도 효율적으로 관리할 수 있습니다.

## 프로젝트 구조

```
yt-w/
├── src/
│   └── yt_monitor/          # 메인 패키지
│       ├── config.py        # 설정 관리
│       ├── logger.py        # 로깅 설정
│       ├── youtube_client.py # YouTube API 클라이언트
│       ├── downloader.py    # 스트림 다운로더 (라이브용)
│       ├── video_downloader.py # 일반 동영상 다운로더 (NEW!)
│       └── monitor.py       # 라이브 스트림 모니터
├── test/                    # 테스트 디렉토리
│   ├── test_config.py
│   ├── test_youtube_client.py
│   ├── test_downloader.py
│   ├── test_video_downloader.py  # NEW!
│   └── test_monitor.py
├── docs/                    # 문서
│   ├── ARCHITECTURE.md      # 아키텍처 문서
│   ├── TESTING.md          # 테스트 가이드
│   └── history.md          # 변경 이력
├── main.py                  # 엔트리포인트 (CLI 지원)
└── config.json              # 설정 파일
```

## 사용 방법

### 모드 1: 라이브 방송 모니터링 (기본)

프로그램을 실행하면 자동으로 채널을 모니터링합니다:

```bash
uv run main.py
# 또는
python main.py
```

프로그램이 실행되면:
1. 설정된 주기마다 채널을 체크합니다
2. 라이브 방송이 감지되면 자동으로 다운로드를 시작합니다
3. 다운로드가 완료되면 다시 모니터링을 계속합니다
4. `Ctrl+C`를 눌러 프로그램을 종료할 수 있습니다

### 모드 2: 일반 동영상 다운로드 (NEW!)

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

# 짧은 옵션 조합
python main.py -u "URL" -q 720 -o "./downloads"
```

#### CLI 옵션 설명

| 옵션 | 짧은 형식 | 설명 | 기본값 |
|------|----------|------|--------|
| `--url` | `-u` | 다운로드할 YouTube URL | - |
| `--quality` | `-q` | 화질 선택 (2160/1440/1080/720/480/360/best) | best |
| `--audio-only` | `-a` | 오디오만 추출 (MP3) | False |
| `--output` | `-o` | 저장 디렉토리 | ./downloads |
| `--filename` | `-f` | 파일명 (확장자 제외) | 자동 생성 |
| `--config` | `-c` | 설정 파일 경로 | config.json |

#### 사용 예시

```bash
# 음악 다운로드 (MP3)
python main.py -u "https://youtube.com/watch?v=dQw4w9WgXcQ" -a

# 4K 화질 다운로드
python main.py -u "URL" -q 2160

# 여러 옵션 조합
python main.py \
  -u "https://youtube.com/watch?v=VIDEO_ID" \
  -q 1080 \
  -o "./my_downloads" \
  -f "awesome_video"
```

## 테스트 실행

```bash
# 모든 테스트 실행
uv run pytest

# 상세 출력과 함께
uv run pytest -v

# 특정 테스트 파일만
uv run pytest test/test_config.py
```

## 다운로드 파일 이름

### 라이브 방송
다운로드된 라이브 방송 파일은 다음 형식으로 저장됩니다:
```
_라이브_YYYYMMDD_HHMMSS.mp4
```
예시: `_라이브_20250111_143000.mp4`

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

## 개발자 가이드

### 코드 구조

이 프로젝트는 클린 코드 원칙을 따릅니다:

1. **단일 책임 원칙 (SRP)**: 각 모듈은 하나의 책임만 가집니다
   - `config.py`: 설정 관리
   - `logger.py`: 로깅 설정
   - `youtube_client.py`: YouTube API 통신
   - `downloader.py`: 스트림 다운로드
   - `monitor.py`: 전체 프로세스 조율

2. **의존성 주입 (DI)**: 테스트와 확장이 용이하도록 의존성을 주입합니다

3. **테스트 가능한 설계**: 모든 모듈이 독립적으로 테스트 가능합니다

### 새로운 기능 추가하기

1. 해당 모듈에 기능 구현
2. 테스트 코드 작성 (test/ 디렉토리)
3. 테스트 실행으로 검증
4. 문서 업데이트

### 문서

- [아키텍처 문서](docs/ARCHITECTURE.md): 전체 시스템 설계 설명
- [테스트 가이드](docs/TESTING.md): 테스트 작성 및 실행 방법
- [변경 이력](docs/history.md): 프로젝트 변경 이력

## 라이선스

개인적인 용도로 자유롭게 사용하세요.