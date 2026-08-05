# 검증 시나리오: 의존성 업그레이드 후 영상 워크플로 회귀 검증

## 메타데이터
- **주제**: 최신 Python 의존성으로 Docker 재배포한 뒤 모니터링·다운로드·분할·병합 동작 보존
- **생성일**: 2026-08-05
- **대상 타입**: 복합(웹 + API + CLI)
- **시나리오 수**: 10건
- **실행 셸**: Windows PowerShell

---

## 공통 기준선

- 배포 전 `yt-web`, `yt-monitor`, `pot-provider` 컨테이너는 모두 `healthy`였다.
- `GET /health`는 HTTP 200과 `{"status":"ok"}`를 반환했다.
- `GET /api/monitor/status`는 `state=running`, `source=yt-monitor`, `is_running=true`를 반환했다.
- 루트 화면 제목은 `yt-w · 유튜브 다운로드와 라이브 자동 녹화`였다.
- 직접 런타임 의존성은 `bgutil-ytdlp-pot-provider 1.3.1`, `fastapi 0.122.0`, `python-multipart 0.0.22`, `uvicorn 0.38.0`, `yt-dlp 2026.3.17`이었다.
- 검증 영상은 yt-dlp 프로젝트가 문서와 테스트에서 사용하는 `https://www.youtube.com/watch?v=BaW_jenozKc`를 사용한다.
- 검증 시작 전 `GET /api/files?refresh=true`의 경로 집합을 저장하고, 종료 후 기존 경로 집합이 그대로 남았는지 비교한다.

---

## 시나리오 목록

### S01: 새 이미지 빌드와 컨테이너 정상 기동
- **대상**: CLI
- **도구**: PowerShell + Docker Compose
- **사전조건**: Docker Desktop이 실행 중이고 `pot-provider`가 healthy 상태다.
- **단계**:
  1. `docker compose up -d --build --force-recreate yt-monitor yt-web`를 실행한다.
  2. `docker compose ps`에서 `yt-monitor`, `yt-web`, `pot-provider` 상태를 확인한다.
  3. `yt-monitor`와 `yt-web`의 새 image ID와 시작 시각을 배포 전 기준선과 비교한다.
- **기대결과**: Python `3.15-rc-alpine` 기반 빌드와 재생성이 종료 코드 0으로 끝나고 세 컨테이너가 모두 `running/healthy`이며, `yt-monitor`와 `yt-web`은 새 이미지로 실행된다.
- **카테고리**: 정상

### S02: 컨테이너 런타임 의존성 적용
- **대상**: CLI
- **도구**: PowerShell + Docker
- **사전조건**: S01이 PASS 상태다.
- **단계**:
  1. `yt-web` 안에서 Python과 직접 의존성 설치 버전을 조회한다.
  2. `yt-monitor` 안에서 같은 버전을 조회한다.
  3. 두 결과를 `.python-version`과 `uv.lock`의 버전과 비교한다.
- **기대결과**: 두 컨테이너 모두 Python `3.15.x` prerelease와 `bgutil-ytdlp-pot-provider 1.3.1`, `fastapi 0.141.1`, `python-multipart 0.0.32`, `uvicorn 0.52.1`, `yt-dlp 2026.7.4`를 사용한다.
- **카테고리**: 회귀

### S03: 활성 채널의 실제 모니터링 주기
- **대상**: API + CLI
- **도구**: PowerShell + Docker
- **사전조건**: 활성 채널 1개가 구성되어 있고 `yt-monitor`가 재기동되었다.
- **단계**:
  1. `GET /api/monitor/status`를 호출해 heartbeat 상태를 읽는다.
  2. 재기동 이후 `yt-monitor` 로그에서 채널 모니터 시작과 `Checking for live stream...`을 찾는다.
  3. 같은 주기의 `No live stream found`, `Live stream detected`, 또는 명시적인 외부 인증 오류 중 하나를 확인한다.
- **기대결과**: API는 `is_running=true`, `state=running`, `source=yt-monitor`, `stale=false`, `active_channels=1`, `total_channels=1`을 반환하고, 로그에 실제 YouTube 확인 시도가 남는다. 외부 인증 오류는 앱 실패와 구분해 BLOCKED로 기록한다.
- **카테고리**: 정상

### S04: 실제 YouTube 영상 메타데이터 조회
- **대상**: API
- **도구**: PowerShell `Invoke-RestMethod`
- **사전조건**: YouTube와 POT provider에 접근 가능하다.
- **단계**:
  1. `POST /api/video/info`에 검증 영상 URL을 보낸다.
  2. HTTP 상태와 JSON 응답을 확인한다.
- **기대결과**: HTTP 200이며 `success=true`, 비어 있지 않은 `title`, 0보다 큰 `duration`을 반환한다.
- **카테고리**: 정상

