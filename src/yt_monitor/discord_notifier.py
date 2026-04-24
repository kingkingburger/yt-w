"""Discord webhook notification module."""

import json
import os
import threading
import time
import urllib.request
import urllib.error
from enum import Enum
from typing import Optional


class NotificationLevel(Enum):
    """Notification severity levels with Discord embed colors."""

    INFO = 0x3498DB
    SUCCESS = 0x2ECC71
    WARNING = 0xF39C12
    ERROR = 0xE74C3C


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

        with self._lock:
            now = time.time()
            if now < self._rate_limit_until:
                time.sleep(self._rate_limit_until - now)

        embed: dict = {
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
            headers={
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (https://github.com/yt-monitor, 1.0.0)",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) == 0:
                    reset_after = float(response.headers.get("X-RateLimit-Reset-After", "1"))
                    with self._lock:
                        self._rate_limit_until = time.time() + reset_after
            return True

        except urllib.error.HTTPError as error:
            if error.code == 429:
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

    def notify_bot_detection(self, channel_name: str, detail: str) -> bool:
        """봇 감지로 라이브 확인/녹화 실패 알림."""
        return self.send(
            title=f"🚨 봇 감지 차단: {channel_name}",
            description=(
                "YouTube 봇 감지로 라이브 확인 실패 — 녹화 놓칠 수 있음.\n"
                "쿠키 재추출 또는 pot-provider 상태 확인 필요.\n"
                f"```{detail[:1200]}```"
            ),
            level=NotificationLevel.ERROR,
        )


_notifier: Optional[DiscordNotifier] = None


def get_notifier() -> DiscordNotifier:
    """모듈 레벨 싱글턴 notifier를 반환한다."""
    global _notifier
    if _notifier is None:
        _notifier = DiscordNotifier()
    return _notifier
