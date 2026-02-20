#!/usr/bin/env python3
from balethon import Client
from balethon.objects import InlineKeyboard, LabeledPrice
from balethon.conditions import successful_payment
from balethon.event_handlers import PreCheckoutQueryHandler
import time, traceback, threading, random, datetime
from db import *
from db import stats as get_stats

# ---------- BOT ----------
with open("bot_id.txt") as f:
    client = Client(f.read().strip())

with open("pay_id.txt") as f:
    PROVIDER_TOKEN = f.read().strip()

with open("admins.txt") as f:
    admins = {int(x) for x in f.read().splitlines() if x}


# ---------- STATE ----------
try:
    users = set(get_users())
except:
    users = set()

user_states = {}
pending_actions = {}

with client:
    for admin in admins:
        if admin in users:
            client.send_message(admin, "ربات روشن شد.")

# ---------- SEND POLL ----------
def send_poll(uid, pid):
    poll_type = get_poll_type(pid)
    if not poll_type:
        return

    questions = get_questions(pid)

    for q_index, q_id, q_text in questions:
        if poll_type == 'score':
            kb = InlineKeyboard(
                [("1", f"{pid}:{q_index}:1"),
                 ("2", f"{pid}:{q_index}:2"),
                 ("3", f"{pid}:{q_index}:3"),
                 ("4", f"{pid}:{q_index}:4"),
                 ("5", f"{pid}:{q_index}:5")],
                [("6", f"{pid}:{q_index}:6"),
                 ("7", f"{pid}:{q_index}:7"),
                 ("8", f"{pid}:{q_index}:8"),
                 ("9", f"{pid}:{q_index}:9"),
                 ("10", f"{pid}:{q_index}:10")]
            )
        else:
            kb = InlineKeyboard(
                [("پاسخ دادن", f"{pid}:{q_index}:text")]
            )

        try:
            client.send_message(uid, q_text, reply_markup=kb)
        except Exception as e:
            print("send_poll error:", e)

# ---------- ACTIVATE POLL ----------
# ---------- ACTIVATE POLL ----------
def activate_poll(pid):
    try:
        c = conn()
        cur = c.cursor()
        cur.execute("UPDATE polls SET active=1 WHERE id=?", (pid,))
        c.commit()
        cur.close()
        c.close()
    except Exception as e:
        print("activate_poll DB error:", e)
        return

    class_name = get_poll_class(pid)
    if class_name is None:
        print(f"⚠️ کلاس '{class_name}' برای نظرسنجی {pid} یافت نشد.")
        return

    class_id = get_class_id_by_name(class_name)
    if not class_id:
        return
    users_to_send = get_users_in_class(class_id)

    for u in users_to_send:
        send_poll(u, pid)

    print("Poll activated PID:", pid)

# ---------- PAYMENT VALIDATION ----------
def validate_payment_input(amount_str, class_name, title, description):
    errors = []

    try:
        amount_toman = int(amount_str.strip())
        if amount_toman <= 0:
            errors.append("❌ مبلغ باید بزرگتر از صفر باشد")
        else:
            amount_rial = amount_toman * 10
    except ValueError:
        errors.append("❌ مبلغ باید یک عدد معتبر باشد (مثال: 5000)")
        amount_rial = None

    class_id = get_class_id_by_name(class_name.strip())
    if class_id is None:
        errors.append(f"❌ کلاس '{class_name}' یافت نشد")
        users_count = 0
    else:
        users_in_class = get_users_in_class(class_id)
        users_count = len(users_in_class)
        if users_count == 0:
            errors.append(f"❌ هیچ کاربری در کلاس '{class_name}' وجود ندارد")

    title = title.strip()
    if not title:
        errors.append("❌ عنوان نمی‌تواند خالی باشد")
    elif len(title) > 32:
        errors.append("❌ عنوان نباید بیشتر از 32 کاراکتر باشد")

    description = description.strip()
    if not description:
        errors.append("❌ توضیحات نمی‌تواند خالی باشد")
    elif len(description) > 255:
        errors.append("❌ توضیحات نباید بیشتر از 255 کاراکتر باشد")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'amount_rial': amount_rial,
        'class_id': class_id,
        'class_name': class_name.strip(),
        'title': title,
        'description': description,
        'users_count': users_count
    }
