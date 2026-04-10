from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import auth, students, alerts, surveys, reports, mentors, risk

settings = get_settings()

app = FastAPI(
    title="AcademIQ API",
    description="Early warning system for student risk detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(alerts.router)
app.include_router(surveys.router)
app.include_router(reports.router)
app.include_router(mentors.router)
app.include_router(risk.router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "AcademIQ API", "version": "1.0.0"}


@app.get("/", tags=["system"])
async def root():
    return {
        "message": "AcademIQ API is running",
        "docs": "/docs",
        "health": "/health",
    }
