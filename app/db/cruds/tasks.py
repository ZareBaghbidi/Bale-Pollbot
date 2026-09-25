import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete
from app.db.session import SessionLocal
from app.db.models import Task, Poll, Question

TEHRAN = ZoneInfo("Asia/Tehran")

__all__ = [
    "add_task",
    "next_task",
    "del_task",
    "get_scheduled_tasks",
    "cancel_scheduled_task",
]


def add_task(ts, pid):
    with SessionLocal() as session:
        run_at = datetime.datetime.fromtimestamp(ts, TEHRAN).replace(tzinfo=None)
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
            run_at = row[2].replace(tzinfo=TEHRAN)
            return {"id": row[0], "poll_id": row[1], "t": int(run_at.timestamp())}
        return None


def del_task(tid):
    with SessionLocal() as session:
        session.execute(delete(Task).where(Task.id == tid))
        session.commit()


def get_scheduled_tasks():
    """Return queued sends with poll details, ordered by scheduled time."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Task.id, Task.poll_id, Task.run_at, Poll.type,
                   Poll.class_name, Question.text)
            .join(Poll, Poll.id == Task.poll_id)
            .outerjoin(Question, Question.poll_id == Poll.id)
            .order_by(Task.run_at, Task.id, Question.index)
        ).all()
        return [(r[0], r[1], r[2].replace(tzinfo=TEHRAN), r[3], r[4], r[5])
                for r in rows]


def cancel_scheduled_task(tid):
    """Remove a queued task and its not-yet-published poll, if found."""
    with SessionLocal() as session:
        task = session.get(Task, tid)
        if task is None:
            return None
        poll_id = task.poll_id
        poll = session.get(Poll, poll_id)
        session.delete(task)
        if poll is not None and not poll.active:
            session.delete(poll)  # ORM cascades its questions and votes.
        session.commit()
        return poll_id
