import datetime
from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.db.models import Poll


__all__ = [
    "create_poll",
    "stop_poll",
    "deactivate_old_polls",
    "show_active_polls",
    "show_all_polls",
    "get_poll_type",
    "get_poll_class",
    "is_poll_active"
]


def create_poll(poll_type, class_=None):
    with SessionLocal() as session:
        now = datetime.datetime.now()
        poll = Poll(type=poll_type, class_name=class_,
                    active=0, created_at=now)
        session.add(poll)
        session.commit()
        return poll.id


def stop_poll(pid):
    with SessionLocal() as session:
        session.execute(update(Poll).where(Poll.id == pid).values(active=0))
        session.commit()


def deactivate_old_polls(days=7):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    with SessionLocal() as session:
        res = session.execute(
            update(Poll)
            .where(Poll.active == 1, Poll.created_at < cutoff)
            .values(active=0)
        )
        session.commit()
        return res.rowcount


def show_active_polls():
    with SessionLocal() as session:
        rows = session.execute(
            select(Poll.id, Poll.class_name, Poll.type).where(Poll.active == 1)).all()
        return [(r[0], r[1], r[2]) for r in rows]


def show_all_polls():
    with SessionLocal() as session:
        rows = session.execute(
            select(Poll.id, Poll.type, Poll.class_name, Poll.active,
                   Poll.created_at).order_by(Poll.id.desc())
        ).all()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def get_poll_type(pid):
    with SessionLocal() as session:
        row = session.execute(select(Poll.type).where(Poll.id == pid)).first()
        return row[0] if row else None


def get_poll_class(pid):
    with SessionLocal() as session:
        row = session.execute(
            select(Poll.class_name).where(Poll.id == pid)).first()
        return row[0] if row else None


def is_poll_active(pid):
    with SessionLocal() as session:
        row = session.execute(
            select(Poll.active).where(Poll.id == pid)).first()
        return row[0] == 1 if row else False


def do_activate_poll(poll_id):
    with SessionLocal() as session:
        session.execute(update(Poll).where(
            Poll.id == poll_id).values(active=1))
        session.commit()
