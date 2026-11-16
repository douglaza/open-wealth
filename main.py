from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.database import init_db
from app.core.scheduler import start_scheduler, stop_scheduler
from app.repositories.snapshot_repository import SnapshotRepository


@asynccontextmanager
async def lifespan(app):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="OpenWealth", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/patrimonio")
def patrimonio():
    return SnapshotRepository().get_all()


@app.get("/health")
def health():
    return {"status": "ok"}
