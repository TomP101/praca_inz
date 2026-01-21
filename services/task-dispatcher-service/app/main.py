import time

from app.core.config import get_settings
from app.core.db import SessionLocal, Base, engine
from app.services.dispatcher import dispatch_pending_tasks


def main():
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    while True:
        db = SessionLocal()
        try:
            dispatch_pending_tasks(db, batch_size=settings.batch_size)
        finally:
            db.close()
        time.sleep(settings.poll_interval_sec)


if __name__ == "__main__":
    main()
