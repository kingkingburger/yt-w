# Discord 모니터링 알림 시스템 구현 계획

> 작성일: 2026-04-09
> 목표: Docker에 직접 들어가지 않고 디스코드로 모든 상태를 실시간 알림 받기

---

## 1. 현재 상태 분석

### 서비스 구조 (docker-compose.yml)
```
pot-provider  — PO Token 사이드카 (brainicism/bgutil-ytdlp-pot-provider)
yt-monitor   — 멀티 채널 라이브 감지 + 다운로드 (monitoring.py)
yt-web       — FastAPI 웹 서버 (main.py → web_api.py)
```

### 현재 부재한 것
- `/health` 엔드포인트 없음
- Docker HEALTHCHECK 없음
- 알림/웹훅 시스템 전혀 없음
- 에러 발생 시 로그 파일에만 기록 (logger.py, TimedRotatingFileHandler)
- 컨테이너 상태 확인 수단 = `docker ps` + `docker logs`뿐

---

## 2. 알림 대상 이벤트

| 이벤트 | 심각도 | 발생 위치 | 현재 코드 |
|--------|--------|-----------|-----------|
| 컨테이너 시작 | INFO | yt-monitor 시작 시 | `MultiChannelMonitor.start()` |
| 라이브 감지 | INFO | 채널별 모니터 루프 | `ChannelMonitorThread._handle_live_stream()` L113-121 |
| 다운로드 완료 | INFO | 채널별 모니터 루프 | `ChannelMonitorThread._handle_live_stream()` L129 |
| 다운로드 실패 | ERROR | 채널별 모니터 루프 | `ChannelMonitorThread._handle_live_stream()` L131 |
| 다운로드 에러(예외) | ERROR | StreamDownloader | `StreamDownloader.download()` L58-59 |
| 쿠키 만료 | WARN | cookie_helper | `validate_cookies()` 반환값 `valid=False` |
| 모니터 루프 에러 | ERROR | 채널별 모니터 루프 | `ChannelMonitorThread._monitor_loop()` L95 |
| 컨테이너 종료 | WARN | shutdown signal | `MultiChannelMonitor.start()` L194 KeyboardInterrupt |

---

## 3. 구현 계획

### 3-1. 새 파일: `src/yt_monitor/discord_notifier.py`

Discord Webhook을 통해 알림을 전송하는 순수 모듈. 외부 라이브러리 없이 `urllib`만 사용.

