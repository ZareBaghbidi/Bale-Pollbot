import traceback
import datetime
import re
import jdatetime
from balethon.objects import InlineKeyboard

from app.bot.messages import CREATE_POLL_HELP
from app.db.cruds.polls import deactivate_old_polls, get_poll_type, show_all_polls
from app.db.cruds.questions import get_questions
from app.db.cruds.votes import get_responses
from app.services.poll import stop_poll_by_pid
from app.bot.poll_calendar import TEHRAN, fa_num, poll_type_keyboard
from app.db.cruds.tasks import get_scheduled_tasks, cancel_scheduled_task


async def _reply_long(message, text, limit=3800):
    if len(text) > limit:
        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
        for part in parts:
            await message.reply(part)
    else:
        await message.reply(text)


async def _handle_create_poll(uid, text, message, pending_actions, user_states):
    if text.strip() != "create_poll":
        await message.reply(CREATE_POLL_HELP)
        return

    pending_actions[uid] = {'kind': 'poll_wizard', 'step': 'type'}
    user_states[uid] = 'poll_wizard_type'
    await message.reply(
        "نوع نظرسنجی را انتخاب کن:",
        reply_markup=poll_type_keyboard(uid)
    )


async def handle_poll_question(uid, text, message, pending_actions, user_states):
    pending = pending_actions.get(uid, {})
    if (user_states.get(uid) != 'poll_wizard_question'
            or pending.get('kind') != 'poll_wizard'
            or pending.get('step') != 'question'):
        return False

    question = text.strip()
    if not question:
        await message.reply("متن سوال نمی‌تواند خالی باشد؛ دوباره بفرست.")
        return True

    pending['q_text'] = question
    pending['step'] = 'schedule'
    user_states[uid] = 'poll_wizard_schedule'
    from app.bot.poll_calendar import schedule_keyboard
    await message.reply(
        "زمان ارسال نظرسنجی را انتخاب کن.\n"
        "می‌توانی نظرسنجی را فوری بفرستی یا تاریخ شمسی و ساعت دقیق را از تقویم و دکمه‌ها تعیین کنی.",
        reply_markup=schedule_keyboard(uid)
    )
    return True


async def handle_poll_schedule_time(uid, text, message, pending_actions, user_states):
    pending = pending_actions.get(uid, {})
    if (user_states.get(uid) != 'poll_wizard_time'
            or pending.get('kind') != 'poll_wizard'
            or pending.get('step') != 'time'):
        return False

    normalized = text.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    match = re.fullmatch(r'\s*(\d{1,2})\s*:\s*(\d{1,2})\s*', normalized)
    if not match:
        await message.reply("زمان را به شکل ساعت:دقیقه بفرست؛ مثلاً `18:05`.")
        return True
    hour, minute = map(int, match.groups())
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        await message.reply("ساعت باید بین ۰ تا ۲۳ و دقیقه بین ۰ تا ۵۹ باشد؛ دوباره به شکل `h:m` بفرست.")
        return True

    try:
        jalali_date = jdatetime.date(
            pending['jalali_year'], pending['jalali_month'], pending['jalali_day'])
        local_dt = datetime.datetime.combine(
            jalali_date.togregorian(), datetime.time(hour, minute), tzinfo=TEHRAN)
    except (KeyError, ValueError, TypeError):
        await message.reply("تاریخ انتخاب‌شده معتبر نیست؛ فرایند ساخت نظرسنجی را از ابتدا شروع کن.")
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        return True

    if local_dt <= datetime.datetime.now(TEHRAN):
        await message.reply("این زمان گذشته است؛ ساعت و دقیقهٔ آینده را به شکل `h:m` بفرست.")
        return True

    ts = int(local_dt.timestamp())
    pending.update(kind='poll', ts=ts)
    user_states[uid] = 'confirm_poll'
    type_label = 'امتیازی (۱ تا ۱۰)' if pending['poll_type'] == 'score' else 'پاسخ متنی'
    jalali_str = (f"{fa_num(jalali_date.year)}/{fa_num(str(jalali_date.month).zfill(2))}/"
                  f"{fa_num(str(jalali_date.day).zfill(2))}")
    time_str = f"{fa_num(f'{hour:02d}')}:{fa_num(f'{minute:02d}')}"
    summary = (
        "📊 خلاصه نظرسنجی جدید\n"
        f"🔹 نوع: {type_label}\n"
        f"🔹 کلاس: {pending['class_name']}\n"
        f"🔹 زمان: {jalali_str} {time_str} (تهران)\n"
        f"🔹 سوال: {pending['q_text']}\n\n"
        "برای فعال‌شدن زمان‌بندی، ایجاد نظرسنجی را تأیید کن."
    )
    keyboard = InlineKeyboard(
        [("✅ تایید", f"confirm_poll_{uid}"), ("❌ لغو", f"cancel_poll_{uid}")])
    await message.reply(summary, reply_markup=keyboard)
    return True


