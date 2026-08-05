# 검증 결과: 의존성 업그레이드 후 영상 워크플로 회귀 검증

**일시**: 2026-08-05 11:10 +09:00

**대상 타입**: 복합(웹 + API + CLI)
**시나리오 파일**: `docs/verify/2026-08-05-dependency-upgrade-video-workflows-scenarios.md`

---

## 요약: 총 10건 / PASS 10 / FAIL 0 / FLAKY 0 / BLOCKED 0

| # | 시나리오 | 카테고리 | 결과 | 수정 시도 | 비고 |
|---|---------|---------|------|----------|------|
| S01 | 새 이미지 빌드와 컨테이너 정상 기동 | 정상 | PASS | 0 | Python 3.15.0b4 이미지로 `yt-web`/`yt-monitor` 재생성 |
| S02 | 컨테이너 런타임 의존성 적용 | 회귀 | PASS | 0 | 두 컨테이너의 Python·직접 의존성 버전 일치 |
| S03 | 활성 채널의 실제 모니터링 주기 | 정상 | PASS | 0 | heartbeat 정상, 실제 YouTube 확인 주기 반복 완료 |
| S04 | 실제 YouTube 영상 메타데이터 조회 | 정상 | PASS | 0 | 사용자 승인 대체 입력으로 HTTP 200, duration 19초 |
| S05 | 실제 라이브 스트림의 제한 시간 캡처 | 정상 | PASS | 0 | H.264/AAC 라이브 MP4 24.99초 저장 확인 |
| S06 | 실제 영상 다운로드와 host 저장 | 정상 | PASS | 0 | AV1/AAC MP4 535,458 bytes 저장 확인 |
| S07 | 다운로드 영상 2등분 | 정상 | PASS | 0 | 2개 part 생성 및 ffprobe 성공 |
| S08 | 분할 영상 재병합 | 정상 | PASS | 0 | 현재와 배포 전 이미지가 동일한 duration 재현 |
| S09 | 영상 중심 웹 화면 상호작용 | 회귀 | PASS | 0 | 4개 화면 클릭·렌더링, 브라우저 오류 0건 |
| S10 | 영상 파일 오류 계약과 검증 산출물 정리 | 에러·회귀 | PASS | 0 | 404 유지, 검증 MP4 6개와 빈 폴더 정리 |

**수정 예산 사용**: 세션 합계 0/20회 — 애플리케이션 코드 자동 수정 없음

---

## 상세 결과

### S01: 새 이미지 빌드와 컨테이너 정상 기동 — PASS

**실행 정보**
- 대상: CLI
- 도구: PowerShell + Docker Compose

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | `docker compose up -d --build --force-recreate yt-monitor yt-web` | OK | 종료 코드 0, 두 서비스 `Built`/`Recreated`/`Started` |
| 2 | health 대기 | OK | `yt-web`, `yt-monitor`, `pot-provider` 모두 `running/healthy` |
| 3 | image ID 확인 | OK | `yt-web=5cf1bf5...`, `yt-monitor=2df1444...`; 배포 전 image ID와 다름 |

**판정 근거**
- 기대: `python:3.15-rc-alpine` 태그가 현재 해석한 Python 3.15.0b4 이미지로 재생성되고 세 컨테이너가 healthy
- 실제: `yt-web`과 `yt-monitor`는 새 시작 시각과 image ID로 교체됐고 `pot-provider`는 기존 healthy 컨테이너를 유지함

### S02: 컨테이너 런타임 의존성 적용 — PASS

**실행 정보**
- 대상: CLI
- 도구: Docker `exec`

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | `yt-web` 버전 조회 | OK | Python 3.15.0b4 |
| 2 | `yt-monitor` 버전 조회 | OK | Python 3.15.0b4 |
| 3 | 직접 의존성 비교 | OK | 두 컨테이너 모두 아래 버전과 일치 |

직접 런타임 의존성:

- `bgutil-ytdlp-pot-provider==1.3.1`
- `fastapi==0.141.1`
- `python-multipart==0.0.32`
- `uvicorn==0.52.1`
- `yt-dlp==2026.7.4`

**판정 근거**
- 기대: Docker 런타임이 새 Python과 lockfile 버전을 실제 사용
- 실제: 두 컨테이너의 설치 메타데이터가 모두 일치함

### S03: 활성 채널의 실제 모니터링 주기 — PASS

**실행 정보**
- 대상: API + CLI
- 도구: `GET /api/monitor/status`, host log

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | heartbeat 조회 | OK | `is_running=true`, `state=running`, `source=yt-monitor`, `stale=false` |
| 2 | 채널 수 확인 | OK | `active_channels=1`, `total_channels=1` |
| 3 | 실제 YouTube 확인 로그 | OK | `Checking for live stream...` 뒤 `No live stream found`가 여러 주기 반복 |

