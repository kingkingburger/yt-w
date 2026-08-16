# 스튜디오 체크 컨트롤 리디자인 검증

- **검증일**: 2026-08-16
- **기준 브랜치**: `master`
- **변경 전 기준 커밋**: `eb9075e` (`feat(web): 인디 스튜디오 감성으로 콘솔 리디자인`)

## 범위

- 파일·그룹 선택 checkbox와 YouTube source radio의 공통 선택 마크
- YouTube 업로드의 아동용 checkbox
- 다운로드 완료와 병합 source 소진 상태의 장식 체크
- 현재 콘솔 테마와 선택 컨트롤의 접근성 계약 문서화

서버 API, 업로드 payload, 파일 선택 상태 로직은 변경하지 않았다.

## 구현 계약

- 실제 checkbox/radio `input`을 DOM과 접근성 트리에 유지하고 시각 표시만
  `.selection-mark`로 분리했다.
- checked checkbox는 `--studio-check-shape` polygon, 전기 보라 바탕, 애시드 라임
  실루엣과 오프셋 그림자를 사용한다.
- `checked`, `indeterminate`, radio, hover, `:focus-visible` 상태를 각각 구분한다.
- 장식용 완료 체크는 `aria-hidden="true"`로 두고, 모션 감소 설정에서는 애니메이션
  시간을 사실상 제거한다.
- 네이티브 모양으로 남아 있던 아동용 checkbox도 같은 컨트롤 계열로 통합했다.

## 자동 검증

| 검증 | 결과 |
|------|------|
| `uv run pytest tests/web/frontend -q` | 39 passed |
| `uv run pytest -q` | 359 passed, 1 skipped |
| 변경 파일 대상 `uv run pre-commit run --files ...` | Ruff, orphan pyc, frontend regression 통과 |
| `git diff --check` | whitespace 오류 없음 |

전체 테스트의 warning 1건은 FastAPI `TestClient`가 `httpx`를 사용하는 방식에 대한
기존 `StarletteDeprecationWarning`이다. 이번 UI 변경으로 새로 발생한 실패는 없다.

## Docker 적용 검증

`docker compose up -d --build --force-recreate yt-web`로 web 서비스만 다시 만들었다.

- `yt-web`: `healthy`, restart count `0`
- `GET http://127.0.0.1:8088/health`: `{"status":"ok"}`
- 배포된 `/static/app.css`: `--studio-check-shape` 포함
- 배포된 `/`: 아동용 커스텀 checkbox와 `aria-hidden` 완료 마크 포함

## 시각 검증 경계

현재 Codex 세션에 연결된 브라우저 인스턴스가 없어 렌더링 화면 캡처와 클릭 기반
비교는 수행하지 못했다. 따라서 이 기록은 DOM/CSS 계약, 자동 테스트, 배포된 정적
자산과 HTTP health까지의 검증이다. 실제 모양은 로컬 운영 화면
`http://127.0.0.1:8088`에서 최종 확인할 수 있다.

`docs/verify/2026-08-05-*` 리포트와 스크린샷은 당시 실행의 증빙이므로 새 테마로
덮어쓰지 않았다. `docs/history.md`도 v0 프로토타입 기록이라는 상단 경계를 유지했다.