### S05: 실제 라이브 스트림의 제한 시간 캡처
- **대상**: CLI
- **도구**: PowerShell + 컨테이너 `StreamDownloader` + Docker `ffprobe`
- **사전조건**: YouTube에 접근 가능하고 공개 라이브 채널이 방송 중이다.
- **단계**:
  1. 공개 24시간 라이브 채널에서 현재 live URL을 실제 `YouTubeClient`로 찾는다.
  2. 운영 채널 설정과 알림을 사용하지 않는 별도 프로세스에서 실제 `StreamDownloader`를 전용 `downloads/live_verify_stream` 폴더에 실행한다.
  3. 파일 크기가 증가하는 것을 두 번 이상 관측한 뒤 제한 시간에 `stop()`으로 ffmpeg를 종료한다.
  4. 생성 파일을 `ffprobe`로 읽어 duration과 video/audio stream을 확인한다.
- **기대결과**: live URL이 확인되고 캡처 파일이 실제로 생성·증가하며, 종료 후 0보다 큰 duration과 video stream을 가진 재생 가능한 파일로 남는다. 외부 방송 종료·지역 제한·인증 차단은 앱 실패와 구분해 BLOCKED로 기록한다.
- **카테고리**: 정상

### S06: 실제 영상 다운로드와 host 저장
- **대상**: API + CLI
- **도구**: PowerShell `Invoke-RestMethod` + Docker `ffprobe`
- **사전조건**: S04가 PASS 상태이고 downloads bind mount에 쓰기 가능하다.
- **단계**:
  1. `POST /api/download`에 검증 영상 URL, `quality=360`, `audio_only=false`를 보낸다.
  2. 응답의 `file_path`와 `filename`을 기록한다.
  3. host의 대응 파일이 존재하고 크기가 0보다 큰지 확인한다.
  4. `yt-web` 컨테이너의 `ffprobe`로 duration과 stream 정보를 읽는다.
- **기대결과**: HTTP 200과 `success=true`를 반환하고, MP4가 host에 저장되며 `ffprobe`가 0보다 큰 길이와 video stream을 보고한다.
- **카테고리**: 정상

### S07: 다운로드 영상 2등분
- **대상**: API + CLI
- **도구**: PowerShell `Invoke-RestMethod` + Docker `ffprobe`
- **사전조건**: S06의 다운로드 파일이 존재한다.
- **단계**:
  1. 다운로드 파일의 root 상대 경로로 `POST /api/split`에 `strategy=parts`, `parts=2`를 보낸다.
  2. `GET /api/split/jobs/{job_id}`를 폴링해 terminal 상태를 확인한다.
  3. 반환된 두 output 파일의 존재와 크기를 확인한다.
  4. 두 파일을 `ffprobe`로 읽어 각각 0보다 큰 duration과 video stream이 있는지 확인한다.
- **기대결과**: 작업이 `done`으로 끝나고 정확히 2개 파일이 생성되며 둘 다 유효한 영상이다.
- **카테고리**: 정상

### S08: 분할 영상 재병합
- **대상**: API + CLI
- **도구**: PowerShell `Invoke-RestMethod` + Docker `ffprobe`
- **사전조건**: S07의 두 분할 파일이 존재한다.
- **단계**:
  1. 두 output 경로를 순서대로 `POST /api/merge`에 보내고 `mode=concat`으로 실행한다.
  2. `GET /api/merge/jobs/{job_id}`를 폴링해 terminal 상태를 확인한다.
  3. 병합 결과 파일의 존재, 크기, duration, video stream을 `ffprobe`로 확인한다.
  4. 병합 결과 duration을 S06 원본과 비교한다.
- **기대결과**: 작업이 `done`으로 끝나고 결과가 유효한 영상이며, 결과 duration은 원본과 1초 이내로 일치한다.
- **카테고리**: 정상

### S09: 영상 중심 웹 화면 상호작용
- **대상**: 웹
- **도구**: Playwright
- **사전조건**: `http://127.0.0.1:8088/`에 접근 가능하다.
- **단계**:
  1. 루트 페이지로 이동하고 화면 제목과 기본 `영상 합치기` 화면을 확인한다.
  2. `영상 분할`, `다운로드`, `라이브 녹화` 메뉴를 차례로 클릭한다.
  3. 각 화면의 핵심 제목과 상태 영역이 렌더링되는지 snapshot으로 확인한다.
  4. 각 화면의 증거 스크린샷을 지정 경로에 저장한다.
- **기대결과**: 모든 메뉴 전환이 오류 없이 동작하고 각 화면의 핵심 제목과 실제 API 기반 상태가 표시된다.
- **카테고리**: 회귀

### S10: 영상 파일 오류 계약과 검증 산출물 정리
- **대상**: API
- **도구**: PowerShell `Invoke-WebRequest` + `Invoke-RestMethod`
- **사전조건**: S05~S08이 생성한 경로 목록과 검증 전 기존 파일 경로 집합을 보관하고 있다.
- **단계**:
  1. 존재하지 않는 `live-verify-does-not-exist.mp4`를 `GET /api/download/file/{filename}`으로 요청한다.
  2. S05~S08이 생성한 파일 경로만 `DELETE /api/files`로 삭제한다.
  3. `GET /api/files?refresh=true`를 호출해 검증 파일이 사라졌는지 확인한다.
  4. 검증 전 기존 파일 경로 집합이 모두 남았는지 비교한다.
- **기대결과**: 누락 파일 요청은 HTTP 404이며, 검증 산출물만 삭제되고 기존 파일은 변경되지 않는다.
- **카테고리**: 에러 + 회귀
