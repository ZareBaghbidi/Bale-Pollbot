import datetime
from sqlalchemy import select, delete
from app.db.session import SessionLocal
from app.db.models import Task

__all__ = [
    "add_task",
    "next_task",
    "del_task"
]


def add_task(ts, pid):
    with SessionLocal() as session:
        run_at = datetime.datetime.fromtimestamp(ts)
        t = Task(run_at=run_at, poll_id=pid)
        session.add(t)
        session.commit()
        return t.id


def next_task():
    with SessionLocal() as session:
        row = session.execute(
            select(Task.id, Task.poll_id, Task.run_at)
            .order_by(Task.run_at)
            .limit(1)
        ).first()
        if row:
            return {"id": row[0], "poll_id": row[1], "t": int(row[2].timestamp())}
        return None


def del_task(tid):
    with SessionLocal() as session:
        session.execute(delete(Task).where(Task.id == tid))
        session.commit()
