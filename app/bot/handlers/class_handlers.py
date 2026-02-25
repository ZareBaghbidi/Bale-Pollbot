import datetime
from balethon.objects import InlineKeyboard
from app.bot.messages import WRONG_REMOVE_FROM_CLASS_HELP, WRONG_SEND_MESSAGE_HELP
from app.db.cruds.classes import (
    create_class,
    get_all_classes,
    get_class_id_by_name,
    get_class_users_with_names,
    get_users_in_class,
    remove_user_from_class,
)

from db import get_all_invoices, get_class_invoice_summary


def _reply_long(message, text):
    if len(text) > 3800:
        parts = [text[i:i+3800] for i in range(0, len(text), 3800)]
        for part in parts:
            message.reply(part)
    else:
        message.reply(text)


def _handle_send_message(uid, text, message, pending_actions, user_states):
    if not text.startswith("send_message"):
        return False

    parts = text.split('\n', 1)
    first_line = parts[0].strip()
    if len(parts) < 2 or not parts[1].strip():
        message.reply(WRONG_SEND_MESSAGE_HELP)
        return True

    try:
        _, class_name = first_line.split(maxsplit=1)
    except ValueError:
        message.reply("❌ لطفاً نام کلاس را وارد کنید.\nمثال: send_message 05")
        return True

    class_name = class_name.strip()
    message_text = parts[1].strip()

    class_id = get_class_id_by_name(class_name)
    if class_id is None:
        message.reply(f"❌ کلاس '{class_name}' یافت نشد.")
        return True

    user_ids = get_users_in_class(class_id)
    if not user_ids:
        message.reply(f"📭 هیچ کاربری در کلاس '{class_name}' وجود ندارد.")
        return True

    pending_actions[uid] = {
        'kind': 'send_message',
        'class_name': class_name,
        'message_text': message_text,
        'user_ids': user_ids
    }
    user_states[uid] = 'confirm_send_message'

    summary = f"📨 *ارسال پیام به کلاس {class_name}*\n\n"
    summary += f"👥 تعداد گیرندگان: {len(user_ids)} نفر\n"
    summary += f"📝 متن پیام:\n---\n{message_text}\n---\n\n"
    summary += "آیا از ارسال این پیام اطمینان دارید؟"

    kb = InlineKeyboard(
        [
            ("✅ بله، ارسال شود", f"confirm_sendmsg_{uid}"),
            ("❌ خیر، لغو", f"cancel_sendmsg_{uid}")
        ]
    )
    message.reply(summary, reply_markup=kb)
    return True


def _handle_remove_from_class(text, message):
    if not text.startswith("remove_from_class"):
        return False

    parts = text.split()
    if len(parts) != 3:
        message.reply(WRONG_REMOVE_FROM_CLASS_HELP)
        return True

    class_name = parts[1].strip()
    try:
        user_id = int(parts[2].strip())
    except ValueError:
        message.reply("❌ آیدی کاربر باید یک عدد معتبر باشد.")
        return True

    success, result = remove_user_from_class(class_name, user_id)
    message.reply(result)
    return True


def _handle_create_class(text, message):
    if not text.startswith("create_class"):
        return False

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply("لطفاً نام کلاس را وارد کنید.\nمثال: create_class 05")
        return True

    class_name = parts[1].strip()
    class_id = create_class(class_name)
    if class_id:
        message.reply(f"کلاس '{class_name}' با موفقیت ایجاد شد.")
    else:
        message.reply(f"کلاس '{class_name}' قبلاً وجود دارد.")
    return True


def _handle_list_classes(text, message):
    if text != "list_classes":
        return False

    classes = get_all_classes()
    if not classes:
        message.reply("هیچ کلاسی وجود ندارد.")
        return True

    msg = "کلاس‌های موجود:\n"
    for cid, cname in classes:
        count = len(get_users_in_class(cid))
        msg += f"- {cname} (تعداد اعضا: {count})\n"
    message.reply(msg)
    return True


def _handle_class_users(uid, text, message, admins):
    if not text.startswith("class_users"):
        return False

    if uid not in admins:
        message.reply("دسترسی denied.")
        return True

    parts = text.split()
    if len(parts) < 2:
        message.reply("فرمت: class_users <نام کلاس>\nمثال: class_users 05")
        return True

    class_name = parts[1]
    users_list = get_class_users_with_names(class_name)

    if users_list is None:
        message.reply(f"❌ کلاس '{class_name}' یافت نشد.")
        return True

    if not users_list:
        message.reply(f"📭 هیچ کاربری در کلاس '{class_name}' وجود ندارد.")
        return True

    msg = f"👥 لیست کاربران کلاس '{class_name}':\n"
    for i, (user_id, name) in enumerate(users_list, 1):
        msg += f"{i}. {name}\n"
        msg += f"   آیدی: {user_id}\n"

    msg += f"\n📊 آمار: {len(users_list)} کاربر"
    _reply_long(message, msg)
    return True


