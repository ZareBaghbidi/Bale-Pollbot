import datetime
from balethon.objects import InlineKeyboard
from app.db.cruds.payments import get_daily_payments_stats, get_payments_stats, get_recent_payments, get_user_payments
from app.db.cruds.users import get_user_name
from app.services.patment import validate_payment_input


def payment_hadnler(uid, text, message, pending_actions, user_states, admins):
    if text == "payments":
        if uid not in admins:
            message.reply("دسترسی denied.")
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
                    user_name = payment.get(
                        'user_name') or payment.get('user_id')
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

            if len(report) > 3800:
                parts = [report[i:i+3800]
                         for i in range(0, len(report), 3800)]
                for part in parts:
                    message.reply(part)
            else:
                message.reply(report)

        except Exception as e:
            print(f"خطا در گزارش payments: {e}")
            message.reply(f"خطا در دریافت گزارش: {str(e)[:100]}")
        return

    if text.startswith("user_payments"):
        if uid not in admins:
            message.reply("دسترسی denied.")
            return

        parts = text.split()
        if len(parts) < 2:
            message.reply(
                "فرمت: user_payments <آیدی کاربر>\nمثال: user_payments 213614271")
            return

        try:
            target_id = int(parts[1])

            user_payments_list = get_user_payments(target_id, 20)
            user_name = get_user_name(target_id) or target_id

            if not user_payments_list:
                message.reply(
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

            message.reply(report)

        except Exception as e:
            print(f"خطا در دریافت پرداخت‌های کاربر: {e}")
            message.reply("خطا در دریافت اطلاعات.")
        return

    if text.startswith("payments_filter"):
        if uid not in admins:
            message.reply("دسترسی denied.")
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

            stats = get_payments_stats(
                days=days, min_amount=min_amount)

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

            message.reply(report)

        except Exception as e:
            print(f"خطا در گزارش payments_filter: {e}")
            message.reply("خطا در تولید گزارش.")
        return

    if text.startswith("get_money"):
        if uid not in admins:
            message.reply("شما دسترسی به این دستور را ندارید.")
            return

        if uid in user_states and user_states[uid] == 'confirm_payment':
            message.reply(
                "شما قبلاً درخواست ارسال صورتحساب دارید. لطفاً ابتدا آن را تکمیل یا لغو کنید.")
            return

        lines = text.strip().split('\n')

        if len(lines) < 5:
            message.reply(
                "📝 *فرمت دستور:*\n"
                "get_money\n"
                "<مبلغ به تومان>\n"
                "<نام کلاس>\n"
                "<عنوان صورتحساب>\n"
                "<توضیحات>\n"
                "*مثال:*\n"
                "get_money\n"
                "5000\n"
                "05\n"
                "حق عضویت\n"
                "پرداخت حق عضویت تیرماه ۱۴۰۳"
            )
            return

        _, amount_str, class_name, title, description = lines[:5]

        validation = validate_payment_input(
            amount_str, class_name, title, description)

        if not validation['valid']:
            error_msg = "⚠️ *خطاهای اعتبارسنجی:*\n"
            for error in validation['errors']:
                error_msg += f"• {error}\n"

            error_msg += "\n🔍 *راهنمایی:*\n"
            error_msg += "- برای مشاهده کلاس‌ها: list_classes\n"
            error_msg += "- عنوان: حداکثر 32 کاراکتر\n"
            error_msg += "- توضیحات: حداکثر 255 کاراکتر"

            message.reply(error_msg)
            return

        summary = (
            f"✅ *اطلاعات معتبر هستند*\n"
            f"📋 *خلاصه صورتحساب:*\n"
            f"• مبلغ: {int(validation['amount_rial'] / 10):,} تومان ({validation['amount_rial']:,} ریال)\n"
            f"• کلاس: {validation['class_name']} ({validation['users_count']} کاربر)\n"
            f"• عنوان: {validation['title']}\n"
            f"• توضیحات: {validation['description']}\n"
            f"آیا از ارسال صورتحساب به {validation['users_count']} کاربر مطمئن هستید؟\n"
            f"✅ تایید\n"
            f"❌ لغو"
        )

        user_states[uid] = 'confirm_payment'
        pending_actions[uid] = validation

        kb = InlineKeyboard(
            [("✅ تایید و ارسال",
                f"confirm_pay_{uid}"), ("❌ لغو", f"cancel_pay_{uid}")]
        )

        message.reply(summary, reply_markup=kb)
        return
