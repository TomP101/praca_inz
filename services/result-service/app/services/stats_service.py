from collections import Counter
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus, TaskType


def get_summary_stats(db: Session) -> Dict:
    tasks = db.query(Task).all()
    total_tasks = len(tasks)

    status_counts = Counter(t.status.value for t in tasks)

    wait_times = []
    run_times_by_type = {t.value: [] for t in TaskType}
    finished_times = []

    for t in tasks:
        if t.created_at and t.started_at:
            wait_times.append((t.started_at - t.created_at).total_seconds())

        if t.started_at and t.finished_at:
            run_times_by_type[t.task_type.value].append(
                (t.finished_at - t.started_at).total_seconds()
            )
            finished_times.append(t.finished_at)

    avg_wait_time_sec: Optional[float] = None
    if wait_times:
        avg_wait_time_sec = sum(wait_times) / len(wait_times)

    avg_run_time_sec_by_type: Dict[str, Optional[float]] = {}
    for type_name, values in run_times_by_type.items():
        if values:
            avg_run_time_sec_by_type[type_name] = sum(values) / len(values)
        else:
            avg_run_time_sec_by_type[type_name] = None

    throughput_tasks_per_min: Optional[float] = None
    completed = [t for t in tasks if t.status == TaskStatus.COMPLETED and t.finished_at]
    if completed:
        finished_sorted = sorted(t.finished_at for t in completed)
        start = finished_sorted[0]
        end = finished_sorted[-1]
        delta_sec = max((end - start).total_seconds(), 0.0)
        if delta_sec > 0:
            throughput_tasks_per_min = len(completed) / (delta_sec / 60.0)

    return {
        "total_tasks": total_tasks,
        "status_counts": dict(status_counts),
        "avg_wait_time_sec": avg_wait_time_sec,
        "avg_run_time_sec_by_type": avg_run_time_sec_by_type,
        "throughput_tasks_per_min": throughput_tasks_per_min,
    }