def _handle_delete_class(uid, text, message, pending_actions, user_states):
    if not text.startswith("delete_class"):
        return False

    parts = text.split()
    if len(parts) != 2:
        message.reply(
            "📝 *فرمت:*\n`delete_class <نام کلاس>`\nمثال: delete_class 05")
        return True

    class_name = parts[1].strip()
    class_id = get_class_id_by_name(class_name)
    if not class_id:
        message.reply(f"❌ کلاس '{class_name}' وجود ندارد.")
        return True

    pending_actions[uid] = {'kind': 'delete_class', 'class_name': class_name}
    user_states[uid] = 'confirm_delete_class'

    summary = f"⚠️ *آیا از حذف کلاس '{class_name}' اطمینان دارید؟*\n\n"
    summary += "🔸 تمام نظرسنجی‌ها و پاسخ‌های مرتبط با این کلاس\n"
    summary += "🔸 تمام صورتحساب‌های ارسال شده برای این کلاس\n"
    summary += "🔸 ارتباط کاربران با این کلاس\n\n"
    summary += "همگی **برای همیشه حذف** خواهند شد. این عمل قابل بازگشت نیست."

    kb = InlineKeyboard(
        [
            ("✅ بله، حذف شود", f"confirm_delclass_{uid}"),
            ("❌ خیر، لغو", f"cancel_delclass_{uid}")
        ]
    )
    message.reply(summary, reply_markup=kb)
    return True


def _handle_invoices_class(uid, text, message, admins):
    if not text.startswith("invoices_class"):
        return False

    if uid not in admins:
        message.reply("دسترسی denied.")
        return True

    parts = text.split()
    if len(parts) < 2:
        message.reply(
            "فرمت: invoices_class <نام کلاس>\nمثال: invoices_class 05")
        return True

    class_name = parts[1]

    try:
        class_invoices = get_all_invoices(class_name=class_name, limit=50)

        if not class_invoices:
            message.reply(f"هیچ صورتحسابی برای کلاس '{class_name}' یافت نشد.")
            return True

        class_summary = get_class_invoice_summary(class_name)
        summary = class_summary[0] if class_summary else {}

        report = f"🏫 *صورتحساب‌های کلاس: {class_name}*\n"
        if summary:
            report += f"📊 *آمار کلاس:*\n"
            report += f"• کل صورتحساب‌ها: {summary['total_invoices']}\n"
            report += f"• پرداخت شده: {summary['paid_count']}\n"
            report += f"• مبلغ پرداخت شده: {summary['paid_amount']//10:,} تومان\n"
            report += f"• تعداد کاربران: {summary['total_users']}\n"
            report += (
                f"• نرخ پرداخت: "
                f"{round(summary['paid_count']/summary['total_invoices']*100, 1) if summary['total_invoices'] > 0 else 0}%\n"
            )

        user_status = {}
        for invoice in class_invoices:
            user_id = invoice['user_id']
            if user_id not in user_status:
                user_status[user_id] = {
                    'name': invoice.get('user_name'),
                    'total': 0,
                    'paid': 0
                }
            user_status[user_id]['total'] += 1
            if invoice['status'] == 'paid':
                user_status[user_id]['paid'] += 1

        report += f"👥 *وضعیت کاربران:*\n"
        for user_id, stats in list(user_status.items())[:15]:
            status_icon = "✅" if stats['paid'] > 0 else "📤"
            report += f"• {status_icon} {stats['name'] or user_id}: {stats['paid']}/{stats['total']}\n"

        if len(user_status) > 15:
            report += f"• و {len(user_status) - 15} کاربر دیگر...\n"

        unpaid_invoices = [
            inv for inv in class_invoices if inv['status'] != 'paid'
        ][:10]
        if unpaid_invoices:
            report += f"\n📋 *پرداخت نشده‌ها (10 مورد اول):*\n"
            for invoice in unpaid_invoices[:10]:
                user_name = invoice.get(
                    'user_name') or f"ID: {invoice['user_id']}"
                sent_time = datetime.datetime.fromtimestamp(
                    invoice['sent_at']
                ).strftime('%m/%d')
                report += f"• {user_name} | {invoice['amount']//10:,} تومان | {sent_time}\n"

        _reply_long(message, report)

    except Exception as e:
        print(f"خطا در invoices_class: {e}")
        message.reply("خطا در دریافت اطلاعات کلاس")
    return True


def class_hadnler(uid, text, message, pending_actions, user_states, admins):
    if _handle_send_message(uid, text, message, pending_actions, user_states):
        return
    if _handle_remove_from_class(text, message):
        return
    if _handle_create_class(text, message):
        return
    if _handle_list_classes(text, message):
        return
    if _handle_class_users(uid, text, message, admins):
        return
    if _handle_delete_class(uid, text, message, pending_actions, user_states):
        return
    if _handle_invoices_class(uid, text, message, admins):
        return
