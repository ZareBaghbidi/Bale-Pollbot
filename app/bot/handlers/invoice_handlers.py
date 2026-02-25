
import datetime
from app.db.cruds.invoices import (
    get_all_invoices,
    get_class_invoice_summary,
    get_grouped_invoices,
    get_invoice_stats,
    get_unpaid_invoices
)


def invoice_hadnler(uid, text, message, admins):
    if text == "invoices":
        if uid not in admins:
            message.reply("دسترسی denied.")
            return

        try:
            stats = get_invoice_stats()
            grouped_invoices = get_grouped_invoices(limit=15)

            report = f"🧾 *گزارش صورتحساب‌های ارسال شده (گروه‌بندی شده)*\n"
            report += f"📊 *آمار کلی:*\n"
            report += f"• کل صورتحساب‌ها: {stats['total']}\n"
            report += f"• ارسال شده: {stats['sent']}\n"
            report += f"• پرداخت شده: {stats['paid']} ({stats['paid_amount']//10:,} تومان)\n"
            report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n"
            report += f"• کلاس‌های منحصر به فرد: {stats['unique_classes']}\n"

            if grouped_invoices:
                report += f"🕒 *آخرین صورتحساب‌ها:*\n"
                report += "─" * 40 + "\n"

                for i, group in enumerate(grouped_invoices, 1):
                    class_name = group['class_name'] or 'بدون کلاس'
                    title = group['title']
                    amount = group['amount']
                    total_count = group['total_count']
                    paid_count = group['paid_count']
                    paid_amount = group['paid_amount']
                    last_sent = datetime.datetime.fromtimestamp(
                        group['last_sent']).strftime('%m/%d %H:%M')

                    report += f"{i}. 🏫 *{class_name}*\n"
                    report += f"   📝 {title}\n"
                    report += f"   💰 {amount//10:,} تومان\n"
                    report += f"   📤 ارسال شده: {total_count}\n"
                    report += f"   ✅ پرداخت شده: {paid_count}\n"
                    report += f"   💳 مبلغ پرداختی: {paid_amount//10:,} تومان\n"
                    report += f"   ⏰ آخرین ارسال: {last_sent}\n"

                    if i < len(grouped_invoices):
                        report += "   ─────\n"

            report += "\n🔍 *دستورات بیشتر:*\n"
            report += "• `invoices_filter days=7 status=paid`\n"
            report += "• `invoices_class 05`\n"
            report += "• `invoices_unpaid`\n"
            report += "• `invoice_stats`\n"

            if len(report) > 3800:
                parts = [report[i:i+3800]
                         for i in range(0, len(report), 3800)]
                for part in parts:
                    message.reply(part)
            else:
                message.reply(report)

        except Exception as e:
            print(f"خطا در گزارش invoices: {e}")
            message.reply(f"خطا: {str(e)[:100]}")
        return

    if text.startswith("invoices_filter"):
        if uid not in admins:
            message.reply("دسترسی denied.")
            return

        try:
            days = None
            status = None
            class_name = None

            parts = text.split()
            for part in parts:
                if part.startswith("days="):
                    days = int(part.split("=")[1])
                elif part.startswith("status="):
                    status = part.split("=")[1]
                elif part.startswith("class="):
                    class_name = part.split("=")[1]

            grouped_invoices = get_grouped_invoices(
                days=days, status=status, class_name=class_name, limit=30)

            report = f"🔍 *صورتحساب‌های فیلتر شده (گروه‌بندی)*\n"
            report += f"📊 *فیلترها:*\n"
            if days:
                report += f"• روزهای گذشته: {days}\n"
            if status:
                report += f"• وضعیت: {status}\n"
            if class_name:
                report += f"• کلاس: {class_name}\n"

            report += f"• تعداد گروه‌ها: {len(grouped_invoices)}\n"

            if grouped_invoices:
                report += f"📋 *نتایج:*\n"
                for i, group in enumerate(grouped_invoices, 1):
                    class_name = group['class_name'] or 'بدون کلاس'
                    title = group['title'][:20] + \
                        '...' if len(
                            group['title']) > 20 else group['title']
                    amount = group['amount']
                    total_count = group['total_count']
                    paid_count = group['paid_count']
                    last_sent = datetime.datetime.fromtimestamp(
                        group['last_sent']).strftime('%m/%d')

                    report += f"{i}. 🏫 {class_name} | 📝 {title}\n"
                    report += f"   💰 {amount//10:,} تومان | 📤 {total_count} | ✅ {paid_count}\n"
                    report += f"   ⏰ {last_sent}\n"

            if len(report) > 3800:
                message.reply(report[:3800])
            else:
                message.reply(report)

        except Exception as e:
            print(f"خطا در invoices_filter: {e}")
            message.reply("خطا در فیلتر")
        return

    if text == "invoices_unpaid":
        if uid not in admins:
            message.reply("دسترسی denied.")
            return

        try:
            unpaid_invoices = get_unpaid_invoices(days=30)

            if not unpaid_invoices:
                message.reply(
                    "✅ *هیچ صورتحساب پرداخت نشده‌ای در ۳۰ روز گذشته وجود ندارد.*")
                return

            report = f"📋 *صورتحساب‌های پرداخت نشده (۳۰ روز گذشته)*\n"
            report += f"📊 تعداد کل: {len(unpaid_invoices)}\n"
            report += f"💰 مجموع مبالغ: {sum(inv['amount'] for inv in unpaid_invoices)//10:,} تومان\n"

            class_groups = {}
            for invoice in unpaid_invoices:
                class_name = invoice.get('class_name', 'بدون کلاس')
                if class_name not in class_groups:
                    class_groups[class_name] = []
                class_groups[class_name].append(invoice)

            for class_name, invoices in list(class_groups.items())[:5]:
                report += f"🏫 *{class_name}:* {len(invoices)} صورتحساب\n"
                for invoice in invoices[:3]:
                    user_name = invoice.get(
                        'user_name') or f"ID: {invoice['user_id']}"
                    sent_time = datetime.datetime.fromtimestamp(
                        invoice['sent_at']).strftime('%m/%d')
                    report += f"  • {user_name} | {invoice['amount']//10:,} تومان | {sent_time}\n"

                if len(invoices) > 3:
                    report += f"  • و {len(invoices) - 3} مورد دیگر...\n"

                report += "\n"

            if len(class_groups) > 5:
                report += f"و {len(class_groups) - 5} کلاس دیگر...\n"

            report += "\n💡 *راهنمایی:* برای ارسال یادآوری می‌توانید از دستور `get_money` مجدداً استفاده کنید."

            if len(report) > 3800:
                message.reply(report[:3800])
            else:
                message.reply(report)

        except Exception as e:
            print(f"خطا در invoices_unpaid: {e}")
            message.reply("خطا در دریافت پرداخت نشده‌ها")
        return

    if text == "invoice_stats":
        if uid not in admins:
            message.reply("دسترسی denied.")
            return

        try:
            stats = get_invoice_stats()

            class_summaries = get_class_invoice_summary()

            report = f"📈 *آمار دقیق صورتحساب‌ها*\n"

            report += f"📊 *آمار کلی:*\n"
            report += f"• کل صورتحساب‌ها: {stats['total']}\n"
            report += f"• نرخ پرداخت: {round(stats['paid']/stats['total']*100, 1) if stats['total'] > 0 else 0}%\n"
            report += f"• میانگین مبلغ پرداختی: {stats['paid_amount']//stats['paid']//10 if stats['paid'] > 0 else 0:,} تومان\n"
            report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n"
            report += f"• کلاس‌های فعال: {stats['unique_classes']}\n"

            if class_summaries:
                report += f"🏫 *آمار کلاس‌ها:*\n"
                for summary in class_summaries[:10]:
                    class_name = summary['class_name'] or 'بدون کلاس'
                    paid_rate = round(
                        summary['paid_count']/summary['total_invoices']*100, 1) if summary['total_invoices'] > 0 else 0
                    avg_amount = summary['paid_amount']//summary['paid_count']//10 if summary['paid_count'] > 0 else 0

                    report += f"• {class_name}: {summary['paid_count']}/{summary['total_invoices']} ({paid_rate}%) | "
                    report += f"💰 {avg_amount:,} تومان | 👥 {summary['total_users']} کاربر\n"

                if len(class_summaries) > 10:
                    report += f"• و {len(class_summaries) - 10} کلاس دیگر...\n"

            daily_invoices = get_all_invoices(days=7)
            if daily_invoices:
                days_dict = {}
                for invoice in daily_invoices:
                    day = datetime.datetime.fromtimestamp(
                        invoice['sent_at']).strftime('%Y-%m-%d')
                    if day not in days_dict:
                        days_dict[day] = {'total': 0, 'paid': 0}
                    days_dict[day]['total'] += 1
                    if invoice['status'] == 'paid':
                        days_dict[day]['paid'] += 1

                report += f"\n📅 *آمار ۷ روز گذشته:*\n"
                for day, stats_day in sorted(days_dict.items(), reverse=True)[:7]:
                    report += f"• {day}: {stats_day['paid']}/{stats_day['total']} پرداخت\n"

            message.reply(report)

        except Exception as e:
            print(f"خطا در invoice_stats: {e}")
            message.reply("خطا در تولید آمار")
        return
