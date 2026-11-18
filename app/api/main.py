from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.exceptions import PluggyError
from app.core.metrics import refresh_financial_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    refresh_financial_metrics()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Open Wealth API", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(PluggyError)
    async def pluggy_error_handler(request: Request, exc: PluggyError):
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Falha ao consultar o Pluggy",
                "error": str(exc),
            },
        )

    app.include_router(router)
    return app


app = create_app()
