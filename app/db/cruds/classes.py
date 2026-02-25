from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.db.models import Class, UserClass, User, Poll, Task, Vote, Question, Invoice

__all__ = [
    "create_class",
    "get_all_classes",
    "get_class_id_by_name",
    "get_users_in_class",
    "add_users_to_class",
    "get_class_users_with_names",
    "remove_user_from_class",
    "delete_class"
]


def create_class(class_name):
    with SessionLocal() as session:
        try:
            cls = Class(name=class_name)
            session.add(cls)
            session.commit()
            return cls.id
        except IntegrityError:
            session.rollback()
            return None


def get_all_classes():
    with SessionLocal() as session:
        rows = session.execute(
            select(Class.id, Class.name).order_by(Class.name)).all()
        return [(r[0], r[1]) for r in rows]


def get_class_id_by_name(name):
    with SessionLocal() as session:
        row = session.execute(
            select(Class.id).where(Class.name == name)).first()
        return row[0] if row else None


def get_users_in_class(class_id):
    with SessionLocal() as session:
        rows = (
            session.query(User.chat_id)
            .join(UserClass, User.chat_id == UserClass.user_id)
            .filter(UserClass.class_id == class_id)
            .all()
        )
        return [r[0] for r in rows]


def add_users_to_class(class_id, user_ids):
    with SessionLocal() as session:
        data = [UserClass(user_id=uid, class_id=class_id) for uid in user_ids]
        for uc in data:
            session.merge(uc)
        session.commit()


def get_class_users_with_names(class_name):
    with SessionLocal() as session:
        cls = session.execute(select(Class).where(
            Class.name == class_name)).scalar_one_or_none()
        if not cls:
            return None
        rows = (
            session.query(User.chat_id, User.name)
            .join(UserClass, User.chat_id == UserClass.user_id)
            .filter(UserClass.class_id == cls.id)
            .order_by(User.name)
            .all()
        )
        return [(r[0], r[1] or "بدون نام") for r in rows]


def remove_user_from_class(class_name, user_id):
    with SessionLocal() as session:
        cls = session.execute(select(Class).where(
            Class.name == class_name)).scalar_one_or_none()
        if not cls:
            return False, "❌ کلاس یافت نشد"
        result = session.execute(
            delete(UserClass).where(UserClass.user_id ==
                                    user_id, UserClass.class_id == cls.id)
        )
        session.commit()
        if result.rowcount > 0:
            return True, f"✅ کاربر {user_id} از کلاس '{class_name}' حذف شد."
        return False, f"❌ کاربر {user_id} در کلاس '{class_name}' یافت نشد."


def delete_class(class_name):
    with SessionLocal() as session:
        try:
            cls = session.execute(select(Class).where(
                Class.name == class_name)).scalar_one_or_none()
            if not cls:
                return False, "❌ کلاس یافت نشد"

            poll_ids = [p.id for p in session.execute(
                select(Poll).where(Poll.class_name == class_name)).scalars().all()]

            if poll_ids:
                session.execute(delete(Task).where(Task.poll_id.in_(poll_ids)))
                session.execute(delete(Vote).where(Vote.poll_id.in_(poll_ids)))
                session.execute(delete(Question).where(
                    Question.poll_id.in_(poll_ids)))
                session.execute(delete(Poll).where(Poll.id.in_(poll_ids)))

            session.execute(delete(Invoice).where(
                Invoice.class_name == class_name))
            session.execute(delete(UserClass).where(
                UserClass.class_id == cls.id))
            session.delete(cls)

            session.commit()
            return True, f"✅ کلاس '{class_name}' و تمام نظرسنجی‌ها و صورتحساب‌های مربوطه حذف شدند."
        except Exception as e:
            session.rollback()
            return False, f"❌ خطا در حذف کلاس: {str(e)}"
