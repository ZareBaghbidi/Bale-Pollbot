from app.db.cruds.classes import add_users_to_class, get_class_id_by_name
from app.db.cruds.users import get_all_users_with_names


def user_hadnler(uid, text, message, user_states):
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

        message.reply(
            "حالا نام کلاس و شماره‌های کاربران را به این شکل وارد کنید:\nنام_کلاس\n1 3 5 8")
        user_states[uid] = 'waiting_add_users'
        return

    if uid in user_states and user_states[uid] == 'waiting_add_users':
        lines = text.strip().split('\n')
        if len(lines) < 2:
            message.reply(
                "فرمت نادرست. باید نام کلاس و سپس شماره‌ها باشد.")
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
            message.reply(
                f"{len(valid_uids)} کاربر به کلاس '{class_name}' اضافه شد.")
        else:
            message.reply("هیچ کاربر معتبری انتخاب نشد.")

        del user_states[uid]
        return