```python
"""Discord webhook notification module."""

import json
import os
import threading
import time
import urllib.request
import urllib.error
from typing import Optional
from enum import Enum


class NotificationLevel(Enum):
    """Notification severity levels with Discord embed colors."""
    INFO = 0x3498DB      # 파란색
    SUCCESS = 0x2ECC71   # 초록색
    WARNING = 0xF39C12   # 주황색
    ERROR = 0xE74C3C     # 빨간색


class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        service_name: str = "yt-monitor",
    ):
        self._webhook_url: str = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")
        self._service_name: str = service_name
        self._enabled: bool = bool(self._webhook_url)
        self._rate_limit_until: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def send(
        self,
        title: str,
        description: str,
        level: NotificationLevel = NotificationLevel.INFO,
        fields: Optional[list[dict[str, str]]] = None,
    ) -> bool:
        """
        Discord embed 메시지를 전송한다.

        Args:
            title: 알림 제목
            description: 알림 본문
            level: 심각도 (INFO/SUCCESS/WARNING/ERROR)
            fields: 추가 필드 [{"name": "...", "value": "...", "inline": True}]

        Returns:
            전송 성공 여부. webhook_url 미설정 시 False.
        """
        if not self._enabled:
            return False

        # Rate limit 대기
        with self._lock:
            now = time.time()
            if now < self._rate_limit_until:
                time.sleep(self._rate_limit_until - now)

        embed = {
            "title": title,
            "description": description,
            "color": level.value,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": self._service_name},
        }

        if fields:
            embed["fields"] = fields

        payload = json.dumps({"embeds": [embed]}).encode("utf-8")

        request = urllib.request.Request(
            self._webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                # Rate limit 헤더 처리
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) == 0:
                    reset_after = float(response.headers.get("X-RateLimit-Reset-After", "1"))
                    with self._lock:
                        self._rate_limit_until = time.time() + reset_after
                return True

        except urllib.error.HTTPError as error:
            if error.code == 429:
                # Rate limited — retry-after 헤더 파싱
                retry_after = float(error.headers.get("Retry-After", "5"))
                with self._lock:
                    self._rate_limit_until = time.time() + retry_after
            return False

        except (urllib.error.URLError, OSError):
            return False

    def notify_live_detected(self, channel_name: str, stream_url: str, title: str) -> bool:
        """라이브 방송 감지 알림."""
        return self.send(
            title=f"🔴 라이브 감지: {channel_name}",
            description=f"**{title}**\n{stream_url}",
            level=NotificationLevel.INFO,
        )

    def notify_download_complete(self, channel_name: str, title: str) -> bool:
        """다운로드 완료 알림."""
        return self.send(
            title=f"✅ 다운로드 완료: {channel_name}",
            description=title,
            level=NotificationLevel.SUCCESS,
        )

    def notify_download_failed(self, channel_name: str, error_message: str) -> bool:
        """다운로드 실패 알림."""
        return self.send(
            title=f"❌ 다운로드 실패: {channel_name}",
            description=f"```{error_message[:1500]}```",
            level=NotificationLevel.ERROR,
        )

    def notify_cookie_expired(self, message: str) -> bool:
        """쿠키 만료 알림."""
        return self.send(
            title="⚠️ 쿠키 만료",
            description=message,
            level=NotificationLevel.WARNING,
        )

    def notify_monitor_started(self, channel_count: int) -> bool:
        """모니터 시작 알림."""
        return self.send(
            title="🟢 모니터 시작",
            description=f"{channel_count}개 채널 모니터링 시작",
            level=NotificationLevel.SUCCESS,
        )

    def notify_monitor_stopped(self, reason: str = "shutdown signal") -> bool:
        """모니터 종료 알림."""
        return self.send(
            title="🔴 모니터 종료",
            description=f"사유: {reason}",
            level=NotificationLevel.WARNING,
        )

    def notify_error(self, channel_name: str, error_message: str) -> bool:
        """일반 에러 알림."""
        return self.send(
            title=f"⚠️ 에러: {channel_name}",
            description=f"```{error_message[:1500]}```",
            level=NotificationLevel.ERROR,
        )


# 모듈 레벨 싱글턴 (Logger 패턴과 동일)
_notifier: Optional[DiscordNotifier] = None


def get_notifier() -> DiscordNotifier:
    """모듈 레벨 싱글턴 notifier를 반환한다."""
    global _notifier
    if _notifier is None:
        _notifier = DiscordNotifier()
    return _notifier
```

**설계 원칙:**
- 외부 의존성 0개 (urllib만 사용, requests/aiohttp 불필요)
- 비동기 불필요 — 모니터링 스레드에서 호출, 10초 timeout이면 충분
- Rate limit 처리 내장 (Discord 429 대응)
- `DISCORD_WEBHOOK_URL` 환경변수 미설정 시 모든 메서드가 `False` 반환 (no-op)

---

### 3-2. 기존 파일 수정: `src/yt_monitor/multi_channel_monitor.py`

#### 수정 1: import 추가

```python
# 기존
from .logger import Logger
from .youtube_client import YouTubeClient

# 추가
from .discord_notifier import get_notifier
```

#### 수정 2: `ChannelMonitorThread._handle_live_stream()` (L113-135)

**현재:**
```python
def _handle_live_stream(self, stream_url: str, title: str) -> None:
    self.logger.info(f"[{self.channel.name}] Live stream detected: {stream_url}")
    self.is_downloading = True

    try:
        success = self.downloader.download(
            stream_url=stream_url, filename_prefix=f"{self.channel.name}_라이브"
        )

        if success:
            self.logger.info(f"[{self.channel.name}] Download finished")
        else:
            self.logger.warning(f"[{self.channel.name}] Download failed")

    finally:
        self.is_downloading = False
```

**변경 후:**
```python
def _handle_live_stream(self, stream_url: str, title: str) -> None:
    self.logger.info(f"[{self.channel.name}] Live stream detected: {stream_url}")
    self.is_downloading = True
    notifier = get_notifier()

    notifier.notify_live_detected(
        channel_name=self.channel.name,
        stream_url=stream_url,
        title=title,
    )

    try:
        success = self.downloader.download(
            stream_url=stream_url, filename_prefix=f"{self.channel.name}_라이브"
        )

        if success:
            self.logger.info(f"[{self.channel.name}] Download finished")
            notifier.notify_download_complete(
                channel_name=self.channel.name,
                title=title,
            )
        else:
            self.logger.warning(f"[{self.channel.name}] Download failed")
            notifier.notify_download_failed(
                channel_name=self.channel.name,
                error_message="다운로드가 실패했습니다 (success=False)",
            )

    except Exception as e:
        notifier.notify_download_failed(
            channel_name=self.channel.name,
            error_message=str(e),
        )
        raise

    finally:
        self.is_downloading = False
```

