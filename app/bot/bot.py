#!/usr/bin/env python3
from balethon import Client
import time
import traceback
import threading
import random
import datetime

from app.bot.config import get_settings
from app.bot.handlers.invoice_handlers import invoice_hadnler
from app.bot.handlers.payment_handlers import payment_hadnler
from app.bot.handlers.poll_handlers import poll_hadnler
from app.bot.handlers.user_handlers import user_hadnler
from app.db.cruds import *
from app.db.cruds import init_db
from app.services.patment import process_successful_payment, send_pay_to_class
from app.services.poll import activate_poll, send_poll
from app.bot.messages import *
from app.bot.handlers.class_handlers import class_hadnler

settings = get_settings()

client = Client(settings.bale_bot_token)

init_db()

# ---------- STATE ----------
try:
    users = set(get_users())
except:
    users = set()

user_states = {}
pending_actions = {}

with client:
    for admin in settings.admins:
        if admin in users:
            client.send_message(admin, "ربات روشن شد.")


# ---------- AUTOSTART ----------


def autostart_loop():
    while True:
        try:
            t = next_task()
            if t and t.get("t") and t["t"] <= time.time():
                print("autostart: activating poll", t["poll_id"])
                activate_poll(t["poll_id"])
                del_task(t["id"])
        except Exception as e:
            print("autostart error:", e)
            traceback.print_exc()
        time.sleep(10)

# ---------- CALLBACK QUERY ----------


