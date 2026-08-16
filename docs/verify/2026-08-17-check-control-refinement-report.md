# 체크 컨트롤 정제 검증

- **검증일**: 2026-08-17
- **기준 브랜치**: `master`
- **변경 전 기준 커밋**: `181c838`
- **대체 대상**: `2026-08-16-studio-check-controls-report.md`의 시각 디자인

## 재작업 이유

이전 버전은 18px 선택 컨트롤 안에 비대칭 radius, polygon 체크, 회전, 확대,
애시드 라임 그림자와 drop-shadow를 동시에 적용했다. 아동용 설정 label에도 같은
그림자가 중첩됐고, 완료 마크는 `--ok-*` 성공색 대신 선택색을 사용했다. 작은 상태
표시가 화면의 정보보다 먼저 읽히는 것이 문제였다.

## 변경 결과

- checkbox는 정렬된 17px 박스, `--action` 채움, 흰 체크와 얕은 inset만 사용한다.
- indeterminate 가로선과 radio 원형 마크는 별도 상태로 유지한다.
- hover는 테두리와 옅은 배경만 바꾸고 위치·회전·확대를 사용하지 않는다.
- 아동용 설정 label은 선택 배경과 테두리만 남겨 내부 checkbox와 효과가 겹치지 않는다.
- 다운로드 완료와 source 소진 체크는 `--ok`, `--ok-tint`, `--ok-line` 성공색으로
  복귀하고 polygon, 형광 대비, 외부 그림자를 제거한다.
- 실제 checkbox/radio `input`, label 클릭 범위, `checked`/`indeterminate`,
  `:focus-visible`, `prefers-reduced-motion` 계약은 유지한다.

## 자동 검증

| 검증 | 결과 |
|------|------|
| `uv run pytest tests/web/frontend -q` | 39 passed |
| `uv run pytest -q` | 359 passed, 1 skipped |
| 변경 파일 대상 `uv run pre-commit run --files ...` | Ruff, orphan pyc, frontend regression 통과 |
| `git diff --check` | whitespace 오류 없음 |

전체 테스트의 warning 1건은 기존 `StarletteDeprecationWarning`이며 이번 CSS 변경으로
새로 발생한 실패는 없다.

## Docker 적용 검증

`docker compose up -d --build --force-recreate yt-web`로 web 서비스만 다시 만들었다.

- `yt-web`: `healthy`, restart count `0`
- `GET http://127.0.0.1:8088/health`: `{"status":"ok"}`
- 배포된 `/static/app.css`: `--studio-check-shape`와 `clip-path` 없음
- 배포된 `/static/app.css`: 표준 체크 선, `--ok-tint` 완료 마크, focus selector 포함

## 시각 검증 경계

로컬 Edge headless로 `1440x1200` 기본 병합 화면을 캡처했다. 선택 전 checkbox가
파일 행 높이에 맞게 정렬되고, 외부 그림자·회전·잘림 없이 표시되는 것을 확인했다.
현재 Codex 앱 브라우저 인스턴스는 없어 키보드·클릭 기반 상태 전환 캡처까지는
수행하지 못했다. DOM/CSS 계약, 자동 테스트, 배포된 정적 자산과 HTTP health까지
검증했으며 실제 화면은 `http://127.0.0.1:8088`에 반영돼 있다.
