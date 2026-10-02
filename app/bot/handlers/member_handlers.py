from balethon.objects import InlineKeyboard, ReplyKeyboard

from app.bot.messages import MEMBER_HELP
from app.db.cruds.invoices import (
    get_user_unpaid_invoice,
    get_user_unpaid_invoices,
)
from app.db.cruds.users import update_user_name
from app.db.cruds.users import get_user_name
from app.db.cruds.votes import get_user_unanswered_polls
from app.services.poll import send_poll
from app.services.patment import send_invoice_to_user


def member_help_keyboard(message_owner_label="✉️ پیام به ادمین",
                        owner_controls=False):
    rows = [
        ["📊 نظرسنجی پاسخ‌داده‌نشده", "🧾 صورتحساب پرداخت‌نشده"],
        [message_owner_label, "🐞 گزارش باگ"],
        ["✏️ تغییر نام"],
    ]
    if owner_controls:
        rows.extend([
            ["👑 مدیریت ادمین‌ها", "📊 ساخت نظرسنجی"],
            ["🏫 فهرست کلاس‌ها", "👥 مدیریت کاربران کلاس‌ها"],
            ["📨 ارسال پیام", "🗓 نظرسنجی‌های زمان‌بندی‌شده"],
            ["📈 گزارش نظرسنجی‌ها", "📤 خروجی اکسل"],
            ["💳 ساخت صورتحساب", "⛔ غیرفعال‌سازی صورتحساب"],
        ])
    rows.append(["❔ راهنما"])
    return ReplyKeyboard(
        *rows,
        resize=True,
        one_time=False,
        is_persistent=True,
    )


async def send_member_help(message):
    await message.reply(MEMBER_HELP, reply_markup=member_help_keyboard())


async def resend_unanswered_polls(client, uid, message):
    unanswered = get_user_unanswered_polls(uid)
    if not unanswered:
        await message.reply("✅ نظرسنجی فعالی که منتظر پاسخ شما باشد پیدا نشد.")
        return

    poll_questions = {}
    for poll_id, class_name, poll_type, question_id, question_index, question_text in unanswered:
        poll_questions.setdefault(poll_id, []).append(question_id)

    await message.reply(
        f"📊 {len(poll_questions)} نظرسنجیِ فعال و پاسخ‌داده‌نشده برای شما دوباره ارسال می‌شود."
    )
    for poll_id, question_ids in poll_questions.items():
        await send_poll(client, uid, poll_id, question_ids=question_ids)


async def send_unpaid_invoice_list(client, uid, message):
    invoices = get_user_unpaid_invoices(uid)
    if not invoices:
        await message.reply("✅ صورتحساب پرداخت‌نشده‌ای برای شما ثبت نشده است.")
        return

    # Keep each keyboard comfortably below platform limits while preserving one
    # payment button per invoice.
    for start in range(0, len(invoices), 8):
        batch = invoices[start:start + 8]
        lines = ["🧾 صورتحساب‌های پرداخت‌نشدهٔ شما:"]
        rows = []
        for invoice in batch:
            title = invoice.get("title") or "صورتحساب"
            amount = invoice.get("amount") or 0
            class_name = invoice.get("class_name") or "—"
            lines.append(
                f"\n• {title}\n  کلاس: {class_name} | مبلغ: {amount // 10:,} تومان"
            )
            label = title if len(title) <= 24 else title[:21] + "…"
            rows.append([("💳 پرداخت " + label, f"user:pay:{uid}:{invoice['id']}")])
        await message.reply("\n".join(lines), reply_markup=InlineKeyboard(*rows))


