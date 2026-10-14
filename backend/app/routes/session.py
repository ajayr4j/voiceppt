from fastapi import APIRouter, HTTPException

from app.realtime import RealtimeTokenError, mint_client_secret
from app.slides import build_instructions, build_tools

router = APIRouter()


@router.post("/api/session")
async def create_session() -> dict:
    try:
        client_secret = await mint_client_secret()
    except RealtimeTokenError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "client_secret": client_secret,
        "instructions": build_instructions(),
        "tools": build_tools(),
    }
