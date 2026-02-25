from sqlalchemy import select, func, cast, Float
from app.db.session import SessionLocal
from app.db.models import Vote, Question
from app.db.cruds.polls import get_poll_type

__all__ = [
    "vote",
    "stats",
    "get_responses"
]


def vote(pid, q_id, value, uid, username, name):
    with SessionLocal() as session:
        v = Vote(poll_id=pid, question_id=q_id, value=value,
                 user_id=uid, username=username, name=name)
        session.add(v)
        session.commit()


def stats(pid):
    poll_type = get_poll_type(pid)
    with SessionLocal() as session:
        if poll_type == "score":
            rows = session.execute(
                select(
                    Vote.question_id,
                    func.count(),
                    func.sum(cast(Vote.value, Float))
                )
                .where(Vote.poll_id == pid)
                .group_by(Vote.question_id)
            ).all()
            return {r[0]: (r[1], r[2]) for r in rows}
        else:
            rows = session.execute(
                select(
                    Vote.question_id,
                    func.count(),
                    func.null()
                )
                .where(Vote.poll_id == pid)
                .group_by(Vote.question_id)
            ).all()
            return {r[0]: (r[1], None) for r in rows}


def get_responses(pid):
    with SessionLocal() as session:
        rows = session.execute(
            select(Question.index, Question.text,
                   Vote.value, Vote.name, Vote.username)
            .join(Question, Vote.question_id == Question.id)
            .where(Vote.poll_id == pid)
            .order_by(Question.index, Vote.id)
        ).all()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]
