from fastapi import APIRouter

from app.slides import SLIDES

router = APIRouter()


@router.get("/api/slides")
def get_slides() -> list[dict]:
    return SLIDES
