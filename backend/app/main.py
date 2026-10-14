from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import session, slides

app = FastAPI(title="voiceppt backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(slides.router)
app.include_router(session.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
