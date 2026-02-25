from app.db.cruds.classes import add_users_to_class, get_class_id_by_name
from app.db.cruds.users import get_all_users_with_names


def _reply_long(message, text, limit=3800):
    if len(text) > limit:
        chunks = [text[i:i+limit] for i in range(0, len(text), limit)]
        for chunk in chunks:
            message.reply(chunk)
    else:
        message.reply(text)


def _reply_lines_safely(message, text, limit=3800):
    if len(text) <= limit:
        message.reply(text)
        return
    lines = text.split('\n')
    current = ""
    for line in lines:
        if len(current + line + '\n') > limit:
            message.reply(current)
            current = line + '\n'
        else:
            current += line + '\n'
    if current.strip():
        message.reply(current)


def _build_users_list(all_users, title):
    msg = title + "\n"
    for idx, uid, name in all_users:
        msg += f"{idx}. {name} (ID: {uid})\n"
    return msg


def _handle_list_users(text, message):
    if text not in ("users", "list_users"):
        return False

    all_users = get_all_users_with_names()
    if not all_users:
        message.reply("هیچ کاربری ثبت نشده است.")
        return True

    msg = _build_users_list(all_users, "👥 لیست تمام کاربران:")
    _reply_long(message, msg)
    return True


def _handle_add_users_command(uid, text, message, user_states):
    if text != "add_users":
        return False

    all_users = get_all_users_with_names()
    if not all_users:
        message.reply("هیچ کاربری ثبت نشده است.")
        return True

    msg = _build_users_list(all_users, "لیست کاربران:")
    _reply_lines_safely(message, msg)

    message.reply(
        "حالا نام کلاس و شماره‌های کاربران را به این شکل وارد کنید:\nنام_کلاس\n1 3 5 8")
    user_states[uid] = 'waiting_add_users'
    return True


def _handle_waiting_add_users(uid, text, message, user_states):
    if uid not in user_states or user_states[uid] != 'waiting_add_users':
        return False

    lines = text.strip().split('\n')
    if len(lines) < 2:
        message.reply(
            "فرمت نادرست. باید نام کلاس و سپس شماره‌ها باشد.")
        del user_states[uid]
        return True

    class_name = lines[0].strip()
    numbers_str = ' '.join(lines[1:]).strip()
    try:
        numbers = [int(x) for x in numbers_str.split()]
    except:
        message.reply("شماره‌ها نامعتبر هستند.")
        del user_states[uid]
        return True

    class_id = get_class_id_by_name(class_name)
    if not class_id:
        message.reply(f"کلاس '{class_name}' وجود ندارد.")
        del user_states[uid]
        return True

    all_users = get_all_users_with_names()
    valid_uids = []
    for num in numbers:
        if 1 <= num <= len(all_users):
            valid_uids.append(all_users[num-1][1])
        else:
            message.reply(f"شماره {num} نامعتبر است.")

    if valid_uids:
        add_users_to_class(class_id, valid_uids)
        message.reply(
            f"{len(valid_uids)} کاربر به کلاس '{class_name}' اضافه شد.")
    else:
        message.reply("هیچ کاربر معتبری انتخاب نشد.")

    del user_states[uid]
    return True


def user_hadnler(uid, text, message, user_states):
    if _handle_list_users(text, message):
        return
    if _handle_add_users_command(uid, text, message, user_states):
        return
    if _handle_waiting_add_users(uid, text, message, user_states):
        return
