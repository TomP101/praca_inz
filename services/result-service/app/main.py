from fastapi import FastAPI

from app.api.routes_admin import router as admin_router
from app.api.routes_stats import router as stats_router
from app.api.routes_ui import router as ui_router

app = FastAPI(
    title="Result Service",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(stats_router)
app.include_router(ui_router)
app.include_router(admin_router)