async def handle_scheduled_polls_command(text, message):
    if text == 'scheduled_polls':
        tasks = get_scheduled_tasks()
        if not tasks:
            await message.reply("هیچ نظرسنجی زمان‌بندی‌شده‌ای وجود ندارد.")
            return True
        lines = ["🗓 نظرسنجی‌های زمان‌بندی‌شده (شناسه برای لغو):"]
        for task_id, poll_id, run_at, poll_type, class_name, question in tasks:
            jalali_day = jdatetime.date.fromgregorian(date=run_at.date())
            when = (f"{fa_num(jalali_day.year)}/{fa_num(str(jalali_day.month).zfill(2))}/"
                    f"{fa_num(str(jalali_day.day).zfill(2))} "
                    f"{fa_num(f'{run_at.hour:02d}')}:{fa_num(f'{run_at.minute:02d}')}")
            lines.append(
                f"\nشناسه زمان‌بندی: {task_id} | نظرسنجی: {poll_id}\n"
                f"زمان: {when} | کلاس: {class_name or 'همه'} | نوع: {poll_type}\n"
                f"سؤال: {question or '—'}")
        await _reply_long(message, "\n".join(lines))
        return True

    if text.startswith('cancel_scheduled'):
        parts = text.split()
        if len(parts) != 2 or parts[0] != 'cancel_scheduled':
            await message.reply("فرمت دستور: `cancel_scheduled <شناسه‌زمان‌بندی>`؛ شناسه را از `scheduled_polls` بردار.")
            return True
        try:
            task_id = int(parts[1])
        except ValueError:
            await message.reply("شناسهٔ زمان‌بندی باید عدد باشد.")
            return True
        poll_id = cancel_scheduled_task(task_id)
        if poll_id is None:
            await message.reply("این زمان‌بندی پیدا نشد؛ فهرست را با `scheduled_polls` تازه کن.")
        else:
            await message.reply(f"زمان‌بندی {task_id} لغو شد و نظرسنجیِ منتشرنشدهٔ {poll_id} حذف شد.")
        return True
    return False


async def _handle_stop_poll(aline, message):
    if len(aline) < 2:
        await message.reply("لطفا شماره نظرسنجی را وارد کنید.")
        return
    try:
        pid = int(aline[1])
    except ValueError:
        await message.reply("شماره نامعتبر.")
        return
    if await stop_poll_by_pid(pid):
        await message.reply("نظرسنجی متوقف شد.")
    else:
        await message.reply("لطفا یک شمارهٔ معتبر وارد کنید.")
    return


async def _handle_clear(message):
    try:
        count = deactivate_old_polls()
        if count > 0:
            await message.reply(
                f"✅ {count} نظرسنجی قدیمی (بیشتر از یک هفته) غیرفعال شدند.")
        else:
            await message.reply(
                "📭 هیچ نظرسنجی فعال قدیمی‌تر از یک هفته یافت نشد.")
    except Exception as e:
        print("clear error:", e)
        await message.reply("❌ خطا در اجرای دستور clear.")
    return


async def _handle_list_polls(message):
    try:
        polls = show_all_polls()
        if not polls:
            await message.reply("هیچ نظرسنجی وجود ندارد.")
            return
        msg = "لیست نظرسنجی‌ها:\n"
        for pid, ptype, class_, active, created in polls:
            status = "فعال" if active else "غیرفعال"
            class_str = class_ if class_ else "همه"
            msg += f"- PID: {pid}, نوع: {ptype}, کلاس: {class_str}, وضعیت: {status}, ایجاد: {created}\n"

        await _reply_long(message, msg)

    except Exception as e:
        print("list_polls error:", e)
        await message.reply("خطا در لیست نظرسنجی‌ها.")
    return


async def _handle_view_responses(text, message):
    parts = text.split()
    if len(parts) < 2:
        await message.reply(
            "لطفا شماره PID را وارد کنید. مثال: view_responses 5")
        return
    try:
        pid = int(parts[1])
    except ValueError:
        await message.reply("PID نامعتبر.")
        return

    poll_type = get_poll_type(pid)
    if not poll_type:
        await message.reply("نظرسنجی یافت نشد.")
        return

    questions = get_questions(pid)
    if not questions:
        await message.reply("این نظرسنجی سوالی ندارد.")
        return

    try:
        responses = get_responses(pid)
        if not responses:
            await message.reply("هیچ پاسخی برای این نظرسنجی وجود ندارد.")
            return

        if poll_type == 'text':
            current_msg = f"📝 پاسخ‌های متنی نظرسنجی PID {pid}:\n"
            truncate = 300
        elif poll_type == 'score':
            current_msg = f"📊 امتیازات فردی نظرسنجی PID {pid}:\n"
            truncate = None  # No truncation for scores
        else:
            await message.reply("نوع نظرسنجی نامعتبر.")
            return

        last_q_index = -1
        for q_index, q_text, value, name, username in responses:
            if q_index != last_q_index:
                q_header = f"سوال {q_index + 1}: {q_text[:100]}\n"
                if len(current_msg + q_header) > 3800:
                    await message.reply(current_msg)
                    current_msg = q_header
                else:
                    current_msg += q_header
                last_q_index = q_index

            user_str = f"{name}" + \
                (f" (@{username})" if username else "")
            disp_value = value[:truncate] if truncate else value
            resp_text = f"- {user_str}: {disp_value}\n"
            if len(current_msg + resp_text) > 3800:
                await message.reply(current_msg)
                current_msg = resp_text
            else:
                current_msg += resp_text

        if current_msg.strip():
            await message.reply(current_msg)

    except Exception as e:
        print("view_responses error:", e)
        traceback.print_exc()
        await message.reply("خطا در دریافت نتایج نظرسنجی.")
    return


async def poll_hadnler(uid, text, message, pending_actions, user_states, aline):
    if text == "create_poll":
        await _handle_create_poll(uid, text, message, pending_actions, user_states)
        return True

    if text.startswith("create_poll "):
        await message.reply(CREATE_POLL_HELP)
        return True

    if (aline and aline[0] == "stop"):
        await _handle_stop_poll(aline, message)
        return True

    if text == "clear":
        await _handle_clear(message)
        return True

    if text == "list_polls":
        await _handle_list_polls(message)
        return True

    if text.startswith("view_responses"):
        await _handle_view_responses(text, message)
        return True

    return False
