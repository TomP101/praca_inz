from fastapi import FastAPI

from app.core.db import Base, engine
from app.api.routes_tasks import router as tasks_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Task API Service",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(tasks_router)
