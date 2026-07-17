"""Channel route contracts."""

from fastapi.testclient import TestClient


class TestChannelRoutes:
    """CRUD /api/channels."""

    def test_list_empty(self, client: TestClient):
        response = client.get("/api/channels")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_and_list(self, client: TestClient):
        payload = {
            "name": "TestCh",
            "url": "https://www.youtube.com/@TestCh",
        }
        created = client.post("/api/channels", json=payload).json()
        assert created["name"] == "TestCh"
        assert "id" in created

        listed = client.get("/api/channels").json()
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]

    def test_update_channel(self, client: TestClient):
        created = client.post(
            "/api/channels",
            json={"name": "Old", "url": "https://www.youtube.com/@Old"},
        ).json()

        updated = client.patch(
            f"/api/channels/{created['id']}", json={"name": "New"}
        ).json()

        assert updated["name"] == "New"

    def test_delete_channel(self, client: TestClient):
        created = client.post(
            "/api/channels",
            json={"name": "Temp", "url": "https://www.youtube.com/@Temp"},
        ).json()

        response = client.delete(f"/api/channels/{created['id']}")
        assert response.status_code == 200

        listed = client.get("/api/channels").json()
        assert listed == []

    def test_create_duplicate_url_returns_400(self, client: TestClient):
        payload = {"name": "A", "url": "https://www.youtube.com/@DupCh"}
        client.post("/api/channels", json=payload)
        response = client.post("/api/channels", json=payload)
        assert response.status_code == 400
