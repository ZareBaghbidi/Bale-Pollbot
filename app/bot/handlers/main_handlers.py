import time
import traceback
from app.bot.handlers.class_handlers import (
    class_hadnler,
    handle_send_message_input,
)
from app.services.poll import send_poll
from app.services.patment import process_successful_payment
from app.db.cruds.votes import get_stats
from app.db.cruds import *
from app.bot.handlers.user_handlers import user_hadnler
from app.bot.handlers.poll_handlers import (
    poll_hadnler, handle_poll_question, handle_poll_schedule_time,
    handle_scheduled_polls_command,
)
from app.bot.handlers.payment_handlers import payment_hadnler, handle_get_money_message
from app.bot.handlers.invoice_handlers import invoice_hadnler
from app.bot.handlers.member_handlers import (
    handle_member_message,
    handle_rename_message,
    forward_owner_message,
    forward_bug_report,
    member_help_keyboard,
)
from app.services.patment import process_successful_payment
from app.services.poll import send_poll
from app.db.export_votes import export_votes
from app.bot.config import save_admins
from app.bot.messages import ADMIN_HELP, OWNER_HELP


COMMAND_NAMES = {
    "help", "unanswered_polls", "unpaid_invoices", "change_name", "message_owner",
    "report_bug", "deactivate_invoice",
    "roles", "add_admin", "remove_admin", "create_poll", "list_classes",
    "users", "list_users", "add_users", "create_class", "class_users",
    "remove_from_class", "delete_class", "send_message", "stop", "clear",
    "list_polls", "view_responses", "scheduled_polls", "cancel_scheduled",
    "report", "export_votes", "get_money", "payments", "user_payments",
    "payments_filter", "invoices", "invoices_filter", "invoices_class",
    "invoices_unpaid", "invoice_stats",
}

MEMBER_COMMANDS = {
    "help", "unanswered_polls", "unpaid_invoices", "change_name",
    "message_owner", "report_bug",
}
ADMIN_COMMANDS = MEMBER_COMMANDS | {"create_poll", "list_classes"}

HELP_BUTTON_COMMANDS = {
    "📊 نظرسنجی پاسخ‌داده‌نشده": "unanswered_polls",
    "🧾 صورتحساب پرداخت‌نشده": "unpaid_invoices",
    "✏️ تغییر نام": "change_name",
    "🐞 گزارش باگ": "report_bug",
    "❔ راهنما": "help",
    "⛔ غیرفعال‌سازی صورتحساب": "deactivate_invoice",
    "📊 نظرسنجی‌های فعالِ بی‌پاسخ": "unanswered_polls",
    "🧾 صورتحساب‌های پرداخت‌نشده": "unpaid_invoices",
    "✏️ تغییر نام کاربری": "change_name",
    "✉️ پیام به ادمین": "message_owner",
    "✉️ پیام به اونرها": "message_owner",
    "✉️ پیام به مسئولان ربات": "message_owner",
    "🐞 گزارش باگ در ربات": "report_bug",
}


def _normalize_command(text):
    if text.startswith("/"):
        remaining = text[1:].strip()
        parts = remaining.split(maxsplit=1)
        command = parts[0].split("@", maxsplit=1)[0] if parts else ""
        if command in COMMAND_NAMES:
            return command + (" " + parts[1] if len(parts) > 1 else "")
    return text


def _command_name(text):
    """Return a known command at the start of a message, if present."""
    stripped = text.strip()
    if not stripped:
        return None
    token = stripped.split(maxsplit=1)[0]
    if token.startswith("/"):
        token = token[1:]
    token = token.split("@", maxsplit=1)[0]
    return token if token in COMMAND_NAMES else None


def _can_use_command(command, is_owner, is_admin):
    if is_owner:
        return True
    if is_admin:
        return command in ADMIN_COMMANDS
    return command in MEMBER_COMMANDS


async def _notify_owners_of_unrecognized_message(uid, text, message, client,
                                                 owners):
    display_name = get_user_name(uid) or message.author.first_name or "کاربر"
    header = (
        "⚠️ پیام خارج از دستورهای ربات\n"
        f"👤 نام: {display_name}\n"
        f"🆔 شناسهٔ کاربر: {uid}\n\n"
    )
    body = text.strip() or "(متن خالی)"
    body = body[:3500 - len(header)]
    notification = header + body
    for owner_id in sorted(owners - {uid}):
        try:
            await client.send_message(owner_id, notification)
        except Exception as exc:
            print(f"خطا در گزارش پیام خارج از دستور کاربر {uid} به اونر {owner_id}: {exc}")
    await message.reply(
        f"{display_name}، این پیام با هیچ‌کدام از دستورهای ربات تطبیق نداشت."
        " برای دیدن راهنما /help را بفرستید."
    )