#### 수정 3: `ChannelMonitorThread._monitor_loop()` (L89-97)

**현재:**
```python
def _monitor_loop(self) -> None:
    while self.is_running:
        try:
            self._monitor_cycle()
        except Exception as e:
            self.logger.error(f"Error monitoring {self.channel.name}: {e}")

        time.sleep(self.global_settings.check_interval_seconds)
```

**변경 후:**
```python
def _monitor_loop(self) -> None:
    while self.is_running:
        try:
            self._monitor_cycle()
        except Exception as e:
            self.logger.error(f"Error monitoring {self.channel.name}: {e}")
            get_notifier().notify_error(
                channel_name=self.channel.name,
                error_message=str(e),
            )

        time.sleep(self.global_settings.check_interval_seconds)
```

#### 수정 4: `MultiChannelMonitor.start()` (L159-195)

시작/종료 알림 추가:

```python
def start(self) -> None:
    # ... 기존 채널 로드 로직 ...

    self.is_running = True

    for channel in channels:
        # ... 기존 스레드 시작 로직 ...

    self.logger.info("All channel monitors started")
    get_notifier().notify_monitor_started(channel_count=len(channels))  # 추가

    try:
        while self.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        self.logger.info("Received shutdown signal")
        get_notifier().notify_monitor_stopped(reason="shutdown signal")  # 추가
        self.stop()
```

---

### 3-3. 기존 파일 수정: `src/yt_monitor/cookie_helper.py`

쿠키 만료 감지 시 디스코드 알림. `validate_cookies()` 함수에 추가.

**수정 위치:** `validate_cookies()` 함수의 `_cookie_valid = False` 설정 부분 (L175, L190 부근)

```python
# validate_cookies() 내부, _cookie_valid = False 직후에:
from .discord_notifier import get_notifier
# ...
if not _cookie_valid and (force or not cached):
    get_notifier().notify_cookie_expired(message=message)
```

**주의:** 순환 import 방지를 위해 함수 내부에서 import하거나, 모듈 최상단에서 lazy import 패턴 사용.

**권장 방식 — 함수 내 지역 import:**
```python
def validate_cookies(force: bool = False) -> Dict[str, Any]:
    # ... 기존 코드 ...

    # 쿠키 무효 판정 후, 캐시가 아닌 새 검사일 때만 알림
    if not result["cached"] and not result["valid"]:
        from .discord_notifier import get_notifier
        get_notifier().notify_cookie_expired(message=result["message"])

    return result
```

---

### 3-4. 기존 파일 수정: `src/yt_monitor/__init__.py`

```python
# 추가
from .discord_notifier import DiscordNotifier, get_notifier

__all__ = [
    # ... 기존 ...
    "DiscordNotifier",
    "get_notifier",
]
```

---

### 3-5. Docker Healthcheck 추가

#### `src/yt_monitor/web_api.py` — 헬스 엔드포인트 추가

```python
@self.app.get("/health")
async def health_check():
    """Docker healthcheck용 엔드포인트."""
    return {"status": "ok"}
```

기존 `__init__` 메서드 내 라우터 등록 부분에 추가한다. 기존 라우터 패턴을 따른다.

#### `Dockerfile` — HEALTHCHECK 추가

```dockerfile
# 기존 EXPOSE 8088 아래에 추가
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${YT_WEB_PORT:-8011}/health || exit 1
```

> Alpine 이미지이므로 `curl` 대신 `wget` 사용 (별도 설치 불필요).

#### `docker-compose.yml` — healthcheck 추가

```yaml
  yt-web:
    # ... 기존 설정 ...
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:${YT_WEB_PORT:-8011}/health"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3

  yt-monitor:
    # ... 기존 설정 ...
    # yt-monitor는 HTTP 서버가 없으므로 프로세스 존재 여부로 체크
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f 'monitoring.py' || exit 1"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3
```

---

### 3-6. `docker-compose.yml` — 환경변수 추가

```yaml
  yt-monitor:
    environment:
      - YT_POT_PROVIDER_URL=http://pot-provider:4416
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}  # 추가

  yt-web:
    environment:
      - YT_WEB_PORT=${YT_WEB_PORT}
      - YT_POT_PROVIDER_URL=http://pot-provider:4416
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}  # 추가 (쿠키 만료 알림용)
```

#### `.env.example` 생성

```env
# Discord Webhook URL (서버 설정 → 연동 → 웹후크에서 생성)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN

# 웹 서버 포트
YT_WEB_PORT=8011
```

