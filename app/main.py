from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import users, events, ratings
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting CarSpot API...")
    init_db()
    print("✅ Database initialized")
    yield
    print("🛑 Shutting down CarSpot API...")

app = FastAPI(
    title="CarSpot API",
    version="1.0.0",
    description="API для автомобильных сходок в странах СНГ",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(ratings.router, prefix="/api/ratings", tags=["Ratings"])

@app.get("/")
async def root():
    return {
        "message": "CarSpot API is running",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}