async def handle_member_message(uid, text, message, client, user_states, owners,
                                developers):
    if text == "help":
        await send_member_help(message)
        return True
    if text == "unanswered_polls":
        await resend_unanswered_polls(client, uid, message)
        return True
    if text == "unpaid_invoices":
        await send_unpaid_invoice_list(client, uid, message)
        return True
    if text == "change_name":
        user_states[uid] = "waiting_for_rename"
        await message.reply(
            "نام جدید خود را وارد کنید:",
            reply_markup=InlineKeyboard([("❌ لغو", f"user:cancel:{uid}")]),
        )
        return True
    if text == "report_bug":
        if not developers:
            await message.reply("هنوز شناسهٔ برنامه‌نویسان برای دریافت گزارش باگ تنظیم نشده است.")
            return True
        user_states[uid] = "waiting_for_bug_report"
        await message.reply(
            "شرح باگ را بفرستید:",
            reply_markup=InlineKeyboard([("❌ لغو", f"user:cancel:{uid}")]),
        )
        return True
    if text == "message_owner":
        if not owners:
            await message.reply("در حال حاضر ادمینی برای دریافت پیام تنظیم نشده است.")
            return True
        user_states[uid] = "waiting_for_owner_message"
        await message.reply(
            "پیامت را بفرست؛ برای ادمین‌های ربات ارسال می‌شود:",
            reply_markup=InlineKeyboard([("❌ لغو", f"user:cancel:{uid}")]),
        )
        return True
    return False


async def handle_rename_message(uid, text, message, user_states):
    name = text.strip()
    if not name:
        await message.reply("نام نمی‌تواند خالی باشد؛ نام جدید خود را وارد کنید:")
        return True
    if len(name) > 80:
        await message.reply("نام حداکثر می‌تواند ۸۰ نویسه باشد؛ نام کوتاه‌تری بفرستید.")
        return True
    if not update_user_name(uid, name):
        user_states.pop(uid, None)
        await message.reply("حساب کاربری پیدا نشد. برای ثبت‌نام دوباره /help را بفرستید.")
        return True
    user_states.pop(uid, None)
    await message.reply(f"✅ نام شما به «{name}» تغییر کرد.")
    return True


async def forward_owner_message(uid, text, message, client, owners, user_states):
    body = text.strip()
    if not body:
        await message.reply("متن پیام خالی است؛ پیام را بفرست یا لغو کن.")
        return True
    if not owners:
        user_states.pop(uid, None)
        await message.reply("در حال حاضر ادمینی برای دریافت پیام تنظیم نشده است.")
        return True

    sender_name = (get_user_name(uid) or message.author.first_name or "بدون نام")[:80]
    header = (
        "✉️ پیام به ادمین ربات\n"
        f"👤 نام: {sender_name}\n"
        f"🆔 شناسهٔ کاربر: {uid}\n\n"
    )
    # Keep each delivered message below Bale's typical text size limit.
    max_body_length = 3500 - len(header)
    chunks = [body[i:i + max_body_length]
              for i in range(0, len(body), max_body_length)]
    if not chunks:
        chunks = [""]

    delivered = 0
    failed = 0
    for owner_id in sorted(owners):
        try:
            for index, chunk in enumerate(chunks):
                text_to_send = (header if index == 0 else
                                f"ادامهٔ پیام کاربر {uid}:\n") + chunk
                await client.send_message(owner_id, text_to_send)
            delivered += 1
        except Exception as exc:
            failed += 1
            print(f"خطا در ارسال پیام کاربر {uid} به اونر {owner_id}: {exc}")

    user_states.pop(uid, None)
    if delivered and not failed:
        await message.reply("✅ پیامت برای ادمین‌های ربات ارسال شد.")
    elif delivered:
        await message.reply(
            f"پیامت برای {delivered} ادمین ارسال شد؛ "
            f"ارسال برای {failed} ادمین ناموفق بود."
        )
    else:
        await message.reply("ارسال پیام انجام نشد؛ کمی بعد دوباره تلاش کن.")
    return True


async def forward_bug_report(uid, text, message, client, developers, user_states):
    body = text.strip()
    if not body:
        await message.reply("شرح گزارش خالی است؛ جزئیات باگ را بفرستید یا لغو کنید.")
        return True
    if not developers:
        user_states.pop(uid, None)
        await message.reply("هنوز شناسهٔ برنامه‌نویسان برای دریافت گزارش باگ تنظیم نشده است.")
        return True

    sender_name = (get_user_name(uid) or message.author.first_name or "بدون نام")[:80]
    header = (
        "🐞 گزارش باگ در ربات\n"
        f"👤 نام فرستنده: {sender_name}\n"
        f"🆔 شناسهٔ فرستنده: {uid}\n\n"
    )
    max_body_length = 3500 - len(header)
    chunks = [body[i:i + max_body_length]
              for i in range(0, len(body), max_body_length)]

    delivered = 0
    failed = 0
    for developer_id in sorted(developers):
        try:
            for index, chunk in enumerate(chunks):
                text_to_send = (header if index == 0 else
                                f"ادامهٔ گزارش باگ از کاربر {uid}:\n") + chunk
                await client.send_message(developer_id, text_to_send)
            delivered += 1
        except Exception as exc:
            failed += 1
            print(f"خطا در ارسال گزارش باگ کاربر {uid} به برنامه‌نویس {developer_id}: {exc}")

    user_states.pop(uid, None)
    if delivered and not failed:
        await message.reply("✅ گزارش باگ شما برای برنامه‌نویسان ارسال شد.")
    elif delivered:
        await message.reply(
            f"گزارش برای {delivered} برنامه‌نویس ارسال شد؛ ارسال برای {failed} نفر ناموفق بود."
        )
    else:
        await message.reply("ارسال گزارش باگ انجام نشد؛ کمی بعد دوباره تلاش کنید.")
    return True


