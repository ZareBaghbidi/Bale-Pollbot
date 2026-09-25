from app.db.cruds.classes import add_users_to_class, get_class_id_by_name
from app.db.cruds.users import get_all_users_with_names


async def _reply_long(message, text, limit=3800):
    if len(text) > limit:
        chunks = [text[i:i+limit] for i in range(0, len(text), limit)]
        for chunk in chunks:
            await message.reply(chunk)
    else:
        await message.reply(text)


async def _reply_lines_safely(message, text, limit=3800):
    if len(text) <= limit:
        await message.reply(text)
        return
    lines = text.split('\n')
    current = ""
    for line in lines:
        if len(current + line + '\n') > limit:
            await message.reply(current)
            current = line + '\n'
        else:
            current += line + '\n'
    if current.strip():
        await message.reply(current)


async def _build_users_list(all_users, title):
    msg = title + "\n"
    for idx, uid, name in all_users:
        msg += f"{idx}. {name} (ID: {uid})\n"
    return msg


async def _handle_list_users(message):
    all_users = get_all_users_with_names()
    if not all_users:
        await message.reply("هیچ کاربری ثبت نشده است.")
        return

    msg = await _build_users_list(all_users, "👥 لیست تمام کاربران:")
    await _reply_long(message, msg)
    return


async def _handle_add_users_command(uid,  message, user_states):
    all_users = get_all_users_with_names()
    if not all_users:
        await message.reply("هیچ کاربری ثبت نشده است.")
        return

    msg = await _build_users_list(all_users, "لیست کاربران:")
    await _reply_lines_safely(message, msg)

    await message.reply(
        "حالا نام کلاس و شماره‌های کاربران را به این شکل وارد کنید:\nنام_کلاس\n1 3 5 8")
    user_states[uid] = 'waiting_add_users'
    return


async def _handle_waiting_add_users(uid, text, message, user_states):
    lines = text.strip().split('\n')
    if len(lines) < 2:
        await message.reply(
            "فرمت نادرست. باید نام کلاس و سپس شماره‌ها باشد.")
        del user_states[uid]
        return

    class_name = lines[0].strip()
    numbers_str = ' '.join(lines[1:]).strip()
    try:
        numbers = [int(x) for x in numbers_str.split()]
    except:
        await message.reply("شماره‌ها نامعتبر هستند.")
        del user_states[uid]
        return

    class_id = get_class_id_by_name(class_name)
    if not class_id:
        await message.reply(f"کلاس '{class_name}' وجود ندارد.")
        del user_states[uid]
        return

    all_users = get_all_users_with_names()
    valid_uids = []
    for num in numbers:
        if 1 <= num <= len(all_users):
            valid_uids.append(all_users[num-1][1])
        else:
            await message.reply(f"شماره {num} نامعتبر است.")

    if valid_uids:
        add_users_to_class(class_id, valid_uids)
        await message.reply(
            f"{len(valid_uids)} کاربر به کلاس '{class_name}' اضافه شد.")
    else:
        await message.reply("هیچ کاربر معتبری انتخاب نشد.")

    del user_states[uid]
    return


async def user_hadnler(uid, text, message, user_states):
    if text in ("users", "list_users"):
        await _handle_list_users(message)
        return True

    if text == "add_users":
        await _handle_add_users_command(uid, message, user_states)
        return True

    if uid in user_states and user_states[uid] == 'waiting_add_users':
        await _handle_waiting_add_users(uid, text, message, user_states)
        return True

    return False
