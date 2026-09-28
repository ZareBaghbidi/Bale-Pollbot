import datetime
from balethon.objects import InlineKeyboard
from app.db.cruds.invoices import (
    deactivate_invoice,
    get_active_invoice,
    get_active_invoice_count,
    get_active_invoices,
    get_all_invoices,
    get_class_invoice_summary,
    get_grouped_invoices,
    get_invoice_stats,
    get_unpaid_invoices,
)


INVOICE_DEACTIVATION_PAGE_SIZE = 8


def _invoice_deactivation_keyboard(uid, invoices, page, total):
    rows = []
    for invoice in invoices:
        title = (invoice.get("title") or "صورتحساب")[:16]
        class_name = (invoice.get("class_name") or "عمومی")[:10]
        label = f"⛔ #{invoice['id']} {title} / {class_name} / {invoice['user_id']}"
        rows.append([(label, f"ivd:select:{uid}:{invoice['id']}:{page}")])

    navigation = []
    if page > 0:
        navigation.append(("⬅️ قبلی", f"ivd:list:{uid}:{page - 1}"))
    if (page + 1) * INVOICE_DEACTIVATION_PAGE_SIZE < total:
        navigation.append(("بعدی ➡️", f"ivd:list:{uid}:{page + 1}"))
    if navigation:
        rows.append(navigation)
    rows.append([("بستن", f"ivd:close:{uid}")])
    return InlineKeyboard(*rows)


async def _show_active_invoice_list(uid, message, page=0, edit=False):
    total = get_active_invoice_count()
    if not total:
        text = "صورتحساب فعالی برای غیرفعال‌کردن وجود ندارد."
        if edit:
            await message.edit_text(text, reply_markup=None)
        else:
            await message.reply(text)
        return

    last_page = (total - 1) // INVOICE_DEACTIVATION_PAGE_SIZE
    page = min(max(page, 0), last_page)
    offset = page * INVOICE_DEACTIVATION_PAGE_SIZE
    invoices = get_active_invoices(
        offset=offset, limit=INVOICE_DEACTIVATION_PAGE_SIZE)
    text = (
        f"🧾 صورتحساب‌های فعال ({total} مورد)\n"
        "برای انتخاب و غیرفعال‌کردن، دکمهٔ صورتحساب را بزنید.\n"
        f"صفحهٔ {page + 1} از {last_page + 1}"
    )
    keyboard = _invoice_deactivation_keyboard(uid, invoices, page, total)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.reply(text, reply_markup=keyboard)


async def _handle_invoice_deactivation(uid, message, owners):
    if uid not in owners:
        await message.reply("غیرفعال‌کردن صورتحساب فقط برای اونرها امکان‌پذیر است.")
        return
    await _show_active_invoice_list(uid, message)


async def handle_invoice_deactivation_callback(callback_query, settings):
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    action = parts[1]
    try:
        uid = int(parts[2])
    except ValueError:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    if callback_query.author.id != uid or uid not in settings.owners:
        await callback_query.answer("این گزینه فقط برای اونرهاست.", show_alert=True)
        return

    if action == "close" and len(parts) == 3:
        await callback_query.answer("فهرست بسته شد.")
        await callback_query.message.edit_text(
            "فهرست صورتحساب‌های فعال بسته شد.", reply_markup=None)
        return

    if action == "list" and len(parts) == 4:
        try:
            page = int(parts[3])
        except ValueError:
            await callback_query.answer("شمارهٔ صفحه نامعتبر است.", show_alert=True)
            return
        await callback_query.answer(" ")
        await _show_active_invoice_list(
            uid, callback_query.message, page, edit=True)
        return

    if action in ("select", "confirm") and len(parts) == 5:
        try:
            invoice_id = int(parts[3])
            page = int(parts[4])
        except ValueError:
            await callback_query.answer("شناسهٔ صورتحساب نامعتبر است.", show_alert=True)
            return
        invoice = get_active_invoice(invoice_id)
        if invoice is None:
            await callback_query.answer(
                "این صورتحساب دیگر فعال نیست.", show_alert=True)
            await _show_active_invoice_list(
                uid, callback_query.message, page, edit=True)
            return

        if action == "select":
            class_name = invoice.get("class_name") or "عمومی"
            user_name = invoice.get("user_name") or invoice["user_id"]
            summary = (
                f"صورتحساب #{invoice_id}\n"
                f"عنوان: {invoice['title']}\n"
                f"کلاس: {class_name}\n"
                f"کاربر: {user_name} (شناسه: {invoice['user_id']})\n"
                f"مبلغ: {invoice['amount'] // 10:,} تومان\n\n"
                "با تأیید، صورتحساب از فهرست پرداخت‌نشده حذف می‌شود و یادآوری آن متوقف خواهد شد."
            )
            keyboard = InlineKeyboard(
                [("✅ تأیید غیرفعال‌سازی", f"ivd:confirm:{uid}:{invoice_id}:{page}")],
                [("↩️ بازگشت به فهرست", f"ivd:list:{uid}:{page}")],
            )
            await callback_query.answer("صورتحساب انتخاب شد.")
            await callback_query.message.edit_text(summary, reply_markup=keyboard)
            return

        if not deactivate_invoice(invoice_id):
            await callback_query.answer(
                "صورتحساب غیرفعال نشد؛ احتمالاً قبلاً تغییر کرده است.",
                show_alert=True,
            )
            return
        await callback_query.answer("صورتحساب غیرفعال شد.")
        await callback_query.message.edit_text(
            f"✅ صورتحساب «{invoice['title']}» برای کاربر {invoice['user_id']} غیرفعال شد.",
            reply_markup=None,
        )
        return

    await callback_query.answer("این گزینه معتبر نیست یا منقضی شده است.", show_alert=True)