# ---------- SEND PAY ------------
def send_pay_to_class(class_name, amount_rial, title, description):
    try:
        class_id = get_class_id_by_name(class_name)
        if class_id is None:
            return False, f"کلاس '{class_name}' یافت نشد."

        users_in_class = get_users_in_class(class_id)
        if not users_in_class:
            return False, f"هیچ کاربری در کلاس '{class_name}' وجود ندارد."

        success_count = 0
        fail_count = 0
        fail_details = []

        for uid in users_in_class:
            try:
                payload = f"class_{class_name}_user_{uid}_time_{int(time.time())}"

                save_invoice(
                    user_id=uid,
                    class_name=class_name,
                    amount=amount_rial,
                    title=title,
                    description=description,
                    payload=payload,
                    provider_token=PROVIDER_TOKEN
                )

                client.send_invoice(
                    chat_id= uid,
                    title= title,
                    description= description,
                    payload= payload,
                    provider_token= PROVIDER_TOKEN,
                    prices=[LabeledPrice(label=title, amount=amount_rial)],
                    need_name=True,
                    need_phone_number=True
                )
                success_count += 1

                time.sleep(0.3)

            except Exception as e:
                fail_count += 1
                user_name = get_user_name(uid) or f"کاربر {uid}"
                fail_details.append(f"{user_name}: {str(e)[:50]}")
                print(f"خطا در ارسال به {uid}: {e}")

        result_msg = f"📊 **نتیجه ارسال صورتحساب:**\n"
        result_msg += f"🎯 کلاس: {class_name}\n"
        result_msg += f"👥 تعداد کاربران: {len(users_in_class)}\n"
        result_msg += f"💰 مبلغ هر صورتحساب: {amount_rial // 10:,} تومان\n"
        result_msg += f"✅ موفق: {success_count} کاربر\n"
        result_msg += f"❌ ناموفق: {fail_count} کاربر\n"

        if fail_details:
            result_msg += "**جزئیات خطاها:**\n"
            for detail in fail_details[:3]:
                result_msg += f"• {detail}\n"
            if len(fail_details) > 3:
                result_msg += f"• و {len(fail_details) - 3} خطای دیگر...\n"

        return True, result_msg

    except Exception as e:
        error_msg = f"❌ خطای سیستمی: {str(e)[:100]}"
        print(f"خطا در send_pay_to_class: {e}")
        return False, error_msg

# ---------- STOP POLL ----------
def stop_poll_by_pid(pid):
    try:
        stop_poll(pid)
        print("Poll stopped:", pid)
        return True
    except Exception as e:
        print("Stop error:", e)
        return False

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

# ---------- PAYMENT HANDLER ----------
def process_successful_payment(client, message):
    try:
        uid = message.author.id
        payment = message.successful_payment

        print(f"🎉 پرداخت موفق از کاربر {uid}")
        print(f"   مبلغ: {payment.total_amount} ریال")
        print(f"   شناسه: {payment.invoice_payload}")

        order_info = payment.order_info if hasattr(payment, 'order_info') else None
        name = order_info.name if order_info and hasattr(order_info, 'name') else None
        phone = order_info.phone_number if order_info and hasattr(order_info, 'phone_number') else None
        email = order_info.email if order_info and hasattr(order_info, 'email') else None

        payment_id = save_payment(
            user_id=uid,
            amount=payment.total_amount,
            payload=payment.invoice_payload,
            name=name,
            phone=phone,
            email=email,
            telegram_charge_id=payment.telegram_payment_charge_id,
            provider_charge_id=payment.provider_payment_charge_id,
            status='completed'
        )

        print(f"💾 پرداخت با ID {payment_id} ذخیره شد")

        invoice_updated = update_invoice_status(payment.invoice_payload, 'paid', payment_id)
        print(f"📄 وضعیت صورتحساب بروزرسانی شد: {invoice_updated}")

        invoice_info = get_invoice_by_payload(payment.invoice_payload)

        user_msg = f"""✅ **پرداخت شما با موفقیت ثبت شد!**
💰 مبلغ: {payment.total_amount//10:,} تومان
🆔 شماره پیگیری: {payment.telegram_payment_charge_id}
📅 زمان: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
"""

        if invoice_info:
            user_msg += f"""
📝 عنوان: {invoice_info.get('title', '')}
🏫 کلاس: {invoice_info.get('class_name', '')}
"""

        if name:
            user_msg += f"👤 نام: {name}\n"
        if phone:
            user_msg += f"📞 تلفن: {phone}\n"

        user_msg += "\nبا تشکر از پرداخت شما! 🙏"

        message.reply(user_msg)

        user_name = get_user_name(uid) or message.author.first_name or f"کاربر {uid}"
        admin_msg = f"""💰 **پرداخت جدید ثبت شد**

👤 کاربر: {user_name} (آیدی: {uid})
💳 مبلغ: {payment.total_amount//10:,} تومان
🆔 شماره پیگیری: {payment.telegram_payment_charge_id}
📝 Payload: {payment.invoice_payload}
📅 زمان: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}
"""

        if invoice_info:
            admin_msg += f"🏫 کلاس: {invoice_info.get('class_name', 'نامشخص')}\n"
            admin_msg += f"📋 عنوان: {invoice_info.get('title', 'نامشخص')}\n"

        for admin_id in admins:
            try:
                client.send_message(admin_id, admin_msg)
                print(f"📤 پیام پرداخت به ادمین {admin_id} ارسال شد")
            except Exception as e:
                print(f"❌ خطا در ارسال به ادمین {admin_id}: {e}")

        return True

    except Exception as e:
        print(f"❌ خطا در پردازش پرداخت: {e}")
        traceback.print_exc()
        return False