async def handle_member_callback(callback_query, client, user_states, owners,
                                 developers):
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
    if callback_query.author.id != uid:
        await callback_query.answer("این دکمه برای شما نیست.", show_alert=True)
        return

    if action == "cancel":
        if user_states.get(uid) not in (
                "waiting_for_rename", "waiting_for_owner_message",
                "waiting_for_bug_report"):
            await callback_query.answer("این فرایند منقضی شده است.", show_alert=True)
            return
        user_states.pop(uid, None)
        await callback_query.answer("لغو شد.")
        await callback_query.message.edit_text("عملیات لغو شد.", reply_markup=None)
        return
    if action == "unanswered" and len(parts) == 3:
        await callback_query.answer(" ")
        await resend_unanswered_polls(client, uid, callback_query.message)
        return
    if action == "unpaid" and len(parts) == 3:
        await callback_query.answer(" ")
        await send_unpaid_invoice_list(client, uid, callback_query.message)
        return
    if action == "rename" and len(parts) == 3:
        user_states[uid] = "waiting_for_rename"
        await callback_query.answer(" ")
        await callback_query.message.reply(
            "نام جدید خود را وارد کنید:",
            reply_markup=InlineKeyboard([("❌ لغو", f"user:cancel:{uid}")]),
        )
        return
    if action == "bug" and len(parts) == 3:
        if not developers:
            await callback_query.answer(
                "هنوز شناسهٔ برنامه‌نویسان برای دریافت گزارش باگ تنظیم نشده است.",
                show_alert=True,
            )
            return
        user_states[uid] = "waiting_for_bug_report"
        await callback_query.answer(" ")
        await callback_query.message.reply(
            "شرح باگ را بفرستید:",
            reply_markup=InlineKeyboard([("❌ لغو", f"user:cancel:{uid}")]),
        )
        return
    if action == "message_owner" and len(parts) == 3:
        # Owner IDs are configured explicitly; never route this message to
        # admins or other users.
        if not owners:
            await callback_query.answer(
                "در حال حاضر ادمینی برای دریافت پیام تنظیم نشده است.",
                show_alert=True,
            )
            return
        user_states[uid] = "waiting_for_owner_message"
        await callback_query.answer(" ")
        await callback_query.message.reply(
            "پیامت را بفرست؛ برای ادمین‌های ربات ارسال می‌شود:",
            reply_markup=InlineKeyboard([("❌ لغو", f"user:cancel:{uid}")]),
        )
        return
    if action == "pay" and len(parts) == 4:
        try:
            invoice_id = int(parts[3])
        except ValueError:
            await callback_query.answer("شناسهٔ صورتحساب نامعتبر است.", show_alert=True)
            return
        invoice = get_user_unpaid_invoice(uid, invoice_id)
        if invoice is None:
            await callback_query.answer(
                "صورتحساب پیدا نشد یا قبلاً پرداخت شده است.", show_alert=True
            )
            return
        try:
            await send_invoice_to_user(client, uid, invoice)
        except Exception as exc:
            print(f"خطا در ارسال صورتحساب {invoice_id} به {uid}: {exc}")
            await callback_query.answer(
                "ارسال صورتحساب ناموفق بود؛ کمی بعد دوباره تلاش کنید.",
                show_alert=True,
            )
        else:
            await callback_query.answer("صورتحساب برای پرداخت ارسال شد.")
        return

    await callback_query.answer("این گزینه معتبر نیست یا منقضی شده است.", show_alert=True)
