from fastapi import FastAPI

from zen_backend.routes.checkin import router as checkin_router
from zen_backend.routes.dashboard import router as dashboard_router
from zen_backend.routes.feedback import router as feedback_router
from zen_backend.routes.health import router as health_router
from zen_backend.routes.internal import router as internal_router
from zen_backend.routes.telegram import router as telegram_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zen Daily Wisdom Backend",
        version="0.1.0",
        description="FastAPI backend for personalized daily wisdom delivery",
    )
    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(feedback_router)
    app.include_router(dashboard_router)
    app.include_router(telegram_router)
    app.include_router(checkin_router)
    return app


app = create_app()