**판정 근거**
- 기대: 재기동 후 활성 채널을 실제로 확인하고 heartbeat를 계속 갱신
- 실제: 약 90초 간격으로 실제 확인 주기가 반복됐고 최종 heartbeat age는 1초 미만

### S04: 실제 YouTube 영상 메타데이터 조회 — PASS

**실행 정보**
- 대상: API
- 도구: `POST /api/video/info`

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | 최초 yt-dlp 테스트 영상 호출 | 외부 입력 실패 | `BaW_jenozKc`가 두 번 모두 HTTP 500 detail `Video unavailable` |
| 2 | 대체 입력 사전 확인 | OK | 19초 공개 영상과 597초 README 예제 모두 HTTP 200 |
| 3 | 사용자 승인 대체 입력 실행 | OK | HTTP 200, `success=true`, title 비어 있지 않음, `duration=19` |

**판정 근거**
- 기대: 실제 YouTube 메타데이터 조회 성공
- 실제: 삭제된 외부 입력은 재시도 후 사용자 승인으로 교체했고, 승인된 입력은 정상 계약을 반환함

### S05: 실제 라이브 스트림의 제한 시간 캡처 — PASS

**실행 정보**
- 대상: CLI
- 도구: `YouTubeClient`, `StreamDownloader`, `ffprobe`

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | 공개 라이브 탐지 | OK | `streams_tab`에서 live video ID 탐지 |
| 2 | 실제 stream-copy 캡처 | OK | 크기 표본 `524336 → 786480 → 1048624` bytes |
| 3 | 제한 시간 종료 | OK | signal 15로 ffmpeg 종료, worker 종료, 잔존 ffmpeg 없음 |
| 4 | 결과 검증 | OK | 1,082,559 bytes, H.264 video + AAC audio, duration 24.986666초 |

**판정 근거**
- 기대: 운영 채널/알림을 바꾸지 않고 실제 라이브 데이터가 파일로 증가하고 재생 가능함
- 실제: 전용 폴더에서 실제 네트워크 스트림이 증가했고 종료 후 `ffprobe`가 video/audio를 정상 인식함
- 참고: 제한 시간에 의도적으로 ffmpeg를 종료했기 때문에 `StreamDownloader.download()`는 false를 반환했지만, 시나리오의 성공 기준은 bounded capture 파일의 유효성이다.

### S06: 실제 영상 다운로드와 host 저장 — PASS

**실행 정보**
- 대상: API + CLI
- 도구: `POST /api/download`, host bind mount, `ffprobe`

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | 360p 영상 다운로드 | OK | API `success=true` |
| 2 | host 파일 확인 | OK | `web_downloads/video_20260805_020315.mp4`, 535,458 bytes |
| 3 | 미디어 검증 | OK | AV1 video + AAC audio, duration 19.063583초 |

**판정 근거**
- 기대: API가 실제 YouTube 파일을 downloads bind mount에 저장
- 실제: Windows host에서 파일을 확인했고 컨테이너 `ffprobe`로 유효한 MP4임을 확인함
- 검증 도구 보정: API의 `downloads/web_downloads/...` 경로를 처음에 `/app/downloads/...`로만 가정해 host 경로를 중복 계산했으며, 실제 응답 경계에 맞춰 매핑을 바로잡았다. 제품 실패는 아니었다.

### S07: 다운로드 영상 2등분 — PASS

**실행 정보**
- 대상: API + CLI
- 도구: `POST /api/split`, job polling, `ffprobe`

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | 2등분 작업 제출 | OK | job `6f3e509f178c` |
| 2 | terminal 상태 확인 | OK | `status=done`, `completed_parts=2/2` |
| 3 | part 1 검증 | OK | 283,225 bytes, video/audio, duration 9.543401초 |
| 4 | part 2 검증 | OK | 378,179 bytes, video/audio, duration 14.063560초 |

**판정 근거**
- 기대: 정확히 2개 파일이 생성되고 둘 다 재생 가능한 영상
- 실제: 두 출력 모두 존재하며 `ffprobe`가 video/audio stream을 인식함

### S08: 분할 영상 재병합 — PASS

**실행 정보**
- 대상: API + CLI
- 도구: `POST /api/merge`, job polling, `ffprobe`, 배포 전 커밋 이미지 비교

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | concat 병합 | OK | job `4f4de254822e`, `status=done`, AV1/AAC, 655,806 bytes |
| 2 | duration 확인 | 기준 불일치 | 현재 병합 23.606961초, 원본보다 4.543378초 김 |
| 3 | 즉시 재실행 | 동일 | retry job `9ce960d6caff`, 23.606961초 |
| 4 | 배포 전 이미지 재현 | 동일 | Python 3.13/구 의존성 이미지도 part `9.543401/14.063560`, merge `23.606961` |
| 5 | 사용자 판정 확인 | OK | 기존 동작과 동일한 것을 회귀 PASS 기준으로 승인 |

