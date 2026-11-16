from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import router
from app.core.database import init_db
from app.core.metrics import (
    ACCOUNTS_TOTAL,
    INVESTMENTS_TOTAL,
    LAST_SYNC_TIMESTAMP,
    PLUGGY_ERRORS_TOTAL,
    TOTAL_PATRIMONIO_BRL,
)
from app.core.scheduler import start_scheduler, stop_scheduler
from app.repositories.snapshot_repository import SnapshotRepository


@asynccontextmanager
async def lifespan(app):
    init_db()
    start_scheduler()

    # Inicializa o contador para o Grafana exibir 0 em vez de No data
    PLUGGY_ERRORS_TOTAL.labels(operation="sync")

    # Alimenta os gauges com o snapshot atual do banco
    try:
        latest = SnapshotRepository().get_latest()
        if latest and latest.positions:
            accounts = [p for p in latest.positions if p.account_type != "investment"]
            investments = [p for p in latest.positions if p.account_type == "investment"]
            ACCOUNTS_TOTAL.set(len(accounts))
            INVESTMENTS_TOTAL.set(len(investments))
            TOTAL_PATRIMONIO_BRL.set(sum(p.amount for p in latest.positions))
            if latest.positions[0].updated_at:
                LAST_SYNC_TIMESTAMP.set(latest.positions[0].updated_at.timestamp())
    except Exception:
        pass

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


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