---

## 4. 파일 변경 요약

| 파일 | 작업 | 설명 |
|------|------|------|
| `src/yt_monitor/discord_notifier.py` | **생성** | Discord Webhook 알림 모듈 |
| `src/yt_monitor/__init__.py` | 수정 | DiscordNotifier export 추가 |
| `src/yt_monitor/multi_channel_monitor.py` | 수정 | 5곳에 notifier 호출 삽입 |
| `src/yt_monitor/cookie_helper.py` | 수정 | validate_cookies()에 만료 알림 추가 |
| `src/yt_monitor/web_api.py` | 수정 | `/health` 엔드포인트 추가 |
| `Dockerfile` | 수정 | HEALTHCHECK 지시문 추가 |
| `docker-compose.yml` | 수정 | healthcheck + DISCORD_WEBHOOK_URL 환경변수 |
| `.env.example` | **생성** | 환경변수 템플릿 |

---

## 5. 테스트 계획

### 유닛 테스트: `test/test_discord_notifier.py`

```python
"""Discord notifier 유닛 테스트."""
import json
from unittest.mock import patch, MagicMock
from src.yt_monitor.discord_notifier import DiscordNotifier, NotificationLevel


class TestDiscordNotifier:
    """DiscordNotifier 테스트."""

    def test_disabled_when_no_webhook_url(self):
        """webhook URL 없으면 비활성화."""
        notifier = DiscordNotifier(webhook_url="")
        assert not notifier.is_enabled
        assert not notifier.send("test", "test")

    def test_enabled_when_webhook_url_set(self):
        """webhook URL 있으면 활성화."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        assert notifier.is_enabled

    @patch("urllib.request.urlopen")
    def test_send_success(self, mock_urlopen):
        """정상 전송."""
        mock_response = MagicMock()
        mock_response.headers = {"X-RateLimit-Remaining": "5"}
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        result = notifier.send("title", "desc", NotificationLevel.INFO)
        assert result is True

        # 전송된 payload 검증
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data)
        assert payload["embeds"][0]["title"] == "title"
        assert payload["embeds"][0]["color"] == NotificationLevel.INFO.value

    def test_convenience_methods_delegate_to_send(self):
        """편의 메서드가 send()를 호출하는지."""
        notifier = DiscordNotifier(webhook_url="")
        # 비활성화 상태이므로 모두 False
        assert not notifier.notify_live_detected("ch", "url", "title")
        assert not notifier.notify_download_complete("ch", "title")
        assert not notifier.notify_download_failed("ch", "err")
        assert not notifier.notify_cookie_expired("msg")
```

### 통합 테스트 (수동)

```bash
# 1. .env에 실제 webhook URL 설정
echo "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/..." > .env

# 2. 빌드 및 실행
docker-compose up --build -d

# 3. 확인 사항:
#    - 디스코드에 "모니터 시작" 메시지 수신 확인
#    - docker inspect --format='{{.State.Health.Status}}' yt-web → "healthy"
#    - docker inspect --format='{{.State.Health.Status}}' yt-monitor → "healthy"

# 4. 헬스체크 확인
curl http://localhost:8088/health
# → {"status": "ok"}

# 5. 종료 시 알림 확인
docker-compose down
# → 디스코드에 "모니터 종료" 메시지 수신 확인
```

---

## 6. 선행 작업 (사용자)

1. **디스코드 Webhook 생성:**
   - 디스코드 서버 → 서버 설정 → 연동 → 웹후크 → 새 웹후크
   - 알림 받을 채널 선택 → URL 복사
2. **`.env` 파일 생성:**
   ```bash
   echo "DISCORD_WEBHOOK_URL=복사한_URL" > .env
   ```

---

## 7. 구현 순서 (권장)

```
1. discord_notifier.py 생성 + 유닛 테스트 작성/통과
2. __init__.py에 export 추가
3. multi_channel_monitor.py에 알림 호출 삽입
4. cookie_helper.py에 쿠키 만료 알림 추가
5. web_api.py에 /health 엔드포인트 추가
6. Dockerfile에 HEALTHCHECK 추가
7. docker-compose.yml에 healthcheck + 환경변수 추가
8. .env.example 생성
9. 통합 테스트 (docker-compose up --build)
```

---

## 8. 향후 확장 가능성 (이번 스코프 아님)

- 웹 UI 대시보드 (실시간 상태, 로그 뷰어)
- 텔레그램/슬랙 등 멀티 채널 알림
- 디스크 용량 알림
- 다운로드 진행률 알림
