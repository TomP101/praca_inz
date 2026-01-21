# app/api/routes_tasks.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.task import TaskCreate, TaskRead
from app.services.task_service import create_task, get_task, list_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(task_in: TaskCreate, db: Session = Depends(get_db)):
    task = create_task(db, task_in)
    return task


@router.get("/{task_id}", response_model=TaskRead)
def get_task_endpoint(task_id: str, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/", response_model=List[TaskRead])
def list_tasks_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    tasks = list_tasks(db, skip=skip, limit=limit)
    return tasks
