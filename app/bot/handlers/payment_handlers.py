import datetime
from balethon.objects import InlineKeyboard
from app.db.cruds.classes import get_all_classes, get_users_in_class
from app.db.cruds.payments import (
    get_daily_payments_stats,
    get_payments_stats,
    get_recent_payments,
    get_user_payments,
)
from app.db.cruds.users import get_user_name
from app.services.patment import validate_payment_input


async def _reply_long(message, text, limit=3800):
    if len(text) > limit:
        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
        for part in parts:
            await message.reply(part)
    else:
        await message.reply(text)


async def _check_admin(uid, admins, message, deny_text):
    if uid not in admins:
        await message.reply(deny_text)
        return False
    return True


async def _handle_payments(uid, message, admins):
    if not await _check_admin(uid, admins, message, "دسترسی denied."):
        return

    try:
        payments_stats = get_payments_stats()
        recent_payments = get_recent_payments(10)

        report = f"💳 *گزارش پرداخت‌ها*\n"
        report += f"📊 آمار کلی:\n"
        report += f"• تعداد پرداخت‌ها: {payments_stats['count']}\n"
        report += f"• مجموع مبالغ: {payments_stats['total']//10:,} تومان\n"
        report += f"• کاربران منحصر به فرد: {payments_stats['unique_users']}\n"

        if recent_payments:
            report += f"🕒 *آخرین پرداخت‌ها:*\n"
            report += "─" * 30 + "\n"

            for i, payment in enumerate(recent_payments, 1):
                user_name = payment.get('user_name') or payment.get('user_id')
                amount = payment['amount']
                name = payment.get('name')
                phone = payment.get('phone')
                timestamp = payment['timestamp']

                report += f"{i}. {user_name}\n"
                report += f"   💰 {amount//10:,} تومان\n"
                if name:
                    report += f"   👤 نام: {name}\n"
                if phone:
                    report += f"   📞 تلفن: {phone}\n"
                report += f"   ⏰ {datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')}\n"
                if i < len(recent_payments):
                    report += "   ─────\n"

        await _reply_long(message, report)

    except Exception as e:
        print(f"خطا در گزارش payments: {e}")
        await message.reply(f"خطا در دریافت گزارش: {str(e)[:100]}")
    return


async def _handle_user_payments(uid, text, message, admins):
    if not await _check_admin(uid, admins, message, "دسترسی denied."):
        return

    parts = text.split()
    if len(parts) < 2:
        await message.reply(
            "فرمت: user_payments <آیدی کاربر>\nمثال: user_payments 213614271")
        return

    try:
        target_id = int(parts[1])
        user_payments_list = get_user_payments(target_id, 20)
        user_name = get_user_name(target_id) or target_id

        if not user_payments_list:
            await message.reply(
                f"هیچ پرداختی برای کاربر {user_name} یافت نشد.")
            return

        total_amount = sum(p['amount'] for p in user_payments_list)

        report = f"📋 *پرداخت‌های کاربر:* {user_name}\n"
        report += f"🆔 آیدی: {target_id}\n"
        report += f"💰 مجموع پرداخت‌ها: {total_amount//10:,} تومان\n"
        report += f"📊 تعداد تراکنش‌ها: {len(user_payments_list)}\n"

        report += "*لیست پرداخت‌ها:*\n"
        report += "─" * 30 + "\n"

        for i, payment in enumerate(user_payments_list, 1):
            amount = payment['amount']
            name = payment.get('name')
            phone = payment.get('phone')
            timestamp = payment['timestamp']
            payload = payment['payload']

            report += f"{i}. {amount//10:,} تومان\n"
            if name:
                report += f"   نام: {name}\n"
            if phone:
                report += f"   تلفن: {phone}\n"
            report += f"   زمان: {datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')}\n"
            report += f"   شناسه: {payload}\n"
            if i < len(user_payments_list):
                report += "   ─────\n"

        await message.reply(report)

    except Exception as e:
        print(f"خطا در دریافت پرداخت‌های کاربر: {e}")
        await message.reply("خطا در دریافت اطلاعات.")
    return


async def _handle_payments_filter(uid, text, message, admins):
    if not await _check_admin(uid, admins, message, "دسترسی denied."):
        return

    try:
        days = 7
        min_amount = None

        parts = text.split()
        for part in parts:
            if part.startswith("days="):
                days = int(part.split("=")[1])
            elif part.startswith("min="):
                min_amount_toman = int(part.split("=")[1])
                min_amount = min_amount_toman * 10

        stats = get_payments_stats(days=days, min_amount=min_amount)
        daily_stats = get_daily_payments_stats(days=days)

        report = f"📊 *گزارش پرداخت‌ها ({days} روز گذشته)*\n"
        report += f"فیلترها:\n"
        report += f"• بازه زمانی: {days} روز\n"
        if min_amount:
            report += f"• حداقل مبلغ: {min_amount//10:,} تومان\n"
        report += f"\n📈 آمار:\n"
        report += f"• تعداد پرداخت‌ها: {stats['count']}\n"
        report += f"• مجموع مبالغ: {stats['total']//10:,} تومان\n"
        report += f"• میانگین هر پرداخت: {stats['total']//stats['count']//10 if stats['count'] > 0 else 0:,} تومان\n"
        report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n"

        if daily_stats:
            report += "📅 *آمار روزانه:*\n"
            for daily in daily_stats:
                report += f"• {daily['date']}: {daily['count']} پرداخت - {daily['total']//10:,} تومان\n"

        await message.reply(report)

    except Exception as e:
        print(f"خطا در گزارش payments_filter: {e}")
        await message.reply("خطا در تولید گزارش.")
    return


