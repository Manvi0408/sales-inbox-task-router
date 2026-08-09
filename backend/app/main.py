"""FastAPI entrypoint. One base URL serves the Task API (/tasks, /users), the
required /ingest, and the app wrappers (/api/*)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chat import router as chat_router
from .config import settings
from .db import init_db
from .ingest import router as ingest_router
from .stats import router as stats_router
from .task_api import router as task_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sales Inbox Router", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Allow any Vercel deployment (production + preview URLs) without having to
    # re-set CORS_ORIGINS each time the domain changes.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The raw Task API (§5) + /ingest + app wrappers (§7) — all one base URL.
app.include_router(task_router)
app.include_router(ingest_router)
app.include_router(stats_router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {
        "service": "sales-inbox-router",
        "candidate_id": settings.CANDIDATE_ID,
        "endpoints": ["/tasks", "/users", "/ingest", "/api/tasks", "/api/stats", "/api/chat"],
    }


@app.get("/health")
def health():
    return {"ok": True}
