from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.stats_service import get_summary_stats

router = APIRouter(prefix="/stats", tags=["stats"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/summary")
def stats_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return get_summary_stats(db)
