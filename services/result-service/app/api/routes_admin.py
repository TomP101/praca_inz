from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal

router = APIRouter(prefix="/admin", tags=["admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/truncate")
def truncate_tasks(db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.enable_db_admin:
        raise HTTPException(status_code=403, detail="DB admin endpoints disabled")

    db.execute(text("TRUNCATE TABLE tasks RESTART IDENTITY;"))
    db.commit()
    return {"ok": True}
