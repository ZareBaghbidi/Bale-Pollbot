import traceback
import datetime
from balethon.objects import InlineKeyboard

from app.bot.messages import CREATE_POLL_HELP
from app.db.cruds.classes import get_class_id_by_name
from app.db.cruds.polls import deactivate_old_polls, get_poll_type, show_all_polls
from app.db.cruds.questions import get_questions
from app.db.cruds.votes import get_responses
from app.services.poll import stop_poll_by_pid


def poll_hadnler(uid, text, message, pending_actions, user_states, aline):
    if text.startswith("create_poll"):
        if len(text) == len("create_poll"):
            message.reply(CREATE_POLL_HELP)
            return

        parts = text[len("create_poll"):].strip().split(maxsplit=3)
        if len(parts) != 4:
            message.reply("تعداد پارامترها اشتباه است. باید دقیقاً ۴ بخش باشد.\n"
                          "مثال: create_poll text all . نظرت درباره درس چیه؟")
            return

        poll_type, class_input, ts_input, q_text = parts

        poll_type = poll_type.lower()
        if poll_type not in ['score', 'text']:
            message.reply("نوع باید score یا text باشد.")
            return

        class_name = class_input.strip()
        class_id = get_class_id_by_name(class_name)
        if class_id is None:
            message.reply(
                f"کلاس '{class_name}' وجود ندارد. از list_classes استفاده کنید.")
            return

        if ts_input == '.':
            ts = None
        else:
            try:
                ts = int(ts_input)
            except ValueError:
                message.reply(
                    "timestamp باید عدد یونیکس باشد یا '.' برای شروع فوری.")
                return

        q_text = q_text.strip()
        if not q_text:
            message.reply("متن سوال نمی‌تواند خالی باشد.")
            return

        pending_actions[uid] = {
            'kind': 'poll',
            'poll_type': poll_type,
            'class_name': class_name,
            'ts': ts,
            'q_text': q_text
        }
        user_states[uid] = 'confirm_poll'

        summary = f"📊 *خلاصه نظرسنجی جدید*\n"
        summary += f"🔹 نوع: {'امتیازی' if poll_type == 'score' else 'متنی'}\n"
        summary += f"🔹 کلاس: {class_name}\n"
        if ts is None:
            summary += f"🔹 زمان: فوری\n"
        else:
            summary += f"🔹 زمان: {datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')} (timestamp: {ts})\n"
        summary += f"🔹 سوال: {q_text}\n"
        summary += "آیا از ایجاد این نظرسنجی اطمینان دارید؟"

        kb = InlineKeyboard(
            [("✅ تایید", f"confirm_poll_{uid}"),
                ("❌ لغو", f"cancel_poll_{uid}")]
        )

        message.reply(summary, reply_markup=kb)
        return

    if aline and aline[0] == "stop":
        if len(aline) < 1:
            message.reply("لطفا شماره pid را وارد کنید.")
            return
        try:
            pid = int(aline[1])
        except ValueError:
            message.reply("شماره نامعتبر.")
            return
        if stop_poll_by_pid(pid):
            message.reply("نظرسنجی متوقف شد.")
        else:
            message.reply("لطفا یک شمارهٔ معتبر وارد کنید.")
        return

    if text == "clear":
        try:
            count = deactivate_old_polls()
            if count > 0:
                message.reply(
                    f"✅ {count} نظرسنجی قدیمی (بیشتر از یک هفته) غیرفعال شدند.")
            else:
                message.reply(
                    "📭 هیچ نظرسنجی فعال قدیمی‌تر از یک هفته یافت نشد.")
        except Exception as e:
            print("clear error:", e)
            message.reply("❌ خطا در اجرای دستور clear.")
        return

    if text == "list_polls":
        try:
            polls = show_all_polls()
            if not polls:
                message.reply("هیچ نظرسنجی وجود ندارد.")
                return
            msg = "لیست نظرسنجی‌ها:\n"
            for pid, ptype, class_, active, created in polls:
                status = "فعال" if active else "غیرفعال"
                class_str = class_ if class_ else "همه"
                msg += f"- PID: {pid}, نوع: {ptype}, کلاس: {class_str}, وضعیت: {status}, ایجاد: {created}\n"
            if len(msg) > 3800:
                chunks = [msg[i:i+3800]
                          for i in range(0, len(msg), 3800)]
                for chunk in chunks:
                    message.reply(chunk)
            else:
                message.reply(msg)

        except Exception as e:
            print("list_polls error:", e)
            message.reply("خطا در لیست نظرسنجی‌ها.")
        return

    if text.startswith("view_responses"):
        parts = text.split()
        if len(parts) < 2:
            message.reply(
                "لطفا شماره PID را وارد کنید. مثال: view_responses 5")
            return
        try:
            pid = int(parts[1])
        except ValueError:
            message.reply("PID نامعتبر.")
            return

        poll_type = get_poll_type(pid)
        if not poll_type:
            message.reply("نظرسنجی یافت نشد.")
            return

        questions = get_questions(pid)
        if not questions:
            message.reply("این نظرسنجی سوالی ندارد.")
            return

        try:
            responses = get_responses(pid)
            if not responses:
                message.reply("هیچ پاسخی برای این نظرسنجی وجود ندارد.")
                return

            if poll_type == 'text':
                current_msg = f"📝 پاسخ‌های متنی نظرسنجی PID {pid}:\n"
                truncate = 300
            elif poll_type == 'score':
                current_msg = f"📊 امتیازات فردی نظرسنجی PID {pid}:\n"
                truncate = None  # No truncation for scores
            else:
                message.reply("نوع نظرسنجی نامعتبر.")
                return

            last_q_index = -1
            for q_index, q_text, value, name, username in responses:
                if q_index != last_q_index:
                    q_header = f"سوال {q_index + 1}: {q_text[:100]}\n"
                    if len(current_msg + q_header) > 3800:
                        message.reply(current_msg)
                        current_msg = q_header
                    else:
                        current_msg += q_header
                    last_q_index = q_index

                user_str = f"{name}" + \
                    (f" (@{username})" if username else "")
                disp_value = value[:truncate] if truncate else value
                resp_text = f"- {user_str}: {disp_value}\n"
                if len(current_msg + resp_text) > 3800:
                    message.reply(current_msg)
                    current_msg = resp_text
                else:
                    current_msg += resp_text

            if current_msg.strip():
                message.reply(current_msg)

        except Exception as e:
            print("view_responses error:", e)
            traceback.print_exc()
            message.reply("خطا در دریافت نتایج نظرسنجی.")
        return
