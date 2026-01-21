# app/services/task_service.py
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate


def create_task(db: Session, task_in: TaskCreate) -> Task:

    db_task = Task(
        task_type=task_in.task_type,
        complexity=task_in.complexity,
        expected_duration_sec=task_in.expected_duration_sec,
        payload_size_kb=task_in.payload_size_kb,
        status=TaskStatus.PENDING,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_task(db: Session, task_id: str) -> Optional[Task]:

    return db.query(Task).filter(Task.id == task_id).first()


def list_tasks(db: Session, skip: int = 0, limit: int = 100) -> List[Task]:

    return db.query(Task).offset(skip).limit(limit).all()
