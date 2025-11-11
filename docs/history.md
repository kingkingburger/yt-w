# 프로젝트 개발 히스토리

## 프로젝트 개요
유튜브 채널의 라이브 방송을 자동으로 감지하고 로컬에 다운로드하는 시스템

## 개발 요구사항
- 라이브 방송을 로컬에 다운받고 싶음
- 라이브 되는지 감지
- 라이브 시작 시 자동으로 로컬에 영상 저장
- yt-dlp 활용

## 개발 과정

### 1. 프로젝트 구조 확인
- Python 3.13 기반 프로젝트
- uv 패키지 매니저 사용
- 기본 구조: main.py, pyproject.toml, README.md

### 2. 의존성 설치
```bash
uv add yt-dlp
```
- yt-dlp 2025.10.22 버전 설치 완료

### 3. 핵심 기능 구현

#### 설정 파일 (config.json)
```json
{
  "channel_url": "https://www.youtube.com/@ChimChakMan_Data",
  "check_interval_seconds": 60,
  "download_directory": "./downloads",
  "log_file": "./live_monitor.log",
  "video_quality": "best",
  "download_format": "bestvideo+bestaudio/best"
}
```

#### 메인 프로그램 (main.py)
`LiveStreamMonitor` 클래스 구현:
- **라이브 감지 메서드**: 3가지 방법으로 라이브 스트림 감지
  1. `/live` 엔드포인트 체크 (가장 효과적)
  2. `/streams` 탭 체크 (멤버십 전용 영상 에러 무시)
  3. 메인 채널 페이지 체크

- **다운로드 메서드**:
  - 타임스탬프 기반 파일명 생성
  - 최고 화질 다운로드
  - 라이브 시작부터 녹화 (`live_from_start: True`)
  - MP4 형식으로 자동 변환

- **모니터링 루프**:
  - 60초마다 채널 체크
  - 라이브 감지 시 자동 다운로드
  - 다운로드 중에는 체크 중지
  - 완료 후 다시 모니터링 재개

### 4. 라이브 감지 문제 해결

#### 초기 문제
- 채널 페이지에서 라이브 감지가 안 됨
- 멤버십 전용 영상으로 인한 에러 발생

#### 해결 방법
1. **다중 감지 전략**: 3가지 방법으로 순차적으로 시도
2. **에러 핸들링**: `ignoreerrors: True` 옵션으로 멤버십 영상 에러 무시
3. **최적화된 엔드포인트**: `/live` 엔드포인트가 가장 효과적

#### 테스트 결과
```bash
Testing: https://www.youtube.com/@ChimChakMan_Data/live
Title: 알듯말듯 애매한 밸런스 게임 대회 진심으로 해보겠습니다. 특집
Video ID: 2qgyQPVu97M
Is Live: True  ✓ 성공!
```

### 5. 실제 운영 테스트

#### 첫 실행 결과
```
2025-11-11 14:17:31 - INFO - Live stream found via /live endpoint: 2qgyQPVu97M
2025-11-11 14:17:31 - INFO - Live stream detected! URL: https://www.youtube.com/watch?v=2qgyQPVu97M
2025-11-11 14:17:31 - INFO - Starting download of live stream
```

#### 다운로드 진행
- 파일명: `침착맨_라이브_20251111_141731.mp4`
- 저장 위치: `./downloads/`
- 비디오(303)와 오디오(140) 동시 다운로드
- 다운로드 속도: 약 600-700 KiB/s

### 6. 주요 기능

✅ **자동 라이브 감지**
- 60초 간격으로 채널 모니터링
- 3중 감지 시스템으로 안정성 확보

✅ **자동 다운로드**
- 라이브 감지 즉시 다운로드 시작
- 라이브 시작 시점부터 녹화
- 최고 화질 자동 선택

✅ **로깅 시스템**
- 콘솔 + 파일 동시 로깅
- 모든 활동 기록

✅ **안정성**
- 에러 발생 시에도 모니터링 계속
- 멤버십 전용 영상 자동 스킵
- Ctrl+C로 안전한 종료

## 기술 스택
- **언어**: Python 3.13
- **패키지 매니저**: uv
- **주요 라이브러리**: yt-dlp 2025.10.22
- **필수 도구**: ffmpeg (비디오/오디오 병합)

## 파일 구조
```
yt-w/
├── main.py              # 메인 프로그램
├── config.json          # 설정 파일
├── README.md            # 사용 설명서
├── docs/
│   └── history.md       # 개발 히스토리 (이 파일)
├── downloads/           # 다운로드 폴더
│   └── 침착맨_라이브_YYYYMMDD_HHMMSS.mp4
└── live_monitor.log     # 로그 파일
```

## 성공 요인
1. **다중 감지 전략**: 여러 방법을 시도하여 안정성 확보
2. **에러 처리**: 멤버십 영상 등 예외 상황 대응
3. **최적화된 API 사용**: `/live` 엔드포인트가 가장 효과적
4. **실시간 로깅**: 문제 발생 시 빠른 디버깅 가능

## 향후 개선 가능 사항
- [ ] 다운로드 완료 알림 기능 (이메일, 디스코드 등)
- [ ] 여러 채널 동시 모니터링
- [ ] 다운로드 화질 선택 옵션 추가
- [ ] 자동 업로드 기능 (클라우드 스토리지)
- [ ] 웹 대시보드 UI
- [ ] Docker 컨테이너화
- [ ] 시스템 서비스로 등록 (백그라운드 실행)

## 참고 링크
- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp
