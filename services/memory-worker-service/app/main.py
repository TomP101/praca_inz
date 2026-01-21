import time

from app.core.db import SessionLocal
from app.services.memory_worker import process_dispatched_memory_tasks


def main():
    thread_concurrency = 2
    batch_size = 5
    poll_interval_sec = 1.0

    while True:
        db = SessionLocal()
        try:
            processed = process_dispatched_memory_tasks(
                db,
                batch_size=batch_size,
                thread_concurrency=thread_concurrency,
            )
        finally:
            db.close()

        if processed == 0:
            time.sleep(poll_interval_sec)
        else:
            time.sleep(0.01)


if __name__ == "__main__":
    main()
