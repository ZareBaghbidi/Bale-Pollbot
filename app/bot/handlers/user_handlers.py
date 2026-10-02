from balethon.objects import InlineKeyboard

from app.db.cruds.classes import (
    get_all_classes, get_users_in_class, update_class_users,
)
from app.db.cruds.users import get_all_users_with_names


ADD_USERS_PAGE_SIZE = 8


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


async def _handle_add_users_command(uid, message, pending_actions, user_states):
    classes = get_all_classes()
    if not classes:
        await message.reply("هنوز کلاسی ساخته نشده است.")
        return
    pending_actions[uid] = {"kind": "manage_class_users", "step": "class"}
    user_states[uid] = "add_users_select_class"
    rows = [[(name, f"au:class:{uid}:{class_id}")]
            for class_id, name in classes]
    rows.append([("❌ لغو", f"au:cancel:{uid}")])
    await message.reply(
        "کلاس موردنظر را انتخاب کن:", reply_markup=InlineKeyboard(*rows))


async def _show_add_users_page(message, uid, pending, page=0, edit=True):
    class_id = pending["class_id"]
    users = get_all_users_with_names()
    if not users:
        text = "هیچ کاربری ثبت نشده است."
        if edit:
            await message.edit_text(text, reply_markup=None)
        else:
            await message.reply(text)
        return

    existing_ids = set(get_users_in_class(class_id))
    page_count = max(1, (len(users) + ADD_USERS_PAGE_SIZE - 1)
                     // ADD_USERS_PAGE_SIZE)
    page = min(max(page, 0), page_count - 1)
    pending["page"] = page
    start = page * ADD_USERS_PAGE_SIZE
    page_users = users[start:start + ADD_USERS_PAGE_SIZE]
    rows = []
    for _, user_id, name in page_users:
        display_name = (name or str(user_id))[:28]
        if user_id in existing_ids:
            selected = user_id in pending["selected_user_ids_to_remove"]
            label = ("❌ " if selected else "✅ ") + display_name + " (عضو)"
        else:
            selected = user_id in pending["selected_user_ids_to_add"]
            label = ("✅ " if selected else "▫️ ") + display_name
        data = f"au:toggle:{uid}:{class_id}:{user_id}:{page}"
        rows.append([(label, data)])

    navigation = []
    if page > 0:
        navigation.append(("⬅️ قبلی", f"au:page:{uid}:{class_id}:{page - 1}"))
    if page + 1 < page_count:
        navigation.append(("بعدی ➡️", f"au:page:{uid}:{class_id}:{page + 1}"))
    if navigation:
        rows.append(navigation)
    rows.append([
        (f"✅ تأیید تغییرات (+{len(pending['selected_user_ids_to_add'])} / -{len(pending['selected_user_ids_to_remove'])})",
         f"au:confirm:{uid}:{class_id}"),
        ("❌ لغو", f"au:cancel:{uid}"),
    ])
    title = (
        f"اعضای کلاس «{pending['class_name']}» را مدیریت کن.\n"
        "برای افزودن، روی کاربر غیرعضو بزن؛ برای حذف، روی عضو کلاس بزن.\n"
        "✅ عضو فعلی | ❌ انتخاب برای حذف | ▫️ انتخاب‌نشده برای افزودن\n"
        f"صفحهٔ {page + 1} از {page_count} | افزودن: {len(pending['selected_user_ids_to_add'])}"
        f" | حذف: {len(pending['selected_user_ids_to_remove'])}"
    )
    keyboard = InlineKeyboard(*rows)
    if edit:
        await message.edit_text(title, reply_markup=keyboard)
    else:
        await message.reply(title, reply_markup=keyboard)


async def handle_add_users_callback(callback_query, settings,
                                    pending_actions, user_states):
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    action = parts[1]
    try:
        uid = int(parts[2])
    except ValueError:
        await callback_query.answer("شناسهٔ کاربر نامعتبر است.", show_alert=True)
        return
    if callback_query.author.id != uid or uid not in settings.owners:
        await callback_query.answer("مدیریت کاربران کلاس فقط برای اونرهاست.", show_alert=True)
        return

    if action == "cancel" and len(parts) == 3:
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        await callback_query.answer("مدیریت کاربران کلاس لغو شد.")
        await callback_query.message.edit_text("عملیات لغو شد.", reply_markup=None)
        return

    pending = pending_actions.get(uid, {})
    if pending.get("kind") != "manage_class_users":
        await callback_query.answer("این فرایند منقضی شده است.", show_alert=True)
        return

    if action == "class" and len(parts) == 4:
        if pending.get("step") != "class":
            await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
            return
        try:
            class_id = int(parts[3])
        except ValueError:
            await callback_query.answer("شناسهٔ کلاس نامعتبر است.", show_alert=True)
            return
        class_item = next(
            (item for item in get_all_classes() if item[0] == class_id), None)
        if class_item is None:
            await callback_query.answer("این کلاس دیگر وجود ندارد.", show_alert=True)
            return
        if not get_all_users_with_names():
            await callback_query.answer("هیچ کاربری ثبت نشده است.", show_alert=True)
            return
        pending.update(
            step="users", class_id=class_id, class_name=class_item[1],
            selected_user_ids_to_add=set(),
            selected_user_ids_to_remove=set(),
        )
        user_states[uid] = "add_users_select_users"
        await callback_query.answer("کلاس انتخاب شد.")
        await _show_add_users_page(callback_query.message, uid, pending)
        return

    if len(parts) < 4 or pending.get("step") != "users":
        await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
        return
    try:
        class_id = int(parts[3])
    except ValueError:
        await callback_query.answer("شناسهٔ کلاس نامعتبر است.", show_alert=True)
        return
    if class_id != pending.get("class_id"):
        await callback_query.answer("این انتخاب برای کلاس دیگری است.", show_alert=True)
        return

    if action == "page" and len(parts) == 5:
        try:
            page = int(parts[4])
        except ValueError:
            await callback_query.answer("شمارهٔ صفحه نامعتبر است.", show_alert=True)
            return
        await callback_query.answer(" ")
        await _show_add_users_page(
            callback_query.message, uid, pending, page=page)
        return

    if action == "toggle" and len(parts) == 6:
        try:
            user_id = int(parts[4])
            page = int(parts[5])
        except ValueError:
            await callback_query.answer("شناسهٔ کاربر نامعتبر است.", show_alert=True)
            return
        existing_ids = set(get_users_in_class(class_id))
        if not any(row[1] == user_id for row in get_all_users_with_names()):
            await callback_query.answer(
                "این کاربر دیگر قابل انتخاب نیست.", show_alert=True)
            await _show_add_users_page(
                callback_query.message, uid, pending, page=page)
            return
        if user_id in existing_ids:
            selected = pending["selected_user_ids_to_remove"]
            if user_id in selected:
                selected.remove(user_id)
            else:
                selected.add(user_id)
        else:
            selected = pending["selected_user_ids_to_add"]
            if user_id in selected:
                selected.remove(user_id)
            else:
                selected.add(user_id)
        await callback_query.answer("انتخاب به‌روزرسانی شد.")
        await _show_add_users_page(
            callback_query.message, uid, pending, page=page)
        return

    if action == "confirm" and len(parts) == 4:
        selected_to_add = set(pending.get("selected_user_ids_to_add", set()))
        selected_to_remove = set(pending.get("selected_user_ids_to_remove", set()))
        if not selected_to_add and not selected_to_remove:
            await callback_query.answer(
                "تغییری انتخاب نشده است.", show_alert=True)
            return
        if not any(item[0] == class_id for item in get_all_classes()):
            pending_actions.pop(uid, None)
            user_states.pop(uid, None)
            await callback_query.answer("این کلاس دیگر وجود ندارد.", show_alert=True)
            await callback_query.message.edit_text(
                "کلاس پیدا نشد و تغییری اعمال نشد.", reply_markup=None)
            return
        existing_ids = set(get_users_in_class(class_id))
        current_user_ids = {row[1] for row in get_all_users_with_names()}
        valid_ids = sorted(
            (selected_to_add - existing_ids) & current_user_ids)
        remove_ids = sorted(selected_to_remove & existing_ids)
        update_class_users(class_id, valid_ids, remove_ids)
        class_name = pending["class_name"]
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        await callback_query.answer("تغییرات اعضای کلاس اعمال شد.")
        await callback_query.message.edit_text(
            f"✅ مدیریت اعضای کلاس «{class_name}» انجام شد.\n"
            f"افزوده‌شده: {len(valid_ids)} نفر\nحذف‌شده: {len(remove_ids)} نفر",
            reply_markup=None,
        )
        return

    await callback_query.answer("این گزینه معتبر نیست.", show_alert=True)


async def user_hadnler(uid, text, message, pending_actions, user_states):
    if text in ("users", "list_users"):
        await _handle_list_users(message)
        return True

    if text == "add_users":
        await _handle_add_users_command(
            uid, message, pending_actions, user_states)
        return True

    return False
