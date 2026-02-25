from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User, Class, UserClass

__all__ = [
    "add_user",
    "get_users",
    "get_all_users_with_names",
    "get_user_name",
    "get_user_classes"
]


def add_user(uid, name):
    with SessionLocal() as session:
        exists = session.get(User, uid)
        if not exists:
            session.add(User(chat_id=uid, name=name))
            session.commit()


def get_users():
    with SessionLocal() as session:
        rows = session.execute(select(User.chat_id)).all()
        return [r[0] for r in rows]


def get_all_users_with_names():
    with SessionLocal() as session:
        rows = session.execute(
            select(User).order_by(User.name)).scalars().all()
        return [(i + 1, u.chat_id, u.name or "بدون نام") for i, u in enumerate(rows)]


def get_user_name(uid):
    with SessionLocal() as session:
        user = session.get(User, uid)
        return user.name if user else None


def get_user_classes(uid):
    with SessionLocal() as session:
        rows = (
            session.query(Class.name)
            .join(UserClass, Class.id == UserClass.class_id)
            .filter(UserClass.user_id == uid)
            .all()
        )
        return [r[0] for r in rows]
