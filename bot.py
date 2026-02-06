#!/usr/bin/env python3
from balethon import Client
from balethon.objects import InlineKeyboard, LabeledPrice
from balethon.conditions import successful_payment
from balethon.event_handlers import PreCheckoutQueryHandler
import time, traceback, threading, random
from db import *

# ---------- BOT ----------
with open("bot_id.txt") as f:
    client = Client(f.read().strip())

PROVIDER_TOKEN = "WALLET-wmwVRbPeNx9fihMk"
admins = {213614271, 1351870827}

# ---------- STATE ----------
try:
    users = set(get_users())
except Exception as e:
    print("DB get_users error:", e)
    users = set()

active_polls = {}     # poll_index -> poll_id
poll_classes = {}     # poll_index -> class
poll_types = {}       # poll_index -> type ('score' or 'text')
poll_counter = 0

user_states = {}      # (uid -> state)
pending_actions = {}  # uid -> dict of temporary info for actions

polls = show_active_polls()
for pid, class_, poll_type in polls:
    active_polls[poll_counter] = pid
    poll_classes[poll_counter] = class_
    poll_types[poll_counter] = poll_type
    poll_counter += 1

with client:
    for admin in admins:
        if admin in users:
            client.send_message(admin, "ربات روشن شد.")

# ---------- SEND POLL ----------
def send_poll(uid, idx):
    if idx not in active_polls:
        return
    pid = active_polls[idx]
    poll_type = poll_types[idx]
    questions = get_questions(pid)
    for q_index, q_id, q_text in questions:
        if poll_type == 'score':
            # Keyboard for score (1-10 in two rows)
            kb = InlineKeyboard(
                [("1", str(idx * 100 + q_index * 10 + 0)), ("2", str(idx * 100 + q_index * 10 + 1)), ("3", str(idx * 100 + q_index * 10 + 2)), ("4", str(idx * 100 + q_index * 10 + 3)), ("5", str(idx * 100 + q_index * 10 + 4))],
                [("6", str(idx * 100 + q_index * 10 + 5)), ("7", str(idx * 100 + q_index * 10 + 6)), ("8", str(idx * 100 + q_index * 10 + 7)), ("9", str(idx * 100 + q_index * 10 + 8)), ("10", str(idx * 100 + q_index * 10 + 9))]
            )
        elif poll_type == 'text':
            kb = InlineKeyboard(
                [("پاسخ دادن", str(idx * 100 + q_index * 10 + 0))]
            )
        try:
            client.send_message(uid, q_text, reply_markup=kb)
        except Exception as e:
            print(f"send_poll error to {uid}:", e)

