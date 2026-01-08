#!/usr/bin/env python3
from balethon import Client
from balethon.objects import InlineKeyboard
import time, traceback, threading
from db import *

# ---------- BOT ----------
with open("bot_id.txt") as f:
    client = Client(f.read().strip())

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

# ---------- CALLBACK QUERY ----------
@client.on_callback_query()
def on_callback_query(callback_query):
    print("Callback received! data:", callback_query.data)

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
        uid = message.author.id
        text = (message.text or "").strip()
        parts = text.split('\n')

        # print(uid, "he's send:", text)

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

                try:
                    db_name = get_user_name(uid) or message.author.first_name or ""
                    save_msg(uid, message.author.username or "", db_name, text)
                except Exception as e:
                    print("save_msg error:", e)

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
                    base_ans = "📊 گزارش:\n\n"
                    if not active_polls:
                        message.reply("_نظرسنجی فعالی موجود نمی‌باشد._")
                        return

                    current_msg = base_ans
                    for idx, pid in active_polls.items():
                        poll_type = poll_types[idx]
                        class_ = poll_classes.get(idx, '-') or '-'
                        s = stats(pid)
                        questions = get_questions(pid)
                        q_dict = {q_id: q_text for _, q_id, q_text in questions}

                        poll_text = f"نظرسنجی {idx} (کلاس: {class_}) (نوع: {poll_type}) (pid: {pid}):\n"

                        for _, q_id, _ in questions:
                            c, total = s.get(q_id, (0, None))
                            q_text = q_dict.get(q_id, '?')[:50]
                            if poll_type == 'score':
                                avg = round(total / c, 2) if c and total is not None else '-'
                                poll_text += f"{q_text}: {avg} ({c})\n"
                            else:
                                poll_text += f"{q_text}: {c} پاسخ\n"
                        poll_text += "\n"

                        if len(current_msg + poll_text) > 3800:
                            message.reply(current_msg)
                            current_msg = poll_text
                        else:
                            current_msg += poll_text

                    message.reply(current_msg)

                except Exception as e:
                    print("report error:", e)
                    traceback.print_exc()
                    message.reply("خطا در تولید یا ارسال گزارش.")
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
        if (not uid == 213614271):
            client.send_message(213614271, f"{get_user_name(uid)} این پیام رو داد:\n{text}")
        if (not uid == 1351870827):
            client.send_message(1351870827, f"{get_user_name(uid)} این پیام رو داد:\n{text}")

    except Exception as e:
        print("msg_handler top-level error:", e)
        traceback.print_exc()

# ---------- READY ----------

t = threading.Thread(target=autostart_loop, daemon=True)
t.start()

print("autocheck started")

client.run()
