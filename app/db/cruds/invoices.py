from sqlalchemy import case, cast, Integer
import datetime
from sqlalchemy import select, func, update
from app.db.session import SessionLocal
from app.db.models import Invoice, User, Payment

__all__ = [
    "save_invoice",
    "update_invoice_status",
    "get_invoice_by_payload",
    "get_all_invoices",
    "get_invoice_stats",
    "get_class_invoice_summary",
    "get_unpaid_invoices",
    "get_grouped_invoices",
    "get_user_unpaid_invoices",
    "get_user_unpaid_invoice",
    "get_active_invoices",
    "get_active_invoice_count",
    "get_active_invoice",
    "deactivate_invoice",
    "get_due_invoice_reminders",
    "schedule_next_invoice_reminder",
]


def save_invoice(user_id, class_name, amount, title, description, payload,
                 provider_token, reminder_interval_days=None, group_id=None):
    now = int(datetime.datetime.now().timestamp())
    with SessionLocal() as session:
        inv = Invoice(
            user_id=user_id,
            class_name=class_name,
            amount=amount,
            title=title,
            description=description,
            payload=payload,
            provider_token=provider_token,
            group_id=group_id,
            sent_at=now,
            reminder_interval_days=reminder_interval_days,
            next_reminder_at=(now + reminder_interval_days * 24 * 3600
                              if reminder_interval_days else None),
            status="sent"
        )
        session.add(inv)
        session.commit()
        return inv.id


def update_invoice_status(payload, status, payment_id=None):
    with SessionLocal() as session:
        paid_at = int(datetime.datetime.now().timestamp()
                      ) if status == "paid" else None
        res = session.execute(
            update(Invoice)
            .where(Invoice.payload == payload, Invoice.status != "paid")
            .values(status=status, paid_at=paid_at, payment_id=payment_id)
        )
        session.commit()
        return res.rowcount > 0


def get_invoice_by_payload(payload):
    with SessionLocal() as session:
        row = session.execute(select(Invoice).where(
            Invoice.payload == payload)).scalar_one_or_none()
        return row.__dict__ if row else None


def get_all_invoices(days=None, status=None, class_name=None, limit=50):
    with SessionLocal() as session:
        query = (
            select(Invoice, User.name.label("user_name"),
                   Payment.telegram_charge_id)
            .outerjoin(User, Invoice.user_id == User.chat_id)
            .outerjoin(Payment, Invoice.payment_id == Payment.id)
        )
        if days:
            timestamp_limit = int(
                datetime.datetime.now().timestamp()) - (days * 24 * 3600)
            query = query.where(Invoice.sent_at >= timestamp_limit)
        if status:
            query = query.where(Invoice.status == status)
        if class_name:
            query = query.where(Invoice.class_name == class_name)
        query = query.order_by(Invoice.sent_at.desc()).limit(limit)
        rows = session.execute(query).all()
        return [dict(r[0].__dict__, user_name=r[1], telegram_charge_id=r[2]) for r in rows]


def _invoice_group_columns():
    return (
        Invoice.group_id,
        Invoice.class_name,
        Invoice.title,
        Invoice.amount,
        Invoice.description,
        Invoice.reminder_interval_days,
    )


def _active_invoice_groups_query():
    return (
        select(
            func.min(Invoice.id).label("id"),
            Invoice.group_id.label("group_id"),
            Invoice.class_name.label("class_name"),
            Invoice.title.label("title"),
            Invoice.amount.label("amount"),
            Invoice.description.label("description"),
            Invoice.reminder_interval_days.label("reminder_interval_days"),
            func.sum(case((Invoice.status == "sent", 1), else_=0)).label(
                "unpaid_count"),
            func.sum(case((Invoice.status == "paid", 1), else_=0)).label(
                "paid_count"),
            func.max(Invoice.sent_at).label("last_sent"),
        )
        .group_by(*_invoice_group_columns())
        .having(func.sum(case((Invoice.status == "sent", 1), else_=0)) > 0)
    )