async def _handle_get_money(uid, text, message, pending_actions, user_states, admins):
    if not await _check_admin(uid, admins, message, "شما دسترسی به این دستور را ندارید."):
        return

    if user_states.get(uid) == 'confirm_payment':
        await message.reply("یک صورتحساب در انتظار تأیید دارید؛ ابتدا آن را تأیید یا لغو کن.")
        return
    if text.strip() != 'get_money':
        await message.reply("برای شروع فقط `get_money` را بفرست؛ اطلاعات را مرحله‌به‌مرحله می‌گیرم.")
        return
    classes = get_all_classes()
    if not classes:
        await message.reply("هنوز کلاسی ساخته نشده است؛ ابتدا یک کلاس بساز.")
        return
    pending_actions[uid] = {'kind': 'get_money_wizard', 'step': 'class'}
    user_states[uid] = 'get_money_class'
    rows = [[(name, f"gm:class:{uid}:{class_id}")] for class_id, name in classes]
    rows.append([("لغو", f"gm:cancel:{uid}")])
    await message.reply("صورتحساب برای کدام کلاس است؟ کلاس را انتخاب کن:",
                        reply_markup=InlineKeyboard(*rows))
    return


def _get_money_cancel_keyboard(uid):
    return InlineKeyboard([("❌ لغو", f"gm:cancel:{uid}")])


async def handle_get_money_message(uid, text, message, pending_actions, user_states, admins):
    state = user_states.get(uid)
    pending = pending_actions.get(uid, {})
    if not state or not state.startswith('get_money_'):
        return False
    if pending.get('kind') != 'get_money_wizard':
        user_states.pop(uid, None)
        return False
    if uid not in admins:
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        await message.reply("دسترسی شما به ساخت صورتحساب وجود ندارد.")
        return True

    if state == 'get_money_class':
        await message.reply("برای ادامه، کلاس را از دکمه‌های پیام قبلی انتخاب کن.")
        return True

    if state == 'get_money_amount':
        normalized = text.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')).strip()
        try:
            amount = int(normalized)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.reply("مبلغ را به‌صورت عدد صحیح و به تومان بفرست؛ مثلاً 5000.",
                                reply_markup=_get_money_cancel_keyboard(uid))
            return True
        pending['amount'] = str(amount)
        pending['step'] = 'title'
        user_states[uid] = 'get_money_title'
        await message.reply("عنوان صورتحساب را بفرست (حداکثر ۳۲ نویسه):",
                            reply_markup=_get_money_cancel_keyboard(uid))
        return True

    if state == 'get_money_title':
        title = text.strip()
        if not title or len(title) > 32:
            await message.reply("عنوان نباید خالی یا بیشتر از ۳۲ نویسه باشد؛ دوباره بفرست.",
                                reply_markup=_get_money_cancel_keyboard(uid))
            return True
        pending['title'] = title
        pending['step'] = 'description'
        user_states[uid] = 'get_money_description'
        await message.reply("توضیحات صورتحساب را بفرست (حداکثر ۲۵۵ نویسه):",
                            reply_markup=_get_money_cancel_keyboard(uid))
        return True

    if state == 'get_money_description':
        description = text.strip()
        if not description or len(description) > 255:
            await message.reply("توضیحات نباید خالی یا بیشتر از ۲۵۵ نویسه باشد؛ دوباره بفرست.",
                                reply_markup=_get_money_cancel_keyboard(uid))
            return True
        validation = validate_payment_input(
            pending['amount'], pending['class_name'], pending['title'], description)
        if not validation['valid']:
            errors = "⚠️ اطلاعات واردشده معتبر نیست:\n" + "\n".join(validation['errors'])
            await message.reply(errors, reply_markup=_get_money_cancel_keyboard(uid))
            return True

        summary = (
            "📋 خلاصه صورتحساب\n"
            f"• مبلغ: {validation['amount_rial'] // 10:,} تومان\n"
            f"• کلاس: {validation['class_name']} ({validation['users_count']} کاربر)\n"
            f"• عنوان: {validation['title']}\n"
            f"• توضیحات: {validation['description']}\n\n"
            f"ارسال صورتحساب برای {validation['users_count']} کاربر را تأیید می‌کنی؟"
        )
        user_states[uid] = 'confirm_payment'
        pending_actions[uid] = validation
        keyboard = InlineKeyboard(
            [("✅ تأیید و ارسال", f"confirm_pay_{uid}"),
             ("❌ لغو", f"cancel_pay_{uid}")])
        await message.reply(summary, reply_markup=keyboard)
        return True

    return False


async def payment_hadnler(uid, text, message, pending_actions, user_states, admins):
    if text == "payments":
        await _handle_payments(uid, message, admins)
        return True

    if text.startswith("user_payments"):
        await _handle_user_payments(uid, text, message, admins)
        return True

    if text.startswith("payments_filter"):
        await _handle_payments_filter(uid, text, message, admins)
        return True

    if text == "get_money" or text.startswith("get_money "):
        await _handle_get_money(uid, text, message,
                                pending_actions, user_states, admins)
        return True

    return False
