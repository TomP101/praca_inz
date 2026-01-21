from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus


def fetch_pending_tasks(db: Session, limit: int) -> List[Task]:
    return (
        db.query(Task)
        .filter(Task.status == TaskStatus.PENDING)
        .order_by(Task.created_at)
        .limit(limit)
        .all()
    )


def dispatch_pending_tasks(db: Session, batch_size: int) -> int:
    tasks = fetch_pending_tasks(db, batch_size)
    if not tasks:
        return 0

    now = datetime.utcnow()
    for task in tasks:
        task.status = TaskStatus.DISPATCHED
        task.dispatched_at = now

    db.commit()
    return len(tasks)
