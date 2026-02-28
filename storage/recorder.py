from datetime import datetime

from storage.db import Run, Session, init_db


def start_run(topic: str | None = None) -> int:
    init_db()
    with Session() as session:
        run = Run(topic=topic)
        session.add(run)
        session.commit()
        return run.id


def finish_run(run_id: int, status: str = "success", error: str | None = None) -> None:
    with Session() as session:
        run = session.get(Run, run_id)
        if run:
            run.finished_at = datetime.utcnow()
            run.status = status
            run.error = error
            session.commit()