**판정 근거**
- 기대: 병합이 완료되고 현재 동작이 배포 전과 같음
- 실제: 현재와 이전 이미지가 같은 원본에서 완전히 같은 part/merge duration을 반환함
- 남은 특성: `-c copy` 분할은 keyframe 경계 때문에 두 번째 part와 재병합 결과가 원본보다 길어질 수 있다. 이번 업그레이드 회귀는 아니다.

### S09: 영상 중심 웹 화면 상호작용 — PASS

**실행 정보**
- 대상: 웹
- 도구: 인앱 브라우저 Playwright

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | 루트/영상 합치기 | OK | 기존 title 일치, 두 병합 job 완료 표시 |
| 2 | 영상 나누기 클릭 | OK | `2개 파일 분할 완료`, `2/2`, stream-copy 안내 표시 |
| 3 | 다운로드 클릭 | OK | YouTube URL 입력과 `영상 정보 보기` 버튼 표시 |
| 4 | 라이브 녹화 클릭 | OK | `녹화 감시 중`, 감시/전체 채널 `1/1` 표시 |
| 5 | 브라우저 오류 로그 | OK | error 0건 |

**판정 근거**
- 기대: 영상 중심 메뉴가 실제 클릭으로 전환되고 API 상태가 화면에 렌더링됨
- 실제: 네 화면 모두 정상 전환됐고 monitor/cookie/disk 상태와 실제 job 결과가 표시됨
- 스크린샷:
  - `docs/verify/screenshots/2026-08-05-dependency-upgrade-video-workflows/S09-1-merge.png`
  - `docs/verify/screenshots/2026-08-05-dependency-upgrade-video-workflows/S09-2-split.png`
  - `docs/verify/screenshots/2026-08-05-dependency-upgrade-video-workflows/S09-3-download.png`
  - `docs/verify/screenshots/2026-08-05-dependency-upgrade-video-workflows/S09-4-monitor.png`

### S10: 영상 파일 오류 계약과 검증 산출물 정리 — PASS

**실행 정보**
- 대상: API + host filesystem
- 도구: `GET /api/download/file/{filename}`, `DELETE /api/files`

**단계별 실행 결과**

| 단계 | 행동 | 결과 | 관측값 |
|------|------|------|--------|
| 1 | 없는 영상 요청 | OK | HTTP 404 |
| 2 | 생성 경로 검증 | OK | 허용된 테스트 패턴의 MP4 6개, 기존 경로와 교집합 없음 |
| 3 | API 삭제 | OK | `deleted_count=6` |
| 4 | host/API 재확인 | OK | 검증 파일 0개, 검증 전 기존 경로 누락 0개 |
| 5 | 전용 빈 폴더 정리 | OK | `downloads/live_verify_stream` 제거 |

**판정 근거**
- 기대: 오류 계약을 유지하고 이번 검증 산출물만 제거
- 실제: 404가 유지됐고 검증 전·후 기존 영상 경로 집합은 모두 빈 집합으로 동일함

---

## 회귀 가드

- Python 3.15.0b4 기반 새 Docker 이미지 안에서 전체 테스트 실행: **291 passed, 1 warning**
- warning: Starlette가 기존 `httpx` TestClient 사용을 deprecated로 안내함. 현재 테스트/실서비스 동작 실패는 없음.
- `uv lock --check`: 42개 패키지 해석 성공
- `docker compose config --quiet`: 성공
- `git diff --check`: whitespace 오류 없음(CRLF 변환 안내만 존재)
- 자동 수정이 없으므로 수정 후 시나리오 재실행 회귀 가드는 해당 없음

---

## 수정 범위 점검

- 애플리케이션 코드 자동 수정: 없음
- 시나리오 파일 변경:
  - 삭제된 외부 테스트 영상을 사용자 승인 후 현재 조회 가능한 19초 영상으로 교체
  - 현재/이전 이미지 비교 결과와 사용자 승인에 따라 S08 회귀 기준을 기존 동작 parity로 구체화
- 생성한 증거: 이 보고서와 S09 스크린샷 4장
- 화이트리스트 위반 여부: 없음
- 검증 중 생성한 영상 파일: 모두 삭제 완료

---

## 실행 환경

- 사용한 셸: Windows PowerShell
- 배포 명령: `docker compose up -d --build --force-recreate yt-monitor yt-web`
- 실행 중 서비스: `autoheal`, `pot-provider`, `yt-monitor`, `yt-web` — 모두 healthy
- 검증을 위해 새로 띄운 별도 서버: 없음
- 배포 전 비교 이미지/worktree: 비교 후 제거 완료
- 스크린샷 디렉터리: `docs/verify/screenshots/2026-08-05-dependency-upgrade-video-workflows/`
