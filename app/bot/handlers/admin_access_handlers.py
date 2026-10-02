from balethon.objects import InlineKeyboard

from app.bot.messages import ADMIN_HELP
from app.bot.config import save_admins
from app.db.cruds.classes import get_all_classes
from app.db.cruds.users import get_user_name
from app.bot.handlers.member_handlers import member_help_keyboard


def get_admin_allowed_class_ids(settings, admin_id):
    classes = get_all_classes()
    configured = settings.admin_class_access.get(admin_id, "*")
    if configured == "*":
        return {class_id for class_id, _ in classes}
    return set(configured)


def admin_can_access_class(settings, admin_id, class_id):
    configured = settings.admin_class_access.get(admin_id, "*")
    return configured == "*" or class_id in configured


def _admin_class_access_keyboard(owner_id, admin_id, classes, allowed_ids):
    rows = []
    for class_id, class_name in classes:
        marker = "✅" if class_id in allowed_ids else "❌"
        rows.append([(
            f"{marker} {class_name}",
            f"rac:toggle:{owner_id}:{admin_id}:{class_id}",
        )])
    rows.append([("بستن", f"rac:close:{owner_id}:{admin_id}")])
    return InlineKeyboard(*rows)


async def _edit_admin_class_access(callback_query, owner_id, admin_id, settings):
    classes = get_all_classes()
    admin_name = get_user_name(admin_id) or str(admin_id)
    allowed_ids = get_admin_allowed_class_ids(settings, admin_id)
    text = (
        f"دسترسی کلاسی ادمین {admin_name} (شناسه: {admin_id})\n"
        "✅ یعنی مجاز؛ ❌ یعنی محدود. برای تغییر وضعیت هر کلاس دکمه‌اش را بزنید."
    )
    if not classes:
        text += "\n\nهنوز کلاسی ساخته نشده است."
    await callback_query.message.edit_text(
        text,
        reply_markup=_admin_class_access_keyboard(
            owner_id, admin_id, classes, allowed_ids),
    )


async def handle_admin_access_callback(callback_query, settings):
    parts = callback_query.data.split(":")
    if len(parts) < 4:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return

    action = parts[1]
    try:
        owner_id = int(parts[2])
        admin_id = int(parts[3])
    except ValueError:
        await callback_query.answer("شناسهٔ کاربر نامعتبر است.", show_alert=True)
        return

    if callback_query.author.id != owner_id or owner_id not in settings.owners:
        await callback_query.answer("این گزینه فقط برای اونرهاست.", show_alert=True)
        return
    if admin_id not in settings.admins:
        await callback_query.answer("این کاربر دیگر ادمین نیست.", show_alert=True)
        return

    if action == "open" and len(parts) == 4:
        await callback_query.answer("فهرست کلاس‌ها باز شد.")
        classes = get_all_classes()
        admin_name = get_user_name(admin_id) or str(admin_id)
        allowed_ids = get_admin_allowed_class_ids(settings, admin_id)
        text = (
            f"دسترسی کلاسی ادمین {admin_name} (شناسه: {admin_id})\n"
            "✅ یعنی مجاز؛ ❌ یعنی محدود. برای تغییر وضعیت هر کلاس دکمه‌اش را بزنید."
        )
        if not classes:
            text += "\n\nهنوز کلاسی ساخته نشده است."
        await callback_query.message.reply(
            text,
            reply_markup=_admin_class_access_keyboard(
                owner_id, admin_id, classes, allowed_ids),
        )
        return

    if action == "close" and len(parts) == 4:
        await callback_query.answer("بسته شد.")
        await callback_query.message.edit_text(
            "تنظیم دسترسی کلاسی بسته شد.", reply_markup=None)
        return

    if action == "toggle" and len(parts) == 5:
        try:
            class_id = int(parts[4])
        except ValueError:
            await callback_query.answer("شناسهٔ کلاس نامعتبر است.", show_alert=True)
            return
        classes = get_all_classes()
        if not any(item[0] == class_id for item in classes):
            await callback_query.answer("این کلاس دیگر وجود ندارد.", show_alert=True)
            await _edit_admin_class_access(
                callback_query, owner_id, admin_id, settings)
            return

        previous = settings.admin_class_access.get(admin_id)
        if previous is None or previous == "*":
            allowed_ids = {item[0] for item in classes}
        else:
            allowed_ids = set(previous)
        if class_id in allowed_ids:
            allowed_ids.remove(class_id)
            status = "محدود شد"
        else:
            allowed_ids.add(class_id)
            status = "مجاز شد"

        settings.admin_class_access[admin_id] = allowed_ids
        try:
            save_admins(settings.admins, settings.admin_class_access)
        except OSError as exc:
            if previous is None:
                settings.admin_class_access.pop(admin_id, None)
            else:
                settings.admin_class_access[admin_id] = previous
            print(f"ذخیرهٔ دسترسی کلاسی ادمین {admin_id} ناموفق بود: {exc}")
            await callback_query.answer(
                "ذخیرهٔ دسترسی انجام نشد؛ فایل app/.env را بررسی کنید.",
                show_alert=True,
            )
            return

        await callback_query.answer(f"دسترسی این کلاس {status}.")
        await _edit_admin_class_access(
            callback_query, owner_id, admin_id, settings)
        return

    await callback_query.answer("این گزینه معتبر یا فعال نیست.", show_alert=True)