@client.on_callback_query()
def on_callback_query(callback_query):
    print("Callback received! data:", callback_query.data)

    if callback_query.data.startswith("confirm_pay_"):
        target_uid = int(callback_query.data.split("_")[2])

        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        validation = pending_actions.get(target_uid, {})
        if not validation:
            callback_query.answer("اطلاعات یافت نشد!", show_alert=True)
            return

        callback_query.answer("در حال ارسال صورتحساب‌ها...")

        success, result_msg = send_pay_to_class(client, settings,
                                                validation['class_name'],
                                                validation['amount_rial'],
                                                validation['title'],
                                                validation['description']
                                                )

        client.send_message(target_uid, result_msg)

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(
            f"✅ **عملیات تکمیل شد**\n",
            reply_markup=None
        )
        return

    elif callback_query.data.startswith("cancel_pay_"):
        target_uid = int(callback_query.data.split("_")[2])

        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(
            "❌ **عملیات لغو شد**\nارسال صورتحساب‌ها کنسل شد.",
            reply_markup=None
        )
        callback_query.answer("عملیات لغو شد")
        return

    elif callback_query.data.startswith("confirm_poll_"):
        target_uid = int(callback_query.data.split("_")[2])

        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        pending = pending_actions.get(target_uid)
        if not pending or pending.get('kind') != 'poll':
            callback_query.answer(
                "اطلاعات نظرسنجی یافت نشد یا منقضی شده!", show_alert=True)
            return

        callback_query.answer("در حال ایجاد نظرسنجی...")

        poll_type = pending['poll_type']
        class_name = pending['class_name']
        ts = pending['ts']
        q_text = pending['q_text']

        try:
            pid = create_poll(poll_type, class_name)
            add_question(pid, 0, q_text)

            if ts is None:
                activate_poll(client, pid)
                target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
                result_msg = f"✅ نظرسنجی با موفقیت ایجاد و فعال شد.\n"
                result_msg += f"🔹 کلاس: {target}\n"
                result_msg += f"🔹 سوال: {q_text}"
            else:
                add_task(ts, pid)
                target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
                dt_str = datetime.datetime.fromtimestamp(
                    ts).strftime('%Y-%m-%d %H:%M:%S')
                result_msg = f"✅ نظرسنجی با موفقیت ایجاد و برای زمان {dt_str} زمان‌بندی شد.\n"
                result_msg += f"🔹 کلاس: {target}\n"
                result_msg += f"🔹 سوال: {q_text}"

            if target_uid in user_states:
                del user_states[target_uid]
            if target_uid in pending_actions:
                pending_actions.pop(target_uid)

            callback_query.message.edit_text(result_msg, reply_markup=None)

        except Exception as e:
            print("Error in confirm_poll:", e)
            traceback.print_exc()
            callback_query.answer("خطا در ایجاد نظرسنجی!", show_alert=True)
        return

    elif callback_query.data.startswith("cancel_poll_"):
        target_uid = int(callback_query.data.split("_")[2])

        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        if target_uid in user_states and user_states[target_uid] == 'confirm_poll':
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(
            "❌ **ایجاد نظرسنجی لغو شد**",
            reply_markup=None
        )
        callback_query.answer("عملیات لغو شد")
        return
    elif callback_query.data.startswith("confirm_delclass_"):
        target_uid = int(callback_query.data.split("_")[2])
        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        pending = pending_actions.get(target_uid)
        if not pending or pending.get('kind') != 'delete_class':
            callback_query.answer("اطلاعات یافت نشد!", show_alert=True)
            return

        class_name = pending['class_name']
        callback_query.answer("در حال حذف...")

        success, result_msg = delete_class(class_name)

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(result_msg, reply_markup=None)
        return

    elif callback_query.data.startswith("cancel_delclass_"):
        target_uid = int(callback_query.data.split("_")[2])
        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(
            "❌ عملیات حذف کلاس لغو شد.", reply_markup=None)
        callback_query.answer("عملیات لغو شد")
        return

    elif callback_query.data.startswith("confirm_sendmsg_"):
        target_uid = int(callback_query.data.split("_")[2])
        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        pending = pending_actions.get(target_uid)
        if not pending or pending.get('kind') != 'send_message':
            callback_query.answer(
                "اطلاعات یافت نشد یا منقضی شده!", show_alert=True)
            return

        callback_query.answer("در حال ارسال پیام...")

        class_name = pending['class_name']
        message_text = pending['message_text']
        user_ids = pending['user_ids']

        success_count = 0
        fail_count = 0
        fail_details = []

        for uid in user_ids:
            try:
                client.send_message(uid, message_text)
                success_count += 1
                time.sleep(0.3)
            except Exception as e:
                fail_count += 1
                user_name = get_user_name(uid) or f"کاربر {uid}"
                fail_details.append(f"{user_name}: {str(e)[:50]}")
                print(f"خطا در ارسال به {uid}: {e}")

        report = f"📨 *گزارش ارسال پیام به کلاس {class_name}*\n"
        report += f"👥 تعداد کاربران: {len(user_ids)}\n"
        report += f"✅ موفق: {success_count}\n"
        report += f"❌ ناموفق: {fail_count}\n"

        if fail_details:
            report += "\n⚠️ *خطاها:*\n"
            for detail in fail_details[:5]:
                report += f"• {detail}\n"
            if len(fail_details) > 5:
                report += f"• و {len(fail_details)-5} خطای دیگر..."

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(report, reply_markup=None)
        return

    elif callback_query.data.startswith("cancel_sendmsg_"):
        target_uid = int(callback_query.data.split("_")[2])
        if callback_query.author.id != target_uid:
            callback_query.answer(
                "این درخواست برای شما نیست!", show_alert=True)
            return

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text(
            "❌ ارسال پیام لغو شد.", reply_markup=None)
        callback_query.answer("عملیات لغو شد")
        return

    else:
        try:
            data = callback_query.data.split(":")
            if len(data) != 3:
                callback_query.answer("داده نامعتبر", show_alert=True)
                return

            pid = int(data[0])
            q_index = int(data[1])
            value = data[2]

            author = callback_query.author
            uid = author.id

            poll_type = get_poll_type(pid)
            if not poll_type:
                callback_query.answer("نظرسنجی منقضی شده", show_alert=True)
                return

            if not is_poll_active(pid):
                callback_query.answer(
                    "این نظرسنجی دیگر فعال نیست.", show_alert=True)
                return

            poll_class = get_poll_class(pid)
            if poll_class is not None:
                user_classes = get_user_classes(uid)
                if poll_class not in user_classes:
                    callback_query.answer(
                        "شما مجاز به پاسخ به این نظرسنجی نیستید.", show_alert=True)
                    del user_states[uid]
                    pending_actions.pop(uid, None)
                    return

            q_id = get_question_id(pid, q_index)
            if not q_id:
                callback_query.answer("سوال نامعتبر", show_alert=True)
                return

            username = author.username or ""
            db_name = get_user_name(uid) or author.first_name or ""

            if poll_type == 'score':
                vote(pid, q_id, value, uid, username, db_name)
                client.edit_message_text(
                    callback_query.chat_instance,
                    callback_query.message.id,
                    "با تشکر، نظر شما ثبت شد."
                )

            elif poll_type == 'text':
                if value != "text":
                    callback_query.answer("داده نامعتبر", show_alert=True)
                    return

                client.edit_message_text(
                    callback_query.chat_instance,
                    callback_query.message.id,
                    "لطفا پاسخ خود را ارسال کنید."
                )
                user_states[uid] = 'waiting_for_text'
                pending_actions[uid] = {'pid': pid, 'q_id': q_id}
        except Exception as e:
            print("callback error:", e)

# ---------- MESSAGE ----------


