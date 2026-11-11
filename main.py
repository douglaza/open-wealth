from fastapi import FastAPI
from app.repositories.snapshot_repository import get_all
from app.core.database import init_db

from contextlib import asynccontextmanager
from app.core.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(lifespan=lifespan)


# app = FastAPI(title="OpenWealth", version="0.1.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/patrimonio")
def patrimonio():
    return get_all()


@app.get("/health")
def health():
    return {"status": "ok"}