def _admin_removal_keyboard(owner_id, admins, selected_ids):
    rows = []
    for admin_id in admins:
        name = (get_user_name(admin_id) or "بدون نام")[:20]
        marker = "✅" if admin_id in selected_ids else "▫️"
        rows.append([(
            f"{marker} {name} ({admin_id})",
            f"ar:toggle_remove:{owner_id}:{admin_id}",
        )])
    rows.append([
        (f"✅ تأیید حذف ({len(selected_ids)})", f"ar:confirm_remove:{owner_id}"),
        ("❌ لغو", f"ar:cancel:{owner_id}"),
    ])
    return InlineKeyboard(*rows)


async def _show_admin_removal_list(message, owner_id, settings,
                                   selected_ids, edit=False):
    admins = sorted(settings.admins - settings.owners)
    if not admins:
        text = "ادمینی برای حذف وجود ندارد."
        keyboard = InlineKeyboard([("بستن", f"ar:cancel:{owner_id}")])
    else:
        text = (
            "ادمین‌هایی را که باید حذف شوند انتخاب کن.\n"
            "بعد از انتخاب، دکمهٔ تأیید نهایی را بزن."
        )
        keyboard = _admin_removal_keyboard(owner_id, admins, selected_ids)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.reply(text, reply_markup=keyboard)


async def handle_admin_add_message(uid, text, message, client, settings,
                                   pending_actions, user_states):
    if (uid not in settings.owners
            or user_states.get(uid) != "admin_add_ids"
            or pending_actions.get(uid, {}).get("kind") != "admin_add"):
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        await message.reply("این فرایند افزودن ادمین در دسترس نیست.")
        return True

    normalized = text.translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    raw_ids = normalized.replace(",", " ").split()
    try:
        target_ids = {int(item) for item in raw_ids}
        if not target_ids or any(target_id <= 0 for target_id in target_ids):
            raise ValueError
    except ValueError:
        await message.reply(
            "یک یا چند شناسهٔ عددی و مثبت بفرست؛ شناسه‌ها را با فاصله یا ویرگول جدا کن.",
            reply_markup=InlineKeyboard([("❌ لغو", f"ar:cancel:{uid}")]),
        )
        return True

    added_ids = sorted(
        target_id for target_id in target_ids
        if target_id not in settings.owners and target_id not in settings.admins
    )
    skipped_ids = sorted(target_ids - set(added_ids))
    if not added_ids:
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        await message.reply("همهٔ شناسه‌ها از قبل ادمین یا اونر هستند؛ تغییری انجام نشد.")
        return True

    previous_admins = set(settings.admins)
    previous_access = dict(settings.admin_class_access)
    settings.admins.update(added_ids)
    for admin_id in added_ids:
        settings.admin_class_access[admin_id] = "*"
    try:
        save_admins(settings.admins, settings.admin_class_access)
    except OSError as exc:
        settings.admins = previous_admins
        settings.admin_class_access = previous_access
        print(f"ذخیرهٔ ادمین‌های جدید ناموفق بود: {exc}")
        await message.reply("ذخیرهٔ تغییرات در app/.env انجام نشد؛ چیزی اضافه نشد.")
        return True

    pending_actions.pop(uid, None)
    user_states.pop(uid, None)
    await message.reply(
        "✅ ادمین‌های جدید اضافه شدند: "
        + ", ".join(str(admin_id) for admin_id in added_ids)
        + ("\nشناسه‌های ردشده (از قبل ادمین/اونر): "
           + ", ".join(str(admin_id) for admin_id in skipped_ids)
           if skipped_ids else "")
    )
    for admin_id in added_ids:
        try:
            await client.send_message(
                admin_id,
                "✅ شما به‌عنوان ادمین ربات انتخاب شده‌اید.\n\n"
                "فعلاً اجازهٔ ساخت نظرسنجی برای همهٔ کلاس‌ها را دارید.\n\n"
                f"{ADMIN_HELP}",
                reply_markup=member_help_keyboard(),
            )
        except Exception as exc:
            print(f"اطلاع‌رسانی ادمین‌شدن به {admin_id} ناموفق بود: {exc}")
    return True


