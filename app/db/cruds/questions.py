from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Question

__all__ = [
    "add_question",
    "get_questions",
    "get_question_id"
]


def add_question(pid, index, text):
    with SessionLocal() as session:
        q = Question(poll_id=pid, index=index, text=text)
        session.add(q)
        session.commit()
        return q.id


def get_questions(pid):
    with SessionLocal() as session:
        rows = session.execute(
            select(Question.index, Question.id, Question.text)
            .where(Question.poll_id == pid)
            .order_by(Question.index)
        ).all()
        return [(r[0], r[1], r[2]) for r in rows]


def get_question_id(pid, index):
    with SessionLocal() as session:
        row = session.execute(
            select(Question.id).where(
                Question.poll_id == pid, Question.index == index)
        ).first()
        return row[0] if row else None