async def _reply_long(message, text, limit=3800):
    if len(text) > limit:
        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
        for part in parts:
            await message.reply(part)
    else:
        await message.reply(text)


async def _check_admin(uid, admins, message):
    if uid not in admins:
        await message.reply("دسترسی denied.")
        return False
    return True


async def _handle_invoices(uid, message, admins):
    if not await _check_admin(uid, admins, message):
        return

    try:
        stats = get_invoice_stats()
        grouped_invoices = get_grouped_invoices(limit=15)

        report = f"🧾 *گزارش صورتحساب‌های ارسال شده (گروه‌بندی شده)*\n"
        report += f"📊 *آمار کلی:*\n"
        report += f"• کل صورتحساب‌ها: {stats['total']}\n"
        report += f"• فعال / ارسال شده: {stats['sent']}\n"
        report += f"• غیرفعال‌شده: {stats['cancelled']}\n"
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
                sent_count = group['sent_count']
                cancelled_count = group['cancelled_count']
                paid_count = group['paid_count']
                paid_amount = group['paid_amount']
                last_sent = datetime.datetime.fromtimestamp(
                    group['last_sent']).strftime('%m/%d %H:%M')

                report += f"{i}. 🏫 *{class_name}*\n"
                report += f"   📝 {title}\n"
                report += f"   💰 {amount//10:,} تومان\n"
                report += f"   📤 فعال / ارسال شده: {sent_count}\n"
                report += f"   ⛔ غیرفعال‌شده: {cancelled_count}\n"
                report += f"   ✅ پرداخت شده: {paid_count}\n"
                report += f"   💳 مبلغ پرداختی: {paid_amount//10:,} تومان\n"
                report += f"   ⏰ آخرین ارسال: {last_sent}\n"

                if i < len(grouped_invoices):
                    report += "   ─────\n"

        report += "\n🔍 *دستورات بیشتر:*\n"
        report += "• /invoices_filter days=7 status=paid\n"
        report += "• /invoices_class 05\n"
        report += "• /invoices_unpaid\n"
        report += "• /invoice_stats\n"

        await _reply_long(message, report)

    except Exception as e:
        print(f"خطا در گزارش invoices: {e}")
        await message.reply(f"خطا: {str(e)[:100]}")
    return


async def _handle_invoices_filter(uid, text, message, admins):
    if not await _check_admin(uid, admins, message):
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
                cancelled_count = group['cancelled_count']
                last_sent = datetime.datetime.fromtimestamp(
                    group['last_sent']).strftime('%m/%d')

                report += f"{i}. 🏫 {class_name} | 📝 {title}\n"
                report += f"   💰 {amount//10:,} تومان | کل {total_count} | ✅ {paid_count} | ⛔ {cancelled_count}\n"
                report += f"   ⏰ {last_sent}\n"

        if len(report) > 3800:
            await message.reply(report[:3800])
        else:
            await message.reply(report)

    except Exception as e:
        print(f"خطا در invoices_filter: {e}")
        await message.reply("خطا در فیلتر")
    return


async def _handle_invoices_unpaid(uid, message, admins):
    if not await _check_admin(uid, admins, message):
        return

    try:
        unpaid_invoices = get_unpaid_invoices(days=30)

        if not unpaid_invoices:
            await message.reply(
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

        report += "\n💡 *راهنمایی:* برای فعال‌کردن صورتحساب جدید از دستور /get_money استفاده کنید."

        if len(report) > 3800:
            await message.reply(report[:3800])
        else:
            await message.reply(report)

    except Exception as e:
        print(f"خطا در invoices_unpaid: {e}")
        await message.reply("خطا در دریافت پرداخت نشده‌ها")
    return


async def _handle_invoice_stats(uid, message, admins):
    if not await _check_admin(uid, admins, message):
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

        await message.reply(report)

    except Exception as e:
        print(f"خطا در invoice_stats: {e}")
        await message.reply("خطا در تولید آمار")
    return


async def invoice_hadnler(uid, text, message, admins):
    if text == "deactivate_invoice":
        await _handle_invoice_deactivation(uid, message, admins)
        return True

    if text == "invoices":
        await _handle_invoices(uid, message, admins)
        return True

    if text.startswith("invoices_filter"):
        await _handle_invoices_filter(uid, text, message, admins)
        return True

    if text == "invoices_unpaid":
        await _handle_invoices_unpaid(uid, message, admins)
        return True

    if text == "invoice_stats":
        await _handle_invoice_stats(uid, message, admins)
        return True

    return False