async def handle_admin_role_callback(callback_query, client, settings,
                                     pending_actions, user_states):
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    action = parts[1]
    try:
        owner_id = int(parts[2])
    except ValueError:
        await callback_query.answer("شناسهٔ اونر نامعتبر است.", show_alert=True)
        return
    if callback_query.author.id != owner_id or owner_id not in settings.owners:
        await callback_query.answer("این گزینه فقط برای اونرهاست.", show_alert=True)
        return

    if action == "add" and len(parts) == 3:
        pending_actions[owner_id] = {"kind": "admin_add", "step": "ids"}
        user_states[owner_id] = "admin_add_ids"
        await callback_query.answer("شناسه‌ها را بفرستید.")
        await callback_query.message.reply(
            "شناسهٔ یک یا چند کاربر را بفرستید؛ اگر چند نفر هستند، شناسه‌ها را با فاصله یا ویرگول جدا کنید.\n"
            "ادمین‌های تازه ابتدا به همهٔ کلاس‌ها دسترسی دارند.",
            reply_markup=InlineKeyboard([("❌ لغو", f"ar:cancel:{owner_id}")]),
        )
        return

    if action == "remove" and len(parts) == 3:
        pending_actions[owner_id] = {
            "kind": "admin_remove", "step": "select", "selected_ids": set(),
        }
        user_states[owner_id] = "admin_remove_select"
        await callback_query.answer("ادمین‌ها را انتخاب کنید.")
        await _show_admin_removal_list(
            callback_query.message, owner_id, settings, set())
        return

    if action == "cancel" and len(parts) == 3:
        pending = pending_actions.get(owner_id, {})
        if pending.get("kind") not in ("admin_add", "admin_remove"):
            await callback_query.answer("این فرایند منقضی شده است.", show_alert=True)
            return
        pending_actions.pop(owner_id, None)
        user_states.pop(owner_id, None)
        await callback_query.answer("لغو شد.")
        await callback_query.message.edit_text("عملیات لغو شد.", reply_markup=None)
        return

    pending = pending_actions.get(owner_id, {})
    if pending.get("kind") != "admin_remove" or pending.get("step") != "select":
        await callback_query.answer("این فرایند منقضی شده است.", show_alert=True)
        return

    if action == "toggle_remove" and len(parts) == 4:
        try:
            admin_id = int(parts[3])
        except ValueError:
            await callback_query.answer("شناسهٔ ادمین نامعتبر است.", show_alert=True)
            return
        if admin_id not in settings.admins or admin_id in settings.owners:
            await callback_query.answer("این کاربر دیگر ادمین نیست.", show_alert=True)
            return
        selected_ids = pending["selected_ids"]
        if admin_id in selected_ids:
            selected_ids.remove(admin_id)
        else:
            selected_ids.add(admin_id)
        await callback_query.answer("انتخاب به‌روزرسانی شد.")
        await _show_admin_removal_list(
            callback_query.message, owner_id, settings, selected_ids, edit=True)
        return

    if action == "confirm_remove" and len(parts) == 3:
        selected_ids = set(pending.get("selected_ids", set()))
        selected_ids &= settings.admins - settings.owners
        if not selected_ids:
            await callback_query.answer(
                "ادمین‌هایی را برای حذف انتخاب کنید.", show_alert=True)
            return

        previous_admins = set(settings.admins)
        previous_access = dict(settings.admin_class_access)
        settings.admins.difference_update(selected_ids)
        for admin_id in selected_ids:
            settings.admin_class_access.pop(admin_id, None)
        try:
            save_admins(settings.admins, settings.admin_class_access)
        except OSError as exc:
            settings.admins = previous_admins
            settings.admin_class_access = previous_access
            print(f"ذخیرهٔ حذف ادمین‌ها ناموفق بود: {exc}")
            await callback_query.answer(
                "ذخیرهٔ تغییرات در app/.env انجام نشد.", show_alert=True)
            return

        pending_actions.pop(owner_id, None)
        user_states.pop(owner_id, None)
        await callback_query.answer("ادمین‌های انتخاب‌شده حذف شدند.")
        await callback_query.message.edit_text(
            "✅ ادمین‌های انتخاب‌شده حذف شدند: "
            + ", ".join(str(admin_id) for admin_id in sorted(selected_ids)),
            reply_markup=None,
        )
        for admin_id in selected_ids:
            try:
                await client.send_message(
                    admin_id, "ℹ️ دسترسی ادمین شما از ربات برداشته شد.",
                    reply_markup=member_help_keyboard(),
                )
            except Exception as exc:
                print(f"اطلاع‌رسانی حذف ادمین به {admin_id} ناموفق بود: {exc}")
        return

    await callback_query.answer("این گزینه معتبر نیست.", show_alert=True)