# ---------- ACTIVATE POLL ----------
def activate_poll(pid):
    global poll_counter
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
    class_ = get_poll_class(pid)
    poll_type = get_poll_type(pid)
    poll_classes[poll_counter] = class_
    poll_types[poll_counter] = poll_type
    active_polls[poll_counter] = pid

    if class_ is None:
        users_to_send = list(users)
    else:
        class_id = get_class_id_by_name(class_)
        if class_id is None:
            print(f"Class {class_} not found!")
            return
        users_to_send = get_users_in_class(class_id)

    for u in users_to_send:
        send_poll(u, poll_counter)

    print("Poll activated (idx", poll_counter, "pid", pid, "class", class_, ")")
    poll_counter += 1

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

        result_msg = f"📊 **نتیجه ارسال صورتحساب:**\n\n"
        result_msg += f"🎯 کلاس: {class_name}\n"
        result_msg += f"👥 تعداد کاربران: {len(users_in_class)}\n"
        result_msg += f"💰 مبلغ هر صورتحساب: {amount_rial // 10:,} تومان\n"
        result_msg += f"✅ موفق: {success_count} کاربر\n"
        result_msg += f"❌ ناموفق: {fail_count} کاربر\n\n"

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
def stop_poll_idx(idx):
    pid = active_polls.pop(idx, None)
    if pid is None:
        print("stop_poll_idx: no such idx", idx)
        return False
    try:
        stop_poll(pid)
    except Exception as e:
        print("stop_poll (DB) error:", e)
    poll_classes.pop(idx, None)
    poll_types.pop(idx, None)
    print("poll stopped", idx)
    return True

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
            f"✅ **عملیات تکمیل شد**\n\n",
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
            "❌ **عملیات لغو شد**\n\nارسال صورتحساب‌ها کنسل شد.",
            reply_markup=None
        )
        callback_query.answer("عملیات لغو شد")
        return
    else :
        try:
            v = int(callback_query.data)
        except Exception:
            callback_query.answer("دادهٔ نادرست", show_alert=True)
            return

        idx = v // 100
        if idx not in active_polls:
            client.edit_message_text(callback_query.chat_instance, callback_query.message.id, "نظر سنجی منقضی شده است.")
            return

        pid = active_polls[idx]
        poll_type = poll_types[idx]
        q_index = (v % 100) // 10
        val = v % 10

        q_id = get_question_id(pid, q_index)
        if q_id is None:
            callback_query.answer("سوال نامعتبر", show_alert=True)
            return

        author = callback_query.author
        uid = author.id
        username = author.username or ""
        db_name = get_user_name(uid) or author.first_name or ""

        if poll_type == 'score':
            score = val + 1
            try:
                vote(pid, q_id, str(score), uid, username, db_name)
                client.edit_message_text(callback_query.chat_instance, callback_query.message.id, "با تشکر، نظر شما ثبت شد.")
            except Exception as e:
                print("vote error:", e)
                callback_query.answer("خطا در ثبت نظر.", show_alert=True)
        elif poll_type == 'text':
            if val != 0:
                callback_query.answer("دادهٔ نادرست", show_alert=True)
                return
            try:
                client.edit_message_text(callback_query.chat_instance, callback_query.message.id, "لطفا پاسخ خود را ارسال کنید.")
                user_states[uid] = 'waiting_for_text'
                pending_actions[uid] = {'pid': pid, 'q_id': q_id}
            except Exception as e:
                print("edit message error:", e)
                callback_query.answer("خطا.", show_alert=True)

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

                for idx in list(active_polls.keys()):
                    poll_class = poll_classes.get(idx)
                    if poll_class is None or poll_class in get_user_classes(uid):
                        send_poll(uid, idx)

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
            if text.startswith("create_poll"):
                if len(text) == len("create_poll"):
                    message.reply("فرمت: create_poll <type> <class> <ts> <question>\n"
                                  "type: score یا text\n"
                                  "class: نام کلاس یا all\n"
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

                class_name = None if class_input == 'all' else class_input.strip()
                if class_name:
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

                try:
                    pid = create_poll(poll_type, class_name)
                    add_question(pid, 0, q_text)  # question index 0

                    if ts is None:
                        activate_poll(pid)
                        target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
                        message.reply(f"نظرسنجی {target} شروع شد.\nسوال: {q_text}")
                    else:
                        add_task(ts, pid)
                        target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
                        message.reply(f"نظرسنجی {target} زمان‌بندی شد برای {ts}.\nسوال: {q_text}")

                except Exception as e:
                    print("create_poll one-shot error:", e)
                    traceback.print_exc()
                    message.reply("خطا در ایجاد نظرسنجی.")
                return

            if text == "report":
                try:
                    global stats
                    if not active_polls:
                        message.reply("📭 *هیچ نظرسنجی فعالی وجود ندارد.*")
                        return

                    report_parts = []

                    for idx, pid in active_polls.items():
                        poll_type = poll_types.get(idx, 'unknown')
                        class_name = poll_classes.get(idx, 'همه') or 'همه'

                        poll_stats = stats(pid)
                        questions_list = get_questions(pid)

                        if not questions_list:
                            continue

                        poll_report = f"📊 *نظرسنجی #{idx}*\n"
                        poll_report += f"🏫 کلاس: {class_name}\n"
                        poll_report += f"🔧 نوع: {poll_type}\n"
                        poll_report += f"🆔 PID: {pid}\n\n"

                        for q_index, q_id, q_text in questions_list:
                            question_data = poll_stats.get(q_id, (0, None))
                            response_count, total_score = question_data

                            if poll_type == 'score':
                                if response_count > 0 and total_score is not None:
                                    average = total_score / response_count
                                    poll_report += f"*{q_index+1}. {q_text}*\n"
                                    poll_report += f"   میانگین: {average:.2f} از ۱۰\n"
                                    poll_report += f"   تعداد پاسخ‌ها: {response_count}\n"
                                else:
                                    poll_report += f"*{q_index+1}. {q_text}*\n"
                                    poll_report += f"   ⚠️ هیچ پاسخی ثبت نشده\n"
                            else:
                                poll_report += f"*{q_index+1}. {q_text}*\n"
                                poll_report += f"   تعداد پاسخ‌ها: {response_count}\n"

                            poll_report += "\n"

                        report_parts.append(poll_report)

                    final_report = "📈 *گزارش نظرسنجی‌های فعال*\n\n"
                    final_report += f"📊 تعداد نظرسنجی‌های فعال: {len(active_polls)}\n"
                    final_report += "─" * 30 + "\n\n"

                    for i, part in enumerate(report_parts, 1):
                        final_report += part
                        if i < len(report_parts):
                            final_report += "─" * 30 + "\n\n"

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

            if parts and parts[0] == "stop":
                if len(parts) < 2:
                    message.reply("لطفا شماره idx را وارد کنید.")
                    return
                try:
                    idx = int(parts[1])
                except ValueError:
                    message.reply("شماره نامعتبر.")
                    return
                if stop_poll_idx(idx):
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

                msg = f"👥 لیست کاربران کلاس '{class_name}':\n\n"
                for i, (user_id, name) in enumerate(users_list, 1):
                    msg += f"{i}. {name}\n"
                    msg += f"   آیدی: {user_id}\n"

                # اضافه کردن آمار
                msg += f"\n📊 آمار: {len(users_list)} کاربر"

                # اگر پیام طولانی است، آن را به چند قسمت تقسیم کنیم
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
                        current_msg = f"📝 پاسخ‌های متنی نظرسنجی PID {pid}:\n\n"
                        truncate = 300
                    elif poll_type == 'score':
                        current_msg = f"📊 امتیازات فردی نظرسنجی PID {pid}:\n\n"
                        truncate = None  # No truncation for scores
                    else:
                        message.reply("نوع نظرسنجی نامعتبر.")
                        return

                    last_q_index = -1
                    for q_index, q_text, value, name, username in responses:
                        if q_index != last_q_index:
                            q_header = f"سوال {q_index + 1}: {q_text[:100]}\n\n"
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
                    stats = get_payments_stats()

                    recent_payments = get_recent_payments(10)

                    report = f"💳 *گزارش پرداخت‌ها*\n\n"
                    report += f"📊 آمار کلی:\n"
                    report += f"• تعداد پرداخت‌ها: {stats['count']}\n"
                    report += f"• مجموع مبالغ: {stats['total']//10:,} تومان\n"
                    report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n\n"

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
                    report += f"📊 تعداد تراکنش‌ها: {len(user_payments_list)}\n\n"

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

                    report = f"📊 *گزارش پرداخت‌ها ({days} روز گذشته)*\n\n"
                    report += f"فیلترها:\n"
                    report += f"• بازه زمانی: {days} روز\n"
                    if min_amount:
                        report += f"• حداقل مبلغ: {min_amount//10:,} تومان\n"
                    report += f"\n📈 آمار:\n"
                    report += f"• تعداد پرداخت‌ها: {stats['count']}\n"
                    report += f"• مجموع مبالغ: {stats['total']//10:,} تومان\n"
                    report += f"• میانگین هر پرداخت: {stats['total']//stats['count']//10 if stats['count'] > 0 else 0:,} تومان\n"
                    report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n\n"

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

                    report = f"🧾 *گزارش صورتحساب‌های ارسال شده (گروه‌بندی شده)*\n\n"
                    report += f"📊 *آمار کلی:*\n"
                    report += f"• کل صورتحساب‌ها: {stats['total']}\n"
                    report += f"• ارسال شده: {stats['sent']}\n"
                    report += f"• پرداخت شده: {stats['paid']} ({stats['paid_amount']//10:,} تومان)\n"
                    report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n"
                    report += f"• کلاس‌های منحصر به فرد: {stats['unique_classes']}\n\n"

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

                    report = f"🔍 *صورتحساب‌های فیلتر شده (گروه‌بندی)*\n\n"
                    report += f"📊 *فیلترها:*\n"
                    if days:
                        report += f"• روزهای گذشته: {days}\n"
                    if status:
                        report += f"• وضعیت: {status}\n"
                    if class_name:
                        report += f"• کلاس: {class_name}\n"

                    report += f"• تعداد گروه‌ها: {len(grouped_invoices)}\n\n"

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

                    report = f"🏫 *صورتحساب‌های کلاس: {class_name}*\n\n"
                    if summary:
                        report += f"📊 *آمار کلاس:*\n"
                        report += f"• کل صورتحساب‌ها: {summary['total_invoices']}\n"
                        report += f"• پرداخت شده: {summary['paid_count']}\n"
                        report += f"• مبلغ پرداخت شده: {summary['paid_amount']//10:,} تومان\n"
                        report += f"• تعداد کاربران: {summary['total_users']}\n"
                        report += f"• نرخ پرداخت: {round(summary['paid_count']/summary['total_invoices']*100, 1) if summary['total_invoices'] > 0 else 0}%\n\n"

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
                        report += f"\n📋 *پرداخت نشده‌ها (۱۰ مورد اول):*\n"
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

                    report = f"📋 *صورتحساب‌های پرداخت نشده (۳۰ روز گذشته)*\n\n"
                    report += f"📊 تعداد کل: {len(unpaid_invoices)}\n"
                    report += f"💰 مجموع مبالغ: {sum(inv['amount'] for inv in unpaid_invoices)//10:,} تومان\n\n"

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

                    report = f"📈 *آمار دقیق صورتحساب‌ها*\n\n"

                    report += f"📊 *آمار کلی:*\n"
                    report += f"• کل صورتحساب‌ها: {stats['total']}\n"
                    report += f"• نرخ پرداخت: {round(stats['paid']/stats['total']*100, 1) if stats['total'] > 0 else 0}%\n"
                    report += f"• میانگین مبلغ پرداختی: {stats['paid_amount']//stats['paid']//10 if stats['paid'] > 0 else 0:,} تومان\n"
                    report += f"• کاربران منحصر به فرد: {stats['unique_users']}\n"
                    report += f"• کلاس‌های فعال: {stats['unique_classes']}\n\n"

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
                        "📝 *فرمت دستور:*\n\n"
                        "get_money\n"
                        "<مبلغ به تومان>\n"
                        "<نام کلاس>\n"
                        "<عنوان صورتحساب>\n"
                        "<توضیحات>\n\n"
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
                    error_msg = "⚠️ *خطاهای اعتبارسنجی:*\n\n"
                    for error in validation['errors']:
                        error_msg += f"• {error}\n"

                    error_msg += "\n🔍 *راهنمایی:*\n"
                    error_msg += "- برای مشاهده کلاس‌ها: list_classes\n"
                    error_msg += "- عنوان: حداکثر 32 کاراکتر\n"
                    error_msg += "- توضیحات: حداکثر 255 کاراکتر"

                    message.reply(error_msg)
                    return

                summary = (
                    f"✅ *اطلاعات معتبر هستند*\n\n"
                    f"📋 *خلاصه صورتحساب:*\n"
                    f"• مبلغ: {int(validation['amount_rial'] / 10):,} تومان ({validation['amount_rial']:,} ریال)\n"
                    f"• کلاس: {validation['class_name']} ({validation['users_count']} کاربر)\n"
                    f"• عنوان: {validation['title']}\n"
                    f"• توضیحات: {validation['description']}\n\n"
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
        parts = payload.split('_')

        if len(parts) >= 4 and parts[0] == "class" and parts[2] == "user":
            class_name = parts[1]
            user_id = int(parts[3])
            timestamp = parts[5] if len(parts) > 5 else None

            print(f"✅ استخراج از payload: کاربر={user_id}, کلاس={class_name}")
        else:
            print(f"❌ فرمت payload نامعتبر: {payload}")
            client.answer_pre_checkout_query(query_id, ok=False, error_message="شناسه پرداخت نامعتبر")
            return
    except (ValueError, IndexError) as e:
        print(f"❌ خطا در تجزیه payload: {e}")
        client.answer_pre_checkout_query(query_id, ok=False, error_message="خطا در شناسه پرداخت")
        return

    print(f"🔄 دریافت درخواست پرداخت از کاربر {user_id}")
    print(f"   Payload: {payload}")
    print(f"   مبلغ: {pre_checkout_query.total_amount} ریال")
    print(f"   ارز: {pre_checkout_query.currency}")

    invoice = get_invoice_by_payload(payload)
    if not invoice:
        error_msg = "صورتحساب نامعتبر یا یافت نشد."
        print(f"❌ {error_msg}")
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message=error_msg
        )
        return

    if invoice['status'] != 'sent':
        error_msg = "این صورتحساب قبلاً پرداخت شده است."
        print(f"❌ {error_msg}")
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message=error_msg
        )
        return

    if int(user_id) != int(invoice['user_id']):
        error_msg = "این صورتحساب برای شما صادر نشده است."
        print(f"❌ {error_msg}")
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message=error_msg
        )
        return

    if pre_checkout_query.total_amount != invoice['amount']:
        error_msg = f"مبلغ پرداخت ({pre_checkout_query.total_amount} ریال) با صورتحساب ({invoice['amount']} ریال) مطابقت ندارد."
        print(f"❌ {error_msg}")
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message="مبلغ پرداخت با صورتحساب مطابقت ندارد."
        )
        return

    if pre_checkout_query.currency != "IRR":
        error_msg = f"ارز پرداخت ({pre_checkout_query.currency}) نامعتبر است. باید IRR باشد."
        print(f"❌ {error_msg}")
        client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message="ارز پرداخت نامعتبر است."
        )
        return

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