def get_active_invoices(offset=0, limit=8):
    with SessionLocal() as session:
        rows = session.execute(
            _active_invoice_groups_query()
            .order_by(func.max(Invoice.sent_at).desc(), func.min(Invoice.id).desc())
            .offset(offset)
            .limit(limit)
        ).mappings().all()
        return [dict(row) for row in rows]


def get_active_invoice_count():
    with SessionLocal() as session:
        groups = _active_invoice_groups_query().subquery()
        return session.execute(select(func.count()).select_from(groups)).scalar_one()


def _invoice_group_filter(invoice):
    if invoice.group_id is not None:
        return (Invoice.group_id == invoice.group_id,)

    # Older rows predate explicit batch IDs; use their billing details as the
    # best available grouping key so existing unpaid invoices remain manageable.
    filters = [Invoice.group_id.is_(None)]
    for column_name in (
            "class_name", "title", "amount", "description",
            "reminder_interval_days"):
        column = getattr(Invoice, column_name)
        value = getattr(invoice, column_name)
        filters.append(column.is_(None) if value is None else column == value)
    return tuple(filters)


def get_active_invoice(invoice_id):
    with SessionLocal() as session:
        invoice = session.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        ).scalar_one_or_none()
        if invoice is None:
            return None

        filters = _invoice_group_filter(invoice)
        row = session.execute(
            select(
                func.min(Invoice.id).label("id"),
                Invoice.group_id.label("group_id"),
                Invoice.class_name.label("class_name"),
                Invoice.title.label("title"),
                Invoice.amount.label("amount"),
                Invoice.description.label("description"),
                Invoice.reminder_interval_days.label("reminder_interval_days"),
                func.sum(case((Invoice.status == "sent", 1), else_=0)).label(
                    "unpaid_count"),
                func.sum(case((Invoice.status == "paid", 1), else_=0)).label(
                    "paid_count"),
            ).where(*filters)
        ).mappings().one()
        group = dict(row)
        return group if group["unpaid_count"] else None


def deactivate_invoice(invoice_id):
    with SessionLocal() as session:
        invoice = session.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        ).scalar_one_or_none()
        if invoice is None:
            return 0
        result = session.execute(
            update(Invoice)
            .where(
                *_invoice_group_filter(invoice),
                Invoice.status == "sent",
            )
            .values(status="cancelled", next_reminder_at=None)
        )
        session.commit()
        return result.rowcount or 0


def get_invoice_stats():
    with SessionLocal() as session:
        row = session.execute(
            select(
                func.count().label("total"),
                func.sum(case((Invoice.status == "sent", 1), else_=0)).label(
                    "sent_count"),
                func.sum(case((Invoice.status == "cancelled", 1), else_=0)).label(
                    "cancelled_count"),
                func.sum(case((Invoice.status == "paid", 1), else_=0)).label(
                    "paid_count"),
                func.sum(case((Invoice.status == "paid", Invoice.amount), else_=0)).label(
                    "paid_amount"),
                func.count(func.distinct(Invoice.user_id)
                           ).label("unique_users"),
                func.count(func.distinct(Invoice.class_name)
                           ).label("unique_classes")
            )
        ).first()
        if row:
            return {
                "total": row.total or 0,
                "sent": row.sent_count or 0,
                "cancelled": row.cancelled_count or 0,
                "paid": row.paid_count or 0,
                "paid_amount": row.paid_amount or 0,
                "unique_users": row.unique_users or 0,
                "unique_classes": row.unique_classes or 0
            }
        return {
            "total": 0,
            "sent": 0,
            "cancelled": 0,
            "paid": 0,
            "paid_amount": 0,
            "unique_users": 0,
            "unique_classes": 0,
        }


