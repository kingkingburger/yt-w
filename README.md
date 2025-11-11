+  # 침착맨 라이브 방송 자동 다운로더

침착맨 채널의 라이브 방송을 자동으로 감지하고 로컬에 다운로드하는 프로그램입니다.

## 주요 기능

- 침착맨 채널의 라이브 방송 자동 감지
- 라이브 방송 자동 다운로드 (시작부터 끝까지)
- 설정 가능한 체크 주기
- 로그 기록 기능
- MP4 형식으로 자동 변환

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
  "download_format": "bestvideo+bestaudio/best"
}
```

### 설정 항목 설명

- `channel_url`: 모니터링할 유튜브 채널 URL
- `check_interval_seconds`: 라이브 방송 체크 주기 (초 단위)
- `download_directory`: 다운로드한 영상을 저장할 디렉토리
- `log_file`: 로그 파일 경로
- `video_quality`: 비디오 품질 설정
- `download_format`: yt-dlp 다운로드 포맷

## 사용 방법

프로그램을 실행하면 자동으로 채널을 모니터링합니다:

```bash
uv run main.py
```

또는

```bash
python main.py
```

프로그램이 실행되면:
1. 설정된 주기마다 채널을 체크합니다
2. 라이브 방송이 감지되면 자동으로 다운로드를 시작합니다
3. 다운로드가 완료되면 다시 모니터링을 계속합니다
4. `Ctrl+C`를 눌러 프로그램을 종료할 수 있습니다

## 다운로드 파일 이름

다운로드된 파일은 다음 형식으로 저장됩니다:
```
침착맨_라이브_YYYYMMDD_HHMMSS.mp4
```

예시: `침착맨_라이브_20250111_143000.mp4`

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

## 라이선스

개인적인 용도로 자유롭게 사용하세요.