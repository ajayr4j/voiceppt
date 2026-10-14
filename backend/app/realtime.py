import httpx

from app.config import settings

OPENAI_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"


class RealtimeTokenError(RuntimeError):
    """Raised when OpenAI refuses or fails to mint an ephemeral session token."""


async def mint_client_secret() -> str:
    """Mint a short-lived client secret the browser uses to open a Realtime WebRTC session.

    The real API key never leaves the backend — only this ephemeral, scoped
    token is sent to the browser (see docs/guides/voice-webrtc).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                OPENAI_CLIENT_SECRETS_URL,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "session": {
                        "type": "realtime",
                        "model": settings.realtime_model,
                        "audio": {"output": {"voice": settings.realtime_voice}},
                    }
                },
            )
        except httpx.HTTPError as exc:
            raise RealtimeTokenError(f"Could not reach OpenAI: {exc}") from exc

    if response.status_code >= 400:
        raise RealtimeTokenError(
            f"OpenAI rejected the session request ({response.status_code}): {response.text}"
        )

    data = response.json()
    try:
        return data["value"]
    except KeyError as exc:
        raise RealtimeTokenError(f"Unexpected response shape from OpenAI: {data}") from exc
