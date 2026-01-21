from datetime import datetime
from typing import List, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus, TaskType


def fetch_dispatched_cpu_tasks(db: Session, limit: int) -> List[Task]:
    return (
        db.query(Task)
        .filter(
            Task.status == TaskStatus.DISPATCHED,
            Task.task_type == TaskType.CPU_INTENSIVE,
        )
        .order_by(Task.created_at)
        .limit(limit)
        .all()
    )


def simulate_cpu_load(complexity: int) -> None:
    iterations = max(1, complexity) * 100000
    x = 0.001
    for i in range(iterations):
        x = (x * i + 1.2345) % 123456.789


def _run_cpu_task(task_id: str, complexity: int) -> Tuple[str, bool, Optional[str], str]:
    try:
        simulate_cpu_load(complexity)
        return task_id, True, None, datetime.utcnow().isoformat()
    except Exception as exc:
        return task_id, False, str(exc), datetime.utcnow().isoformat()


def process_dispatched_cpu_tasks(db: Session, batch_size: int, process_concurrency: int) -> int:
    tasks = fetch_dispatched_cpu_tasks(db, batch_size)
    if not tasks:
        return 0

    now = datetime.utcnow()
    for task in tasks:
        task.status = TaskStatus.RUNNING
        task.started_at = now
    db.commit()

    ids = [str(t.id) for t in tasks]
    complexity_map = {str(t.id): int(t.complexity) for t in tasks}

    results: List[Tuple[str, bool, Optional[str], str]] = []
    pc = max(1, int(process_concurrency))

    with ProcessPoolExecutor(max_workers=pc) as ex:
        futs = [ex.submit(_run_cpu_task, tid, complexity_map[tid]) for tid in ids]
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
