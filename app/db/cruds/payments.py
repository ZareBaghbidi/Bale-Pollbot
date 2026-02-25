import datetime
from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.db.models import Payment, User

__all__ = [
    "save_payment",
    "get_payments_stats",
    "get_recent_payments",
    "get_user_payments",
    "get_daily_payments_stats"
]


def save_payment(user_id, amount, payload, name=None, phone=None, email=None, telegram_charge_id=None, provider_charge_id=None, status="completed"):
    with SessionLocal() as session:
        p = Payment(
            user_id=user_id,
            amount=amount,
            payload=payload,
            name=name,
            phone=phone,
            email=email,
            telegram_charge_id=telegram_charge_id,
            provider_charge_id=provider_charge_id,
            timestamp=int(datetime.datetime.now().timestamp()),
            status=status
        )
        session.add(p)
        session.commit()
        return p.id


def get_payments_stats(days=None, min_amount=None):
    with SessionLocal() as session:
        query = select(
            func.count().label("count"),
            func.sum(Payment.amount).label("total"),
            func.count(func.distinct(Payment.user_id)).label("unique_users")
        )
        if days:
            timestamp_limit = int(
                datetime.datetime.now().timestamp()) - (days * 24 * 3600)
            query = query.where(Payment.timestamp >= timestamp_limit)
        if min_amount:
            query = query.where(Payment.amount >= min_amount)
        row = session.execute(query).first()
        if row:
            return {"count": row.count or 0, "total": row.total or 0, "unique_users": row.unique_users or 0}
        return {"count": 0, "total": 0, "unique_users": 0}


def get_recent_payments(limit=10):
    with SessionLocal() as session:
        rows = session.execute(
            select(Payment, User.name.label("user_name"))
            .outerjoin(User, Payment.user_id == User.chat_id)
            .order_by(Payment.timestamp.desc())
            .limit(limit)
        ).all()
        return [dict(r[0].__dict__, user_name=r[1]) for r in rows]


def get_user_payments(user_id, limit=20):
    with SessionLocal() as session:
        rows = session.execute(
            select(Payment, User.name.label("user_name"))
            .outerjoin(User, Payment.user_id == User.chat_id)
            .where(Payment.user_id == user_id)
            .order_by(Payment.timestamp.desc())
            .limit(limit)
        ).all()
        return [dict(r[0].__dict__, user_name=r[1]) for r in rows]


def get_daily_payments_stats(days=30):
    with SessionLocal() as session:
        timestamp_limit = int(
            datetime.datetime.now().timestamp()) - (days * 24 * 3600)
        rows = session.execute(
            select(
                func.date(func.datetime(Payment.timestamp,
                          "unixepoch")).label("date"),
                func.count().label("count"),
                func.sum(Payment.amount).label("total")
            )
            .where(Payment.timestamp >= timestamp_limit)
            .group_by(func.date(func.datetime(Payment.timestamp, "unixepoch")))
            .order_by(func.date(func.datetime(Payment.timestamp, "unixepoch")).desc())
            .limit(30)
        ).all()
        return [{"date": r.date, "count": r.count, "total": r.total} for r in rows]
