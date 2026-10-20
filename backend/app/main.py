from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routes import auth, flashcards, profile, quizzes, reactions, studio
from app.services.learning_content import seed_learning_content


settings = get_settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)
with SessionLocal() as seed_db:
    seed_learning_content(seed_db)

app = FastAPI(title="ChemVision AI API", version="0.1.0")

# Allow all origins in local development so the frontend can be opened
# directly as a file:// URL or from any local HTTP server port.
# In production set FRONTEND_ORIGINS explicitly via the .env file.
_origins = settings.frontend_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=(
        r"^(https?://localhost(:\d+)?|https?://127\.0\.0\.1(:\d+)?)$"
        if settings.environment != "production" else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(reactions.router)
app.include_router(studio.router)
app.include_router(flashcards.router)
app.include_router(quizzes.router)


@app.get("/health")
def health_check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "available"}
