from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_response(status_code: int, json_body: dict | None = None, text: str = ""):
    response = httpx.Response(
        status_code=status_code,
        json=json_body,
        text=text if json_body is None else None,
        request=httpx.Request("POST", "https://api.openai.com/v1/realtime/client_secrets"),
    )
    return response


def test_create_session_returns_client_secret_tools_and_instructions():
    fake_openai_response = _mock_response(200, json_body={"value": "ek_test_123"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_openai_response)):
        response = client.post("/api/session")

    assert response.status_code == 200
    body = response.json()
    assert body["client_secret"] == "ek_test_123"
    assert "show_slide" in body["tools"][0]["name"]
    assert "Slide 1" in body["instructions"]
    assert body["tools"][0]["parameters"]["properties"]["slide_number"]["enum"] == [1, 2, 3, 4, 5, 6]


def test_create_session_surfaces_openai_errors_as_502():
    fake_openai_response = _mock_response(401, text="invalid api key")
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_openai_response)):
        response = client.post("/api/session")

    assert response.status_code == 502
    assert "401" in response.json()["detail"]


def test_create_session_handles_network_failure():
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("boom"))):
        response = client.post("/api/session")

    assert response.status_code == 502
