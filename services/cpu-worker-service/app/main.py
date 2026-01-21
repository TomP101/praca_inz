import time

from app.core.config import get_settings
from app.core.db import SessionLocal, Base, engine
from app.services.cpu_worker import process_dispatched_cpu_tasks


def main():
    Base.metadata.create_all(bind=engine)
    settings = get_settings()

    process_concurrency = 8

    while True:
        db = SessionLocal()
        try:
            processed = process_dispatched_cpu_tasks(
                db,
                batch_size=50,
                process_concurrency=int(process_concurrency),
            )
        finally:
            db.close()

        if processed == 0:
            time.sleep(float(settings.poll_interval_sec))
        else:
            time.sleep(0.01)


if __name__ == "__main__":
    main()
