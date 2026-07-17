"""Monitor status route contracts."""

from fastapi.testclient import TestClient


class TestMonitorStatusRoute:
    """/api/monitor/status."""

    def test_status_when_no_channels(self, client: TestClient):
        response = client.get("/api/monitor/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["active_channels"] == 0
        assert data["total_channels"] == 0
        assert data["source"] == "yt-monitor"
        assert data["state"] == "missing"

    def test_status_counts_channels(self, client: TestClient):
        client.post(
            "/api/channels",
            json={"name": "A", "url": "https://www.youtube.com/@A"},
        )
        client.post(
            "/api/channels",
            json={
                "name": "B",
                "url": "https://www.youtube.com/@B",
                "enabled": False,
            },
        )

        data = client.get("/api/monitor/status").json()
        assert data["total_channels"] == 2
        assert data["active_channels"] == 1

    def test_status_reads_external_monitor_heartbeat(
        self, client: TestClient, channels_file: str
    ):
        from src.yt_monitor.channels.repository import ChannelManager
        from src.yt_monitor.monitoring.status import write_monitor_status

        manager = ChannelManager(channels_file)
        settings = manager.get_global_settings()
        write_monitor_status(
            settings.log_file,
            state="running",
            active_channels=1,
            total_channels=1,
            message="test heartbeat",
        )

        data = client.get("/api/monitor/status").json()

        assert data["is_running"] is True
        assert data["state"] == "running"
        assert data["message"] == "test heartbeat"

    def test_start_stop_are_not_available_from_web(self, client: TestClient):
        start = client.post("/api/monitor/start")
        stop = client.post("/api/monitor/stop")

        assert start.status_code == 405
        assert stop.status_code == 405