# ---------- CALLBACK QUERY ----------
@client.on_callback_query()
def on_callback_query(callback_query):
    print("Callback received! data:", callback_query.data)

    if callback_query.data.startswith("confirm_pay_"):
        target_uid = int(callback_query.data.split("_")[2])

        if callback_query.author.id != target_uid:
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
            return

        validation = pending_actions.get(target_uid, {})
        if not validation:
            callback_query.answer("اطلاعات یافت نشد!", show_alert=True)
            return

        callback_query.answer("در حال ارسال صورتحساب‌ها...")

        success, result_msg = send_pay_to_class(
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
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
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
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
            return

        pending = pending_actions.get(target_uid)
        if not pending or pending.get('kind') != 'poll':
            callback_query.answer("اطلاعات نظرسنجی یافت نشد یا منقضی شده!", show_alert=True)
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
                activate_poll(pid)
                target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
                result_msg = f"✅ نظرسنجی با موفقیت ایجاد و فعال شد.\n"
                result_msg += f"🔹 کلاس: {target}\n"
                result_msg += f"🔹 سوال: {q_text}"
            else:
                add_task(ts, pid)
                target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
                dt_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
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
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
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
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
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
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
            return

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text("❌ عملیات حذف کلاس لغو شد.", reply_markup=None)
        callback_query.answer("عملیات لغو شد")
        return

    elif callback_query.data.startswith("confirm_sendmsg_"):
        target_uid = int(callback_query.data.split("_")[2])
        if callback_query.author.id != target_uid:
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
            return

        pending = pending_actions.get(target_uid)
        if not pending or pending.get('kind') != 'send_message':
            callback_query.answer("اطلاعات یافت نشد یا منقضی شده!", show_alert=True)
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
            callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
            return

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        callback_query.message.edit_text("❌ ارسال پیام لغو شد.", reply_markup=None)
        callback_query.answer("عملیات لغو شد")
        return

    else :
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
                callback_query.answer("این نظرسنجی دیگر فعال نیست.", show_alert=True)
                return

            poll_class = get_poll_class(pid)
            if poll_class is not None:
                user_classes = get_user_classes(uid)
                if poll_class not in user_classes:
                    callback_query.answer("شما مجاز به پاسخ به این نظرسنجی نیستید.", show_alert=True)
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
            process_successful_payment(client, message)
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
                    message.reply("نام نمی‌تواند خالی باشد. لطفاً نام خود را وارد کنید.")
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
                        send_poll(uid, pid)

                del user_states[uid]

                message.reply("نام شما ثبت شد. حالا می‌توانید در نظرسنجی شرکت کنید.")
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
                    db_name = get_user_name(uid) or message.author.first_name or ""
                    try:
                        vote(pid, q_id, resp_text, uid, username, db_name)
                        message.reply("با تشکر، پاسخ شما ثبت شد.")
                    except Exception as e:
                        print("vote error:", e)
                        message.reply("خطا در ثبت پاسخ.")
                del user_states[uid]
                pending_actions.pop(uid, None)
                return

            elif uid in admins:
                pending = pending_actions.get(uid, {})

        if uid not in users:
            user_states[uid] = 'waiting_for_name'
            message.reply("شما کاربر جدیدی هستید. لطفاً نام خود را وارد کنید تا ثبت شوید.")
            return

        if uid in admins:
            if text.startswith("send_message"):
                parts = text.split('\n', 1)
                first_line = parts[0].strip()
                if len(parts) < 2 or not parts[1].strip():
                    message.reply(
                        "❌ *فرمت صحیح:*\n"
                        "`send_message <نام کلاس>`\n"
                        "`<متن پیام (می‌تواند چند خط باشد)>`\n\n"
                        "مثال:\n"
                        "send_message 05\n"
                        "سلام بر کلاس ۰۵\nجلسه فردا ساعت ۱۰"
                    )
                    return

                try:
                    _, class_name = first_line.split(maxsplit=1)
                except ValueError:
                    message.reply("❌ لطفاً نام کلاس را وارد کنید.\nمثال: send_message 05")
                    return

                class_name = class_name.strip()
                message_text = parts[1].strip()

                class_id = get_class_id_by_name(class_name)
                if class_id is None:
                    message.reply(f"❌ کلاس '{class_name}' یافت نشد.")
                    return

                user_ids = get_users_in_class(class_id)
                if not user_ids:
                    message.reply(f"📭 هیچ کاربری در کلاس '{class_name}' وجود ندارد.")
                    return

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
                    [("✅ بله، ارسال شود", f"confirm_sendmsg_{uid}"),
                     ("❌ خیر، لغو", f"cancel_sendmsg_{uid}")]
                )
                message.reply(summary, reply_markup=kb)
                return

            if text.startswith("delete_class"):
                parts = text.split()
                if len(parts) != 2:
                    message.reply("📝 *فرمت:*\n`delete_class <نام کلاس>`\nمثال: delete_class 05")
                    return
                class_name = parts[1].strip()

                class_id = get_class_id_by_name(class_name)
                if not class_id:
                    message.reply(f"❌ کلاس '{class_name}' وجود ندارد.")
                    return

                pending_actions[uid] = {'kind': 'delete_class', 'class_name': class_name}
                user_states[uid] = 'confirm_delete_class'

                summary = f"⚠️ *آیا از حذف کلاس '{class_name}' اطمینان دارید؟*\n\n"
                summary += "🔸 تمام نظرسنجی‌ها و پاسخ‌های مرتبط با این کلاس\n"
                summary += "🔸 تمام صورتحساب‌های ارسال شده برای این کلاس\n"
                summary += "🔸 ارتباط کاربران با این کلاس\n\n"
                summary += "همگی **برای همیشه حذف** خواهند شد. این عمل قابل بازگشت نیست."

                kb = InlineKeyboard(
                    [("✅ بله، حذف شود", f"confirm_delclass_{uid}"), ("❌ خیر، لغو", f"cancel_delclass_{uid}")]
                )
                message.reply(summary, reply_markup=kb)
                return

            if text.startswith("remove_from_class"):
                parts = text.split()
                if len(parts) != 3:
                    message.reply(
                        "📝 *فرمت دستور:*\n"
                        "remove_from_class <نام کلاس> <آیدی کاربر>\n"
                        "*مثال:*\n"
                        "remove_from_class 05 123456789"
                    )
                    return

                class_name = parts[1].strip()
                try:
                    user_id = int(parts[2].strip())
                except ValueError:
                    message.reply("❌ آیدی کاربر باید یک عدد معتبر باشد.")
                    return

                success, result = remove_user_from_class(class_name, user_id)
                message.reply(result)
                return

            if text.startswith("create_poll"):
                if len(text) == len("create_poll"):
                    message.reply("فرمت: create_poll <type> <class> <ts> <question>\n"
                                  "type: score یا text\n"
                                  "class: نام کلاس\n"
                                  "ts: timestamp یونیکس یا . برای شروع فوری\n"
                                  "مثال: create_poll score 05 . ارزیابی امروز چطور بود؟")
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
                    message.reply(f"کلاس '{class_name}' وجود ندارد. از list_classes استفاده کنید.")
                    return

                if ts_input == '.':
                    ts = None
                else:
                    try:
                        ts = int(ts_input)
                    except ValueError:
                        message.reply("timestamp باید عدد یونیکس باشد یا '.' برای شروع فوری.")
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
                summary += f"🔹 نوع: {'امتیازی' if poll_type=='score' else 'متنی'}\n"
                summary += f"🔹 کلاس: {class_name}\n"
                if ts is None:
                    summary += f"🔹 زمان: فوری\n"
                else:
                    summary += f"🔹 زمان: {datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')} (timestamp: {ts})\n"
                summary += f"🔹 سوال: {q_text}\n"
                summary += "آیا از ایجاد این نظرسنجی اطمینان دارید؟"

                kb = InlineKeyboard(
                    [("✅ تایید", f"confirm_poll_{uid}"), ("❌ لغو", f"cancel_poll_{uid}")]
                )

                message.reply(summary, reply_markup=kb)
                return
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
                        final_report = "خطا در حذف نظرسنجی های گذشته:" + str(e) + "\n"

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

            if text.startswith("create_class"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    message.reply("لطفاً نام کلاس را وارد کنید.\nمثال: create_class 05")
                    return
                class_name = parts[1].strip()
                class_id = create_class(class_name)
                if class_id:
                    message.reply(f"کلاس '{class_name}' با موفقیت ایجاد شد.")
                else:
                    message.reply(f"کلاس '{class_name}' قبلاً وجود دارد.")
                return

            if text == "list_classes":
                classes = get_all_classes()
                if not classes:
                    message.reply("هیچ کلاسی وجود ندارد.")
                    return
                msg = "کلاس‌های موجود:\n"
                for cid, cname in classes:
                    count = len(get_users_in_class(cid))
                    msg += f"- {cname} (تعداد اعضا: {count})\n"
                message.reply(msg)
                return

            if text == "clear":
                try:
                    count = deactivate_old_polls()
                    if count > 0:
                        message.reply(f"✅ {count} نظرسنجی قدیمی (بیشتر از یک هفته) غیرفعال شدند.")
                    else:
                        message.reply("📭 هیچ نظرسنجی فعال قدیمی‌تر از یک هفته یافت نشد.")
                except Exception as e:
                    print("clear error:", e)
                    message.reply("❌ خطا در اجرای دستور clear.")
                return

            if text.startswith("class_users"):
                if uid not in admins:
                    message.reply("دسترسی denied.")
                    return

                parts = text.split()
                if len(parts) < 2:
                    message.reply("فرمت: class_users <نام کلاس>\nمثال: class_users 05")
                    return

                class_name = parts[1]
                users_list = get_class_users_with_names(class_name)

                if users_list is None:
                    message.reply(f"❌ کلاس '{class_name}' یافت نشد.")
                    return

                if not users_list:
                    message.reply(f"📭 هیچ کاربری در کلاس '{class_name}' وجود ندارد.")
                    return

                msg = f"👥 لیست کاربران کلاس '{class_name}':\n"
                for i, (user_id, name) in enumerate(users_list, 1):
                    msg += f"{i}. {name}\n"
                    msg += f"   آیدی: {user_id}\n"

                msg += f"\n📊 آمار: {len(users_list)} کاربر"

                if len(msg) > 3800:
                    chunks = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
                    for chunk in chunks:
                        message.reply(chunk)
                else:
                    message.reply(msg)
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
                        chunks = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
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
                    message.reply("لطفا شماره PID را وارد کنید. مثال: view_responses 5")
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

                        user_str = f"{name}" + (f" (@{username})" if username else "")
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

            if text == "users" or text == "list_users":
                all_users = get_all_users_with_names()
                if not all_users:
                    message.reply("هیچ کاربری ثبت نشده است.")
                    return

                msg = "👥 لیست تمام کاربران:\n"
                for idx, uid, name in all_users:
                    msg += f"{idx}. {name} (ID: {uid})\n"

                if len(msg) > 3800:
                    chunks = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
                    for chunk in chunks:
                        message.reply(chunk)
                else:
                    message.reply(msg)
                return

            if text == "add_users":
                all_users = get_all_users_with_names()
                if not all_users:
                    message.reply("هیچ کاربری ثبت نشده است.")
                    return

                msg = "لیست کاربران:\n"
                for numm, id, namme in all_users:
                    msg += f"{numm}. {namme} (ID: {id})\n"

                if len(msg) > 3800:
                    lines = msg.split('\n')
                    current = ""
                    for line in lines:
                        if len(current + line + '\n') > 3800:
                            message.reply(current)
                            current = line + '\n'
                        else:
                            current += line + '\n'
                    message.reply(current)
                else:
                    message.reply(msg)

                message.reply("حالا نام کلاس و شماره‌های کاربران را به این شکل وارد کنید:\nنام_کلاس\n1 3 5 8")
                user_states[uid] = 'waiting_add_users'
                return

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

                    if len(report) > 3800:
                        parts = [report[i:i+3800] for i in range(0, len(report), 3800)]
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
                    message.reply("فرمت: user_payments <آیدی کاربر>\nمثال: user_payments 213614271")
                    return

                try:
                    target_id = int(parts[1])

                    user_payments_list = get_user_payments(target_id, 20)
                    user_name = get_user_name(target_id) or target_id

                    if not user_payments_list:
                        message.reply(f"هیچ پرداختی برای کاربر {user_name} یافت نشد.")
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

                    message.reply(report)

                except Exception as e:
                    print(f"خطا در گزارش payments_filter: {e}")
                    message.reply("خطا در تولید گزارش.")
                return

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
                            last_sent = datetime.datetime.fromtimestamp(group['last_sent']).strftime('%m/%d %H:%M')

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
                        parts = [report[i:i+3800] for i in range(0, len(report), 3800)]
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

                    grouped_invoices = get_grouped_invoices(days=days, status=status, class_name=class_name, limit=30)

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
                            title = group['title'][:20] + '...' if len(group['title']) > 20 else group['title']
                            amount = group['amount']
                            total_count = group['total_count']
                            paid_count = group['paid_count']
                            last_sent = datetime.datetime.fromtimestamp(group['last_sent']).strftime('%m/%d')

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

            if text.startswith("invoices_class"):
                if uid not in admins:
                    message.reply("دسترسی denied.")
                    return

                parts = text.split()
                if len(parts) < 2:
                    message.reply("فرمت: invoices_class <نام کلاس>\nمثال: invoices_class 05")
                    return

                class_name = parts[1]

                try:
                    class_invoices = get_all_invoices(class_name=class_name, limit=50)

                    if not class_invoices:
                        message.reply(f"هیچ صورتحسابی برای کلاس '{class_name}' یافت نشد.")
                        return

                    class_summary = get_class_invoice_summary(class_name)
                    summary = class_summary[0] if class_summary else {}

                    report = f"🏫 *صورتحساب‌های کلاس: {class_name}*\n"
                    if summary:
                        report += f"📊 *آمار کلاس:*\n"
                        report += f"• کل صورتحساب‌ها: {summary['total_invoices']}\n"
                        report += f"• پرداخت شده: {summary['paid_count']}\n"
                        report += f"• مبلغ پرداخت شده: {summary['paid_amount']//10:,} تومان\n"
                        report += f"• تعداد کاربران: {summary['total_users']}\n"
                        report += f"• نرخ پرداخت: {round(summary['paid_count']/summary['total_invoices']*100, 1) if summary['total_invoices'] > 0 else 0}%\n"

                    user_status = {}
                    for invoice in class_invoices:
                        user_id = invoice['user_id']
                        if user_id not in user_status:
                            user_status[user_id] = {'name': invoice.get('user_name'), 'total': 0, 'paid': 0}
                        user_status[user_id]['total'] += 1
                        if invoice['status'] == 'paid':
                            user_status[user_id]['paid'] += 1

                    report += f"👥 *وضعیت کاربران:*\n"
                    for user_id, stats in list(user_status.items())[:15]:
                        status_icon = "✅" if stats['paid'] > 0 else "📤"
                        report += f"• {status_icon} {stats['name'] or user_id}: {stats['paid']}/{stats['total']}\n"

                    if len(user_status) > 15:
                        report += f"• و {len(user_status) - 15} کاربر دیگر...\n"

                    unpaid_invoices = [inv for inv in class_invoices if inv['status'] != 'paid'][:10]
                    if unpaid_invoices:
                        report += f"\n📋 *پرداخت نشده‌ها (10 مورد اول):*\n"
                        for invoice in unpaid_invoices[:10]:
                            user_name = invoice.get('user_name') or f"ID: {invoice['user_id']}"
                            sent_time = datetime.datetime.fromtimestamp(invoice['sent_at']).strftime('%m/%d')
                            report += f"• {user_name} | {invoice['amount']//10:,} تومان | {sent_time}\n"

                    if len(report) > 3800:
                        parts = [report[i:i+3800] for i in range(0, len(report), 3800)]
                        for part in parts:
                            message.reply(part)
                    else:
                        message.reply(report)

                except Exception as e:
                    print(f"خطا در invoices_class: {e}")
                    message.reply("خطا در دریافت اطلاعات کلاس")
                return

            if text == "invoices_unpaid":
                if uid not in admins:
                    message.reply("دسترسی denied.")
                    return

                try:
                    unpaid_invoices = get_unpaid_invoices(days=30)

                    if not unpaid_invoices:
                        message.reply("✅ *هیچ صورتحساب پرداخت نشده‌ای در ۳۰ روز گذشته وجود ندارد.*")
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
                            user_name = invoice.get('user_name') or f"ID: {invoice['user_id']}"
                            sent_time = datetime.datetime.fromtimestamp(invoice['sent_at']).strftime('%m/%d')
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
                            paid_rate = round(summary['paid_count']/summary['total_invoices']*100, 1) if summary['total_invoices'] > 0 else 0
                            avg_amount = summary['paid_amount']//summary['paid_count']//10 if summary['paid_count'] > 0 else 0

                            report += f"• {class_name}: {summary['paid_count']}/{summary['total_invoices']} ({paid_rate}%) | "
                            report += f"💰 {avg_amount:,} تومان | 👥 {summary['total_users']} کاربر\n"

                        if len(class_summaries) > 10:
                            report += f"• و {len(class_summaries) - 10} کلاس دیگر...\n"

                    daily_invoices = get_all_invoices(days=7)
                    if daily_invoices:
                        days_dict = {}
                        for invoice in daily_invoices:
                            day = datetime.datetime.fromtimestamp(invoice['sent_at']).strftime('%Y-%m-%d')
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

            if text.startswith("get_money"):
                if uid not in admins:
                    message.reply("شما دسترسی به این دستور را ندارید.")
                    return

                if uid in user_states and user_states[uid] == 'confirm_payment':
                    message.reply("شما قبلاً درخواست ارسال صورتحساب دارید. لطفاً ابتدا آن را تکمیل یا لغو کنید.")
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

                validation = validate_payment_input(amount_str, class_name, title, description)

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
                    [("✅ تایید و ارسال", f"confirm_pay_{uid}"), ("❌ لغو", f"cancel_pay_{uid}")]
                )

                message.reply(summary, reply_markup=kb)
                return

            if uid in user_states and user_states[uid] == 'waiting_add_users':
                lines = text.strip().split('\n')
                if len(lines) < 2:
                    message.reply("فرمت نادرست. باید نام کلاس و سپس شماره‌ها باشد.")
                    del user_states[uid]
                    return

                class_name = lines[0].strip()
                numbers_str = ' '.join(lines[1:]).strip()
                try:
                    numbers = [int(x) for x in numbers_str.split()]
                except:
                    message.reply("شماره‌ها نامعتبر هستند.")
                    del user_states[uid]
                    return

                class_id = get_class_id_by_name(class_name)
                if not class_id:
                    message.reply(f"کلاس '{class_name}' وجود ندارد.")
                    del user_states[uid]
                    return

                all_users = get_all_users_with_names()
                valid_uids = []
                for num in numbers:
                    if 1 <= num <= len(all_users):
                        valid_uids.append(all_users[num-1][1])
                    else:
                        message.reply(f"شماره {num} نامعتبر است.")

                if valid_uids:
                    add_users_to_class(class_id, valid_uids)
                    message.reply(f"{len(valid_uids)} کاربر به کلاس '{class_name}' اضافه شد.")
                else:
                    message.reply("هیچ کاربر معتبری انتخاب نشد.")

                del user_states[uid]
                return

        message.reply(get_user_name(uid)+" رو نمی‌شناسم!🫣")
        if not uid == 213614271:
            client.send_message(213614271, f"{get_user_name(uid)} این پیام رو داد:\n{text}")
        if not uid == 1351870827 and not uid == 213614271:
            client.send_message(1351870827, f"{get_user_name(uid)} این پیام رو داد:\n{text}")

    except Exception as e:
        print("msg_handler top-level error:", e)
        traceback.print_exc()

#--------- PRE CHECK OUT QUERY HANDLER -----------
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
