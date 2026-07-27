from fastapi import FastAPI

from litmonitor.api.routes_digests import router as digests_router
from litmonitor.api.routes_llm import router as llm_router
from litmonitor.api.routes_papers import router as papers_router
from litmonitor.api.routes_profiles import router as profiles_router
from litmonitor.config import get_settings
from litmonitor.database import init_db
from litmonitor.services.scheduler import create_scheduler
from litmonitor.web.routes import router as web_router

app = FastAPI(title="LitMonitor", version="0.1.0")
app.include_router(papers_router, prefix="/api/v1")
app.include_router(profiles_router, prefix="/api/v1")
app.include_router(llm_router, prefix="/api/v1")
app.include_router(digests_router, prefix="/api/v1")
app.include_router(web_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    init_db()
    settings = get_settings()
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler


@app.on_event("shutdown")
def shutdown() -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler:
        scheduler.shutdown()