async def on_message(message, settings, client, user_states, pending_actions, all_users):
    try:
        if hasattr(message, 'successful_payment') and message.successful_payment:
            print("🔄 پرداخت از طریق on_message دریافت شد (پشتیبان)")
            process_successful_payment(client, settings, message)
            return

        uid = message.author.id
        raw_text = (message.text or "").strip()
        active_input_command = _command_name(_normalize_command(raw_text))
        if active_input_command:
            active_is_owner = uid in settings.owners
            active_is_admin = uid in settings.admins
            if not _can_use_command(
                    active_input_command, active_is_owner, active_is_admin):
                await message.reply("⛔ شما برای استفاده از این دستور دسترسی ندارید.")
                return
        text_states = {
            "waiting_for_name", "waiting_for_rename", "waiting_for_text",
            "waiting_for_owner_message", "waiting_for_bug_report",
            "poll_wizard_question", "get_money_amount", "get_money_title",
            "get_money_description", "waiting_add_users", "send_message_id",
            "send_message_text",
        }
        text = (raw_text if user_states.get(uid) in text_states
                else _normalize_command(raw_text))
        if user_states.get(uid) not in text_states:
            text = HELP_BUTTON_COMMANDS.get(text, text)
        parts = text.split('\n')
        aline = text.split()

        if uid in user_states:
            state = user_states[uid]
            if state == 'waiting_for_name':
                if not text:
                    await message.reply("لطفاً نام خود را وارد کنید.")
                    return
                name = text.strip()
                if not name:
                    await message.reply(
                        "نام نمی‌تواند خالی باشد. لطفاً نام خود را وارد کنید.")
                    return

                try:
                    add_user(uid, name)
                    all_users.add(uid)
                except Exception as e:
                    print("add_user DB error:", e)
                    await message.reply("خطا در ثبت نام. لطفاً دوباره امتحان کنید.")
                    return

                active = show_active_polls()
                user_classes = get_user_classes(uid)

                for pid, class_name, poll_type in active:
                    if class_name is None or class_name in user_classes:
                        await send_poll(client, uid, pid)

                del user_states[uid]

                await message.reply(
                    "نام شما ثبت شد. حالا می‌توانید در نظرسنجی شرکت کنید.",
                    reply_markup=member_help_keyboard(
                        "✉️ پیام به اونرها" if uid in settings.owners else "✉️ پیام به ادمین",
                        owner_controls=uid in settings.owners,
                    ),
                )
                return

            elif state == 'waiting_for_rename':
                await handle_rename_message(uid, text, message, user_states)
                return

            elif state == 'waiting_for_owner_message':
                await forward_owner_message(
                    uid, text, message, client, settings.owners, user_states)
                return

            elif state == 'waiting_for_bug_report':
                await forward_bug_report(
                    uid, text, message, client, settings.developers, user_states)
                return

            elif state in (
                    'send_message_target_type', 'send_message_id',
                    'send_message_text'):
                await handle_send_message_input(
                    uid, text, message, pending_actions, user_states,
                    settings.owners)
                return

            elif state == 'waiting_for_text':
                pending = pending_actions.get(uid, {})
                pid = pending.get('pid')
                q_id = pending.get('q_id')
                if pid and q_id:
                    resp_text = text.strip()
                    if not resp_text:
                        await message.reply("پاسخ نمی‌تواند خالی باشد.")
                        return  # stay in state
                    username = message.author.username or ""
                    db_name = get_user_name(
                        uid) or message.author.first_name or ""
                    try:
                        vote(pid, q_id, resp_text, uid, username, db_name)
                        await message.reply("با تشکر، پاسخ شما ثبت شد.")
                    except Exception as e:
                        print("vote error:", e)
                        await message.reply("خطا در ثبت پاسخ.")
                del user_states[uid]
                pending_actions.pop(uid, None)
                return

            elif state == 'poll_wizard_question':
                await handle_poll_question(uid, text, message,
                                           pending_actions, user_states)
                return

            elif state == 'poll_wizard_time':
                await handle_poll_schedule_time(uid, text, message,
                                                pending_actions, user_states)
                return

            elif state.startswith('get_money_'):
                await handle_get_money_message(uid, text, message,
                                               pending_actions, user_states,
                                               settings.owners)
                return

            elif state.startswith('poll_wizard_'):
                await message.reply("لطفاً مرحلهٔ فعلی ساخت نظرسنجی را با دکمه‌ها ادامه بده.")
                return

            elif uid in settings.admins:
                pending = pending_actions.get(uid, {})

        is_owner = uid in settings.owners
        is_admin = uid in settings.admins

        command = _command_name(text)
        if command and not _can_use_command(command, is_owner, is_admin):
            await message.reply("⛔ شما برای استفاده از این دستور دسترسی ندارید.")
            return

        if text == "help":
            if is_owner:
                await message.reply(
                    OWNER_HELP, reply_markup=member_help_keyboard(
                        "✉️ پیام به اونرها", owner_controls=True))
            elif is_admin:
                await message.reply(
                    ADMIN_HELP, reply_markup=member_help_keyboard(
                        "✉️ پیام به اونرها"))
            else:
                await handle_member_message(
                    uid, text, message, client, user_states, settings.owners,
                    settings.developers)
            return

        if command is None and text:
            await _notify_owners_of_unrecognized_message(
                uid, text, message, client, settings.owners)
            return

        if uid not in all_users or not get_user_name(uid):
            user_states[uid] = 'waiting_for_name'
            await message.reply(
                "برای ثبت نام و شرکت در نظرسنجی، لطفاً نامت را بفرست.")
            return

        if await handle_member_message(
                uid, text, message, client, user_states, settings.owners,
                settings.developers):
            return

        if text == "deactivate_invoice":
            await invoice_hadnler(uid, text, message, settings.owners)
            return

        if is_owner:
            if await handle_scheduled_polls_command(text, message):
                return

            if text == "roles":
                def format_people(ids):
                    return "\n".join(
                        f"• {get_user_name(person_id) or 'بدون نام'} (ID: {person_id})"
                        for person_id in sorted(ids)
                    ) or "• هیچ‌کس"

                await message.reply(
                    "👑 اونرها (تنظیم فقط از فایل .env):\n"
                    f"{format_people(settings.owners)}\n\n"
                    "🛡 ادمین‌ها (دسترسی محدود):\n"
                    f"{format_people(settings.admins)}\n\n"
                    "دستورها: /add_admin <شناسه> و /remove_admin <شناسه>"
                )
                return

            command_parts = text.split(maxsplit=1)
            if command_parts and command_parts[0] in ("add_admin", "remove_admin"):
                parts = text.split()
                command = parts[0]
                if len(parts) != 2:
                    await message.reply(f"فرمت: {command} <شناسه کاربر>")
                    return
                try:
                    target_id = int(parts[1])
                except ValueError:
                    await message.reply("شناسه کاربر باید عددی باشد.")
                    return
                if target_id in settings.owners:
                    await message.reply("اونر را نمی‌توان به فهرست ادمین‌ها اضافه یا از آن حذف کرد.")
                    return

                adding = command == "add_admin"
                if adding and target_id in settings.admins:
                    await message.reply("این کاربر از قبل ادمین است.")
                    return
                if not adding and target_id not in settings.admins:
                    await message.reply("این کاربر در فهرست ادمین‌ها نیست.")
                    return

                if adding:
                    settings.admins.add(target_id)
                else:
                    settings.admins.remove(target_id)
                try:
                    save_admins(settings.admins)
                except OSError:
                    if adding:
                        settings.admins.remove(target_id)
                    else:
                        settings.admins.add(target_id)
                    await message.reply("ذخیره تغییرات در فایل .env انجام نشد؛ دسترسی فایل را بررسی کنید.")
                    return
                action = "به فهرست ادمین‌ها اضافه شد" if adding else "از فهرست ادمین‌ها حذف شد"
                await message.reply(f"کاربر {target_id} {action}.")
                if adding:
                    notification = (
                        "✅ شما به‌عنوان ادمین ربات انتخاب شده‌اید.\n\n"
                        f"{ADMIN_HELP}"
                    )
                else:
                    notification = "ℹ️ دسترسی ادمین شما از ربات برداشته شد."
                try:
                    await client.send_message(
                        target_id, notification,
                        reply_markup=(member_help_keyboard(
                            "✉️ پیام به اونرها") if adding else member_help_keyboard()),
                    )
                except Exception as e:
                    print(f"خطا در اطلاع‌رسانی تغییر نقش به {target_id}: {e}")
                    await message.reply(
                        "تغییر نقش ذخیره شد، اما پیام خصوصی به کاربر نرسید. "
                        "از او بخواه ابتدا ربات را باز کند و /help را بفرستد."
                    )
                return

        if is_owner or is_admin:
            if is_admin and not is_owner:
                if text == "list_classes":
                    await class_hadnler(uid, text, message, pending_actions,
                                       user_states, settings.admins)
                    return
                elif text == "create_poll" or text.startswith("create_poll "):
                    await poll_hadnler(uid, text, message, pending_actions,
                                       user_states, text.split())
                    return

            if await class_hadnler(uid, text, message, pending_actions,
                                   user_states, settings.owners):
                return
            if await user_hadnler(uid, text, message, user_states):
                return
            if await invoice_hadnler(uid, text, message, settings.owners):
                return
            if await poll_hadnler(uid, text, message,
                                  pending_actions, user_states, aline):
                return
            if await payment_hadnler(uid, text, message,
                                     pending_actions, user_states, settings.owners):
                return

            if text == "report":
                try:
                    polls = show_active_polls()
                    if not polls:
                        await message.reply("📭 *هیچ نظرسنجی فعالی وجود ندارد.*")
                        return

                    report_parts = []

                    for pid, class_name, poll_type in polls:
                        class_name = class_name or 'همه'

                        poll_stats = get_stats(pid)
                        questions_list = get_questions(pid)

                        if not questions_list:
                            continue

                        poll_report = f"📊 *نظرسنجی #{pid}*\n"
                        poll_report += f"🏫 کلاس: {class_name}\n"
                        poll_report += f"🔧 نوع: {poll_type}\n"
                        poll_report += f"🆔 PID: {pid}\n"

                        for q_index, q_id, q_text in questions_list:
                            question_data = poll_stats.get(q_id, (0, None))
                            response_count, total_score = question_data

                            if poll_type == 'score':
                                if response_count > 0 and total_score is not None:
                                    average = total_score / response_count
                                    poll_report += f"*{q_index+1}. {q_text}*\n"
                                    poll_report += f"   میانگین: {average:.2f} از 10\n"
                                    poll_report += f"   تعداد پاسخ‌ها: {response_count}\n"
                                else:
                                    poll_report += f"*{q_index+1}. {q_text}*\n"
                                    poll_report += f"   ⚠️ هیچ پاسخی ثبت نشده\n"
                            else:
                                poll_report += f"*{q_index+1}. {q_text}*\n"
                                poll_report += f"   تعداد پاسخ‌ها: {response_count}\n"

                            poll_report += "\n"

                        report_parts.append(poll_report)

                    final_report = "📈 *گزارش نظرسنجی‌های فعال*\n"
                    final_report += f"📊 تعداد نظرسنجی‌های فعال: {len(polls)}\n"
                    final_report += "─" * 30 + "\n"

                    for i, part in enumerate(report_parts, 1):
                        final_report += part
                        if i < len(report_parts):
                            final_report += "─" * 30 + "\n"

                    if len(final_report) > 3800:
                        chunks = []
                        current_chunk = ""
                        lines = final_report.split('\n')

                        for line in lines:
                            if len(current_chunk + line + '\n') > 3800:
                                chunks.append(current_chunk)
                                current_chunk = line + '\n'
                            else:
                                current_chunk += line + '\n'

                        if current_chunk:
                            chunks.append(current_chunk)

                        for chunk in chunks:
                            await message.reply(chunk)
                            time.sleep(0.5)
                    else:
                        await message.reply(final_report)

                except Exception as e:
                    error_msg = f"خطا در تولید گزارش: {str(e)[:100]}"
                    print("report error:", e)
                    traceback.print_exc()
                    await message.reply(f"❌ {error_msg}")
                return

            if text == "export_votes":
                export_votes()
                file = "export_votes.xlsx"
                try:
                    await client.send_document(
                        chat_id=message.author.id,
                        document=open(file, "rb"),
                        caption="فایل خروجی تمام نظرسنجی ها",
                    )
                    await message.reply("خروجی نظرسنجی ها با موفقیت ارسال شد.")
                except Exception as e:
                    await message.reply(f"خطا در ارسال فایل: {e}")
                    print(f"Error sending document: {e}")

                return

        if await handle_member_message(
                uid, text, message, client, user_states, settings.owners,
                settings.developers):
            return

        await _notify_owners_of_unrecognized_message(
            uid, text, message, client, settings.owners)

    except Exception as e:
        print("msg_handler top-level error:", e)
        traceback.print_exc()