def get_class_invoice_summary(class_name=None):
    with SessionLocal() as session:
        query = select(
            Invoice.class_name,
            func.count().label("total_invoices"),
            func.sum(case((Invoice.status == "paid", 1), else_=0)
                     ).label("paid_count"),
            func.sum(case((Invoice.status == "paid", Invoice.amount), else_=0)).label(
                "paid_amount"),
            func.count(func.distinct(Invoice.user_id)).label("total_users"),
            func.min(Invoice.sent_at).label("first_sent"),
            func.max(Invoice.sent_at).label("last_sent"),
        )
        if class_name:
            query = query.where(Invoice.class_name == class_name)
        query = query.group_by(Invoice.class_name).order_by(Invoice.class_name)
        rows = session.execute(query).all()
        return [dict(row._mapping) for row in rows]


def get_unpaid_invoices(days=None):
    with SessionLocal() as session:
        query = (
            select(Invoice, User.name.label("user_name"))
            .outerjoin(User, Invoice.user_id == User.chat_id)
            .where(Invoice.status == "sent")
        )
        if days:
            timestamp_limit = int(
                datetime.datetime.now().timestamp()) - (days * 24 * 3600)
            query = query.where(Invoice.sent_at >= timestamp_limit)
        query = query.order_by(Invoice.sent_at.desc())
        rows = session.execute(query).all()
        return [dict(r[0].__dict__, user_name=r[1]) for r in rows]


def get_user_unpaid_invoices(user_id):
    with SessionLocal() as session:
        rows = session.execute(
            select(Invoice)
            .where(Invoice.user_id == user_id, Invoice.status == "sent")
            .order_by(Invoice.sent_at.desc(), Invoice.id.desc())
        ).scalars().all()
        return [dict(row.__dict__) for row in rows]


def get_user_unpaid_invoice(user_id, invoice_id):
    with SessionLocal() as session:
        row = session.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.user_id == user_id,
                Invoice.status == "sent",
            )
        ).scalar_one_or_none()
        return dict(row.__dict__) if row else None


def get_due_invoice_reminders(now_ts=None):
    now_ts = now_ts or int(datetime.datetime.now().timestamp())
    with SessionLocal() as session:
        rows = session.execute(
            select(Invoice)
            .where(
                Invoice.status == "sent",
                Invoice.reminder_interval_days.is_not(None),
                Invoice.next_reminder_at.is_not(None),
                Invoice.next_reminder_at <= now_ts,
            )
            .order_by(Invoice.next_reminder_at, Invoice.id)
        ).scalars().all()
        return [dict(row.__dict__) for row in rows]


def schedule_next_invoice_reminder(invoice_id, next_reminder_at):
    with SessionLocal() as session:
        result = session.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.status == "sent")
            .values(next_reminder_at=next_reminder_at)
        )
        session.commit()
        return result.rowcount > 0


def get_grouped_invoices(days=None, status=None, class_name=None, limit=50):
    with SessionLocal() as session:
        query = select(
            Invoice.class_name,
            Invoice.title,
            Invoice.amount,
            func.count().label("total_count"),
            func.sum(case((Invoice.status == "sent", 1), else_=0)
                     ).label("sent_count"),
            func.sum(case((Invoice.status == "cancelled", 1), else_=0)
                     ).label("cancelled_count"),
            func.sum(case((Invoice.status == "paid", 1), else_=0)
                     ).label("paid_count"),
            func.sum(case((Invoice.status == "paid", Invoice.amount), else_=0)).label(
                "paid_amount"),
            func.min(Invoice.sent_at).label("first_sent"),
            func.max(Invoice.sent_at).label("last_sent")
        )
        if days:
            timestamp_limit = int(
                datetime.datetime.now().timestamp()) - (days * 24 * 3600)
            query = query.where(Invoice.sent_at >= timestamp_limit)
        if status:
            query = query.where(Invoice.status == status)
        if class_name:
            query = query.where(Invoice.class_name == class_name)
        query = query.group_by(Invoice.class_name, Invoice.title, Invoice.amount).order_by(
            func.max(Invoice.sent_at).desc()).limit(limit)
        rows = session.execute(query).all()
        return [dict(row._mapping) for row in rows]
