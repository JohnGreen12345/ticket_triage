"""Integration tests — hit the real endpoint via FastAPI TestClient."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRecommendationsEndpoint:
    def test_valid_ticket_returns_200(self):
        resp = client.post(
            "/recommendations",
            json={
                "title": "Cannot log in",
                "description": "I reset my password but still get an error",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert len(data["recommendations"]) == 3

    def test_response_shape(self):
        resp = client.post(
            "/recommendations",
            json={"title": "Slow page load", "description": "Dashboard takes 10 seconds"},
        )
        data = resp.json()
        rec = data["recommendations"][0]
        assert "action" in rec
        assert "confidence" in rec
        assert "why" in rec
        assert isinstance(rec["confidence"], float)

    def test_custom_top_n(self):
        resp = client.post(
            "/recommendations",
            json={"title": "Billing issue", "description": "Double charge", "top_n": 2},
        )
        data = resp.json()
        assert len(data["recommendations"]) == 2

    def test_missing_title_returns_422(self):
        resp = client.post(
            "/recommendations",
            json={"description": "I have a problem"},
        )
        assert resp.status_code == 422

    def test_missing_description_returns_422(self):
        resp = client.post(
            "/recommendations",
            json={"title": "Help"},
        )
        assert resp.status_code == 422

    def test_empty_title_returns_422(self):
        resp = client.post(
            "/recommendations",
            json={"title": "", "description": "Something"},
        )
        assert resp.status_code == 422

    def test_empty_body_returns_422(self):
        resp = client.post("/recommendations", json={})
        assert resp.status_code == 422

    def test_invalid_json_returns_422(self):
        resp = client.post(
            "/recommendations",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_top_n_out_of_range_returns_422(self):
        resp = client.post(
            "/recommendations",
            json={"title": "Test", "description": "Test", "top_n": 0},
        )
        assert resp.status_code == 422

    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_metrics_endpoint(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "request_count" in data
        assert "error_count" in data
        assert "total_latency_ms" in data
