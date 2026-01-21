# app/schemas/task.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.task import TaskStatus, TaskType


class TaskBase(BaseModel):
    task_type: TaskType
    complexity: int
    expected_duration_sec: Optional[int] = None
    payload_size_kb: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    id: str
    status: TaskStatus
    created_at: datetime
    dispatched_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        orm_mode = True