@client.on_message()
def on_message(message):
    try:
        if hasattr(message, 'successful_payment') and message.successful_payment:
            print("🔄 پرداخت از طریق on_message دریافت شد (پشتیبان)")
            process_successful_payment(client, settings, message)
            return

        uid = message.author.id
        text = (message.text or "").strip()
        parts = text.split('\n')
        aline = text.split()

        if uid in user_states:
            state = user_states[uid]
            if state == 'waiting_for_name':
                if not text:
                    message.reply("لطفاً نام خود را وارد کنید.")
                    return
                name = text.strip()
                if not name:
                    message.reply(
                        "نام نمی‌تواند خالی باشد. لطفاً نام خود را وارد کنید.")
                    return

                try:
                    add_user(uid, name)
                    users.add(uid)
                except Exception as e:
                    print("add_user DB error:", e)
                    message.reply("خطا در ثبت نام. لطفاً دوباره امتحان کنید.")
                    return

                active = show_active_polls()
                user_classes = get_user_classes(uid)

                for pid, class_name, poll_type in active:
                    if class_name is None or class_name in user_classes:
                        send_poll(client, uid, pid)

                del user_states[uid]

                message.reply(
                    "نام شما ثبت شد. حالا می‌توانید در نظرسنجی شرکت کنید.")
                return

            elif state == 'waiting_for_text':
                pending = pending_actions.get(uid, {})
                pid = pending.get('pid')
                q_id = pending.get('q_id')
                if pid and q_id:
                    resp_text = text.strip()
                    if not resp_text:
                        message.reply("پاسخ نمی‌تواند خالی باشد.")
                        return  # stay in state
                    username = message.author.username or ""
                    db_name = get_user_name(
                        uid) or message.author.first_name or ""
                    try:
                        vote(pid, q_id, resp_text, uid, username, db_name)
                        message.reply("با تشکر، پاسخ شما ثبت شد.")
                    except Exception as e:
                        print("vote error:", e)
                        message.reply("خطا در ثبت پاسخ.")
                del user_states[uid]
                pending_actions.pop(uid, None)
                return

            elif uid in settings.admins:
                pending = pending_actions.get(uid, {})

        if uid not in users:
            user_states[uid] = 'waiting_for_name'
            message.reply(
                f"شما کاربر جدیدی هستید. لطفاً نام خود را وارد کنید تا ثبت شوید.")
            return

        if uid in settings.admins:

            class_hadnler(uid, text, message, pending_actions,
                          user_states, settings.admins)
            user_hadnler(uid, text, message, user_states)
            invoice_hadnler(uid, text, message, settings.admins)
            poll_hadnler(uid, text, message,
                         pending_actions, user_states, aline)
            payment_hadnler(uid, text, message,
                            pending_actions, user_states, settings.admins)

            if text == "report":
                try:
                    polls = show_active_polls()
                    if not polls:
                        message.reply("📭 *هیچ نظرسنجی فعالی وجود ندارد.*")
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

                    try:
                        count = deactivate_old_polls()
                        final_report = f"{count} نظرسنجی گذشته حذف شد.\n"

                    except Exception as e:
                        final_report = "خطا در حذف نظرسنجی های گذشته:" + \
                            str(e) + "\n"

                    final_report += "📈 *گزارش نظرسنجی‌های فعال*\n"
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
                            message.reply(chunk)
                            time.sleep(0.5)
                    else:
                        message.reply(final_report)

                except Exception as e:
                    error_msg = f"خطا در تولید گزارش: {str(e)[:100]}"
                    print("report error:", e)
                    traceback.print_exc()
                    message.reply(f"❌ {error_msg}")
                return

        message.reply(get_user_name(uid)+" رو نمی‌شناسم!🫣")
        if not uid == 213614271:
            client.send_message(
                213614271, f"{get_user_name(uid)} این پیام رو داد:\n{text}")
        if not uid == 1351870827 and not uid == 213614271:
            client.send_message(
                1351870827, f"{get_user_name(uid)} این پیام رو داد:\n{text}")

    except Exception as e:
        print("msg_handler top-level error:", e)
        traceback.print_exc()

# --------- PRE CHECK OUT QUERY HANDLER -----------


@client.on_pre_checkout_query()
def handle_pre_checkout(client, pre_checkout_query):
    query_id = pre_checkout_query.id
    payload = pre_checkout_query.invoice_payload

    try:
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=True
        )
        print(f"✅ درخواست پرداخت برای کاربر {user_id} تایید شد.")

    except Exception as e:
        print(f"❌ خطا در ارسال پاسخ تایید: {e}")
        traceback.print_exc()
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message="خطای داخلی سرور در پردازش پرداخت."
        )


# ---------- READY ----------
t = threading.Thread(target=autostart_loop, daemon=True)
t.start()
print("autocheck started")
client.run()
