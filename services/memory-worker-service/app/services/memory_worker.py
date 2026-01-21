from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus, TaskType


def fetch_dispatched_memory_tasks(db: Session, limit: int) -> List[Task]:
    return (
        db.query(Task)
        .filter(
            Task.status == TaskStatus.DISPATCHED,
            Task.task_type == TaskType.MEMORY_INTENSIVE,
        )
        .order_by(Task.created_at)
        .limit(limit)
        .all()
    )


def simulate_memory_load(complexity: int) -> None:
    size_mb = max(1, int(complexity))
    size_bytes = size_mb * 1024 * 1024
    block = bytearray(size_bytes)
    step = 4096
    for i in range(0, len(block), step):
        block[i] = (block[i] + 1) % 256
    del block


def _run_mem_task(task_id: str, complexity: int) -> Tuple[str, bool, Optional[str], str]:
    try:
        simulate_memory_load(complexity)
        return task_id, True, None, datetime.utcnow().isoformat()
    except Exception as exc:
        return task_id, False, str(exc), datetime.utcnow().isoformat()


def process_dispatched_memory_tasks(db: Session, batch_size: int, thread_concurrency: int) -> int:
    tasks = fetch_dispatched_memory_tasks(db, batch_size)
    if not tasks:
        return 0

    now = datetime.utcnow()
    for task in tasks:
        task.status = TaskStatus.RUNNING
        task.started_at = now
    db.commit()

    ids = [str(t.id) for t in tasks]
    complexity_map = {str(t.id): int(t.complexity) for t in tasks}

    tc = max(1, int(thread_concurrency))
    results: List[Tuple[str, bool, Optional[str], str]] = []

    with ThreadPoolExecutor(max_workers=tc) as ex:
        futs = [ex.submit(_run_mem_task, tid, complexity_map[tid]) for tid in ids]
        for fut in as_completed(futs):
            results.append(fut.result())

    for task_id, ok, err, finished_iso in results:
        task = db.query(Task).filter(Task.id == task_id).one_or_none()
        if not task:
            continue
        finished = datetime.fromisoformat(finished_iso)
        task.finished_at = finished
        if ok:
            task.status = TaskStatus.COMPLETED
            task.error_message = None
        else:
            task.status = TaskStatus.FAILED
            task.error_message = err
        db.commit()

    return len(tasks)
