

import datetime
import time
import traceback
import jdatetime
from balethon.objects import InlineKeyboard
from app.db.cruds.classes import delete_class, get_all_classes, get_users_in_class
from app.db.cruds.polls import create_poll, get_poll_class, get_poll_type, is_poll_active
from app.db.cruds.questions import add_question, get_question_id
from app.db.cruds.tasks import add_task
from app.db.cruds.users import get_user_classes, get_user_name
from app.db.cruds.votes import vote
from app.services.patment import send_pay_to_class
from app.services.poll import activate_poll
from app.bot.poll_calendar import (
    TEHRAN, calendar_keyboard, class_keyboard, current_jalali_month,
    fa_num, hour_keyboard, minute_keyboard, schedule_keyboard,
)


async def get_money_wizard_callback(callback_query, settings, pending_actions, user_states):
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    action = parts[1]
    try:
        uid = int(parts[2])
    except ValueError:
        await callback_query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    if callback_query.author.id != uid or uid not in settings.owners:
        await callback_query.answer("این گزینه فقط برای اونر سازنده است.", show_alert=True)
        return
    pending = pending_actions.get(uid, {})
    if action == "cancel":
        if pending.get("kind") == "get_money_wizard":
            pending_actions.pop(uid, None)
            user_states.pop(uid, None)
            await callback_query.answer("ساخت صورتحساب لغو شد.")
            await callback_query.message.edit_text("❌ ساخت صورتحساب لغو شد.", reply_markup=None)
        else:
            await callback_query.answer("این فرایند منقضی شده است.", show_alert=True)
        return
    if (action != "class" or len(parts) != 4
            or pending.get("kind") != "get_money_wizard"
            or pending.get("step") != "class"):
        await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
        return
    try:
        class_id = int(parts[3])
    except ValueError:
        await callback_query.answer("کلاس نامعتبر است.", show_alert=True)
        return
    class_item = next((item for item in get_all_classes() if item[0] == class_id), None)
    if class_item is None:
        await callback_query.answer("این کلاس دیگر وجود ندارد.", show_alert=True)
        return
    if not get_users_in_class(class_id):
        await callback_query.answer("این کلاس کاربری ندارد.", show_alert=True)
        return
    pending.update(class_name=class_item[1], step="amount")
    user_states[uid] = "get_money_amount"
    await callback_query.answer("کلاس انتخاب شد.")
    await callback_query.message.edit_text(
        f"کلاس «{class_item[1]}» انتخاب شد.\nمبلغ را به تومان و به‌صورت عدد صحیح بفرست؛ مثلاً 5000.",
        reply_markup=InlineKeyboard([("❌ لغو", f"gm:cancel:{uid}")])
    )


async def confirm_pay(callback_query, pending_actions, client, settings, user_states):
    target_uid = int(callback_query.data.split("_")[2])

    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    validation = pending_actions.get(target_uid, {})
    if not validation:
        await callback_query.answer("اطلاعات یافت نشد!", show_alert=True)
        return

    await callback_query.answer("در حال ارسال صورتحساب‌ها...")

    success, result_msg = await send_pay_to_class(client, settings,
                                            validation['class_name'],
                                            validation['amount_rial'],
                                            validation['title'],
                                            validation['description']
                                            )

    await client.send_message(target_uid, result_msg)

    if target_uid in user_states:
        del user_states[target_uid]
    if target_uid in pending_actions:
        pending_actions.pop(target_uid)

    await callback_query.message.edit_text(
        f"✅ **عملیات تکمیل شد**\n",
        reply_markup=None
    )
    return


async def cancel_pay(callback_query, pending_actions,  user_states):
    target_uid = int(callback_query.data.split("_")[2])

    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    if target_uid in user_states:
        del user_states[target_uid]
    if target_uid in pending_actions:
        pending_actions.pop(target_uid)

    await callback_query.message.edit_text(
        "❌ **عملیات لغو شد**\nارسال صورتحساب‌ها کنسل شد.",
        reply_markup=None
    )
    await callback_query.answer("عملیات لغو شد")
    return


async def confirm_poll(callback_query, pending_actions, client, user_states):
    target_uid = int(callback_query.data.split("_")[2])

    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    pending = pending_actions.get(target_uid)
    if not pending or pending.get('kind') != 'poll':
        await callback_query.answer(
            "اطلاعات نظرسنجی یافت نشد یا منقضی شده!", show_alert=True)
        return

    await callback_query.answer("در حال ایجاد نظرسنجی...")

    poll_type = pending['poll_type']
    class_name = pending['class_name']
    ts = pending['ts']
    q_text = pending['q_text']

    try:
        pid = create_poll(poll_type, class_name)
        add_question(pid, 0, q_text)

        if ts is None:
            await activate_poll(client, pid)
            target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
            result_msg = f"✅ نظرسنجی[{pid}] با موفقیت ایجاد و فعال شد.\n"
            result_msg += f"🔹 کلاس: {target}\n"
            result_msg += f"🔹 سوال: {q_text}"
        else:
            add_task(ts, pid)
            target = 'برای همه' if class_name is None else f'برای کلاس {class_name}'
            scheduled_at = datetime.datetime.fromtimestamp(ts, TEHRAN)
            jalali_day = jdatetime.date.fromgregorian(date=scheduled_at.date())
            dt_str = (f"{fa_num(jalali_day.year)}/{fa_num(str(jalali_day.month).zfill(2))}/"
                      f"{fa_num(str(jalali_day.day).zfill(2))} "
                      f"{fa_num(str(scheduled_at.hour).zfill(2))}:"
                      f"{fa_num(str(scheduled_at.minute).zfill(2))}")
            result_msg = f"✅ نظرسنجی[{pid}] با موفقیت ایجاد و برای زمان {dt_str} زمان‌بندی شد.\n"
            result_msg += f"🔹 کلاس: {target}\n"
            result_msg += f"🔹 سوال: {q_text}"

        if target_uid in user_states:
            del user_states[target_uid]
        if target_uid in pending_actions:
            pending_actions.pop(target_uid)

        await callback_query.message.edit_text(result_msg, reply_markup=None)

    except Exception as e:
        print("Error in confirm_poll:", e)
        traceback.print_exc()
        await callback_query.answer("خطا در ایجاد نظرسنجی!", show_alert=True)
    return


def _poll_preview_keyboard(uid):
    return InlineKeyboard(
        [("✅ تایید", f"confirm_poll_{uid}"),
         ("❌ لغو", f"cancel_poll_{uid}")]
    )


async def _finish_poll_wizard(callback_query, uid, pending_actions, user_states, ts):
    pending = pending_actions[uid]
    pending.update(kind="poll", ts=ts)
    user_states[uid] = "confirm_poll"
    type_label = "امتیازی (۱ تا ۱۰)" if pending["poll_type"] == "score" else "پاسخ متنی"
    if ts is None:
        time_label = "شروع فوری"
    else:
        local_time = datetime.datetime.fromtimestamp(ts, TEHRAN)
        local_day = jdatetime.date.fromgregorian(date=local_time.date())
        time_label = (f"{fa_num(local_day.year)}/{fa_num(str(local_day.month).zfill(2))}/"
                      f"{fa_num(str(local_day.day).zfill(2))} "
                      f"{fa_num(str(local_time.hour).zfill(2))}:"
                      f"{fa_num(str(local_time.minute).zfill(2))}")
    summary = (
        "📊 خلاصه نظرسنجی جدید\n"
        f"🔹 نوع: {type_label}\n"
        f"🔹 کلاس: {pending['class_name']}\n"
        f"🔹 زمان: {time_label}\n"
        f"🔹 سوال: {pending['q_text']}\n\n"
        "آیا از ایجاد نظرسنجی مطمئنی؟"
    )
    await callback_query.message.edit_text(
        summary, reply_markup=_poll_preview_keyboard(uid)
    )


async def poll_wizard_callback(callback_query, settings, pending_actions, user_states):
    """Handle type/class/date/time choices for the interactive poll wizard."""
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("داده نامعتبر است.", show_alert=True)
        return
    action = parts[1]
    try:
        uid = int(parts[2])
    except ValueError:
        await callback_query.answer("داده نامعتبر است.", show_alert=True)
        return

    if callback_query.author.id != uid:
        await callback_query.answer("این درخواست برای شما نیست!", show_alert=True)
        return
    if uid not in settings.owners and uid not in settings.admins:
        await callback_query.answer("دسترسی شما به این عملیات لغو شده است.", show_alert=True)
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        return

    pending = pending_actions.get(uid)
    if not pending or pending.get("kind") != "poll_wizard":
        await callback_query.answer("این فرایند منقضی شده است؛ دوباره create_poll را بفرست.", show_alert=True)
        return

    if action == "cancel":
        pending_actions.pop(uid, None)
        user_states.pop(uid, None)
        await callback_query.answer("ساخت نظرسنجی لغو شد.")
        await callback_query.message.edit_text("❌ ساخت نظرسنجی لغو شد.", reply_markup=None)
        return

    if action == "noop":
        await callback_query.answer("از دکمه‌های تقویم استفاده کن.")
        return

    if action == "type":
        if pending.get("step") != "type" or len(parts) != 4 or parts[3] not in ("score", "text"):
            await callback_query.answer("انتخاب نوع معتبر نیست.", show_alert=True)
            return
        pending["poll_type"] = parts[3]
        classes = get_all_classes()
        if not classes:
            pending_actions.pop(uid, None)
            user_states.pop(uid, None)
            await callback_query.answer("هنوز کلاسی ساخته نشده است.", show_alert=True)
            await callback_query.message.edit_text("برای ساخت نظرسنجی اول باید یک کلاس بسازید.", reply_markup=None)
            return
        pending["step"] = "class"
        user_states[uid] = "poll_wizard_class"
        await callback_query.answer("نوع انتخاب شد.")
        await callback_query.message.edit_text("کلاس مقصد را انتخاب کن:", reply_markup=class_keyboard(uid, classes))
        return

    if action == "class":
        if pending.get("step") != "class" or len(parts) != 4:
            await callback_query.answer("انتخاب کلاس معتبر نیست.", show_alert=True)
            return
        try:
            class_id = int(parts[3])
        except ValueError:
            await callback_query.answer("کلاس نامعتبر است.", show_alert=True)
            return
        class_item = next((item for item in get_all_classes() if item[0] == class_id), None)
        if class_item is None:
            await callback_query.answer("این کلاس دیگر وجود ندارد.", show_alert=True)
            return
        pending["class_name"] = class_item[1]
        pending["step"] = "question"
        user_states[uid] = "poll_wizard_question"
        await callback_query.answer("کلاس انتخاب شد.")
        await callback_query.message.edit_text("متن سوال نظرسنجی را در یک پیام بفرست:", reply_markup=None)
        return

    if action == "now":
        if pending.get("step") != "schedule":
            await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
            return
        await callback_query.answer("شروع فوری انتخاب شد.")
        await _finish_poll_wizard(callback_query, uid, pending_actions, user_states, None)
        return

    if action == "calendar":
        if pending.get("step") != "schedule":
            await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
            return
        year, month = current_jalali_month()
        pending.update(step="calendar", cal_year=year, cal_month=month)
        user_states[uid] = "poll_wizard_calendar"
        await callback_query.answer("یک روز از تقویم انتخاب کن.")
        await callback_query.message.edit_text(
            "📅 تاریخ شمسی ارسال نظرسنجی را از تقویم انتخاب کن.\n"
            "برای جابه‌جایی بین ماه‌ها از دکمه‌های «‹» و «›» استفاده کن و سپس روی روز دلخواه بزن.\n"
            "زمان‌بندی بر اساس ساعت رسمی تهران انجام می‌شود.",
            reply_markup=calendar_keyboard(uid, year, month)
        )
        return

    if action == "month":
        if pending.get("step") != "calendar" or len(parts) != 6:
            await callback_query.answer("تقویم منقضی شده است.", show_alert=True)
            return
        try:
            year, month = int(parts[3]), int(parts[4])
        except ValueError:
            await callback_query.answer("ماه نامعتبر است.", show_alert=True)
            return
        direction = parts[5]
        month += -1 if direction == "prev" else 1
        if month < 1:
            year, month = year - 1, 12
        elif month > 12:
            year, month = year + 1, 1
        pending.update(cal_year=year, cal_month=month)
        await callback_query.answer(" ")
        await callback_query.message.edit_text(
            "📅 تاریخ شمسی ارسال نظرسنجی را از تقویم انتخاب کن.\n"
            "برای جابه‌جایی بین ماه‌ها از دکمه‌های «‹» و «›» استفاده کن و سپس روی روز دلخواه بزن.\n"
            "زمان‌بندی بر اساس ساعت رسمی تهران انجام می‌شود.",
            reply_markup=calendar_keyboard(uid, year, month)
        )
        return

    if action in ("day", "past"):
        if pending.get("step") != "calendar" or len(parts) != 6:
            await callback_query.answer("تقویم منقضی شده است.", show_alert=True)
            return
        try:
            year, month, day = map(int, parts[3:6])
            selected = jdatetime.date(year, month, day)
        except (ValueError, TypeError):
            await callback_query.answer("تاریخ نامعتبر است.", show_alert=True)
            return
        today = jdatetime.date.fromgregorian(date=datetime.datetime.now(TEHRAN).date())
        if selected < today:
            await callback_query.answer("تاریخ گذشته را نمی‌توان انتخاب کرد.", show_alert=True)
            return
        pending.update(step="time", jalali_year=year, jalali_month=month, jalali_day=day)
        user_states[uid] = "poll_wizard_time"
        await callback_query.answer(" ")
        await callback_query.message.edit_text(
            f"تاریخ {fa_num(year)}/{fa_num(str(month).zfill(2))}/{fa_num(str(day).zfill(2))} انتخاب شد.\n"
            "حالا ساعت و دقیقهٔ ارسال را در یک پیام به شکل ساعت:دقیقه بفرست؛ مثلاً `18:05`.\n"
            "ساعت باید از ۰ تا ۲۳ و دقیقه از ۰ تا ۵۹ باشد. زمان بر اساس ساعت تهران است."
        )
        return

    if action == "hour":
        if pending.get("step") != "hour" or len(parts) != 4:
            await callback_query.answer("انتخاب ساعت معتبر نیست.", show_alert=True)
            return
        try:
            hour = int(parts[3])
        except ValueError:
            await callback_query.answer("ساعت نامعتبر است.", show_alert=True)
            return
        if not 0 <= hour <= 23:
            await callback_query.answer("ساعت نامعتبر است.", show_alert=True)
            return
        pending.update(step="minute", hour=hour)
        user_states[uid] = "poll_wizard_minute"
        await callback_query.answer(" ")
        await callback_query.message.edit_text(
            f"ساعت {fa_num(str(hour).zfill(2))} انتخاب شد.\n"
            "دقیقهٔ دقیق ارسال را از گزینه‌های زیر انتخاب کن.\n"
            "در مرحلهٔ بعد، خلاصهٔ زمان‌بندی را پیش از تأیید می‌بینی.",
            reply_markup=minute_keyboard(uid)
        )
        return

    if action == "minute":
        if pending.get("step") != "minute" or len(parts) != 4:
            await callback_query.answer("انتخاب دقیقه معتبر نیست.", show_alert=True)
            return
        try:
            minute = int(parts[3])
            jalali_date = jdatetime.date(
                pending["jalali_year"], pending["jalali_month"], pending["jalali_day"]
            )
            gregorian_date = jalali_date.togregorian()
            local_dt = datetime.datetime.combine(
                gregorian_date, datetime.time(pending["hour"], minute), tzinfo=TEHRAN
            )
        except (KeyError, ValueError, TypeError):
            await callback_query.answer("زمان انتخابی معتبر نیست.", show_alert=True)
            return
        if not 0 <= minute <= 59:
            await callback_query.answer("دقیقه نامعتبر است.", show_alert=True)
            return
        if local_dt <= datetime.datetime.now(TEHRAN):
            pending["step"] = "hour"
            user_states[uid] = "poll_wizard_hour"
            await callback_query.answer("این زمان گذشته؛ ساعت دیگری انتخاب کن.", show_alert=True)
            await callback_query.message.edit_text(
                "زمانی که انتخاب کردی گذشته است.\n"
                "لطفاً یک ساعت تازه از گزینه‌های زیر انتخاب کن؛ سپس دقیقهٔ ارسال را مشخص می‌کنی.\n"
                "ساعت‌ها بر اساس زمان تهران نمایش داده می‌شوند.",
                reply_markup=hour_keyboard(uid)
            )
            return
        await callback_query.answer("زمان‌بندی ثبت شد.")
        await _finish_poll_wizard(
            callback_query, uid, pending_actions, user_states, int(local_dt.timestamp())
        )
        return

    if action == "backdate":
        if pending.get("step") != "hour":
            await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
            return
        year, month = pending.get("jalali_year"), pending.get("jalali_month")
        pending.update(step="calendar", cal_year=year, cal_month=month)
        user_states[uid] = "poll_wizard_calendar"
        await callback_query.answer(" ")
        await callback_query.message.edit_text(
            "📅 تاریخ شمسی ارسال را از تقویم انتخاب کن.\n"
            "با دکمه‌های «‹» و «›» ماه را عوض کن و روی روز دلخواه بزن.\n"
            "زمان‌بندی بر اساس ساعت رسمی تهران انجام می‌شود.",
            reply_markup=calendar_keyboard(uid, year, month)
        )
        return

    if action == "backhour":
        if pending.get("step") != "minute":
            await callback_query.answer("این مرحله منقضی شده است.", show_alert=True)
            return
        pending["step"] = "hour"
        user_states[uid] = "poll_wizard_hour"
        await callback_query.answer(" ")
        await callback_query.message.edit_text(
            "ساعت ارسال را از دکمه‌های زیر انتخاب کن (ساعت ۲۴ ساعته، از ۰۰ تا ۲۳).\n"
            "بعد از انتخاب ساعت، دقیقهٔ دقیق ارسال را مشخص می‌کنی.",
            reply_markup=hour_keyboard(uid)
        )
        return

    await callback_query.answer("این گزینه شناخته نشد.", show_alert=True)


async def cancel_poll(callback_query, pending_actions,  user_states):
    target_uid = int(callback_query.data.split("_")[2])

    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    if target_uid in user_states and user_states[target_uid] == 'confirm_poll':
        del user_states[target_uid]
    if target_uid in pending_actions:
        pending_actions.pop(target_uid)

    await callback_query.message.edit_text(
        "❌ **ایجاد نظرسنجی لغو شد**",
        reply_markup=None
    )
    await callback_query.answer("عملیات لغو شد")
    return


async def confirm_delclass(callback_query, pending_actions,  user_states):
    target_uid = int(callback_query.data.split("_")[2])
    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    pending = pending_actions.get(target_uid)
    if not pending or pending.get('kind') != 'delete_class':
        await callback_query.answer("اطلاعات یافت نشد!", show_alert=True)
        return

    class_name = pending['class_name']
    await callback_query.answer("در حال حذف...")

    success, result_msg = delete_class(class_name)

    if target_uid in user_states:
        del user_states[target_uid]
    if target_uid in pending_actions:
        pending_actions.pop(target_uid)

    await callback_query.message.edit_text(result_msg, reply_markup=None)
    return


async def cancel_delclass(callback_query, pending_actions,  user_states):
    target_uid = int(callback_query.data.split("_")[2])
    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    if target_uid in user_states:
        del user_states[target_uid]
    if target_uid in pending_actions:
        pending_actions.pop(target_uid)

    await callback_query.message.edit_text(
        "❌ عملیات حذف کلاس لغو شد.", reply_markup=None)
    await callback_query.answer("عملیات لغو شد")
    return


async def confirm_sendmsg(callback_query, pending_actions, user_states, client):
    target_uid = int(callback_query.data.split("_")[2])
    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    pending = pending_actions.get(target_uid)
    if not pending or pending.get('kind') != 'send_message':
        await callback_query.answer(
            "اطلاعات یافت نشد یا منقضی شده!", show_alert=True)
        return

    await callback_query.answer("در حال ارسال پیام...")

    class_name = pending['class_name']
    message_text = pending['message_text']
    user_ids = pending['user_ids']

    success_count = 0
    fail_count = 0
    fail_details = []

    for uid in user_ids:
        try:
            user_name = get_user_name(uid) or "کاربر"
            custom_text = message_text.replace("{name}", user_name)
            custom_text = custom_text.replace("{id}", str(uid))

            await client.send_message(uid, custom_text)

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

    await callback_query.message.edit_text(report, reply_markup=None)
    return


async def cancel_sendmsg(callback_query, pending_actions, user_states):
    target_uid = int(callback_query.data.split("_")[2])
    if callback_query.author.id != target_uid:
        await callback_query.answer(
            "این درخواست برای شما نیست!", show_alert=True)
        return

    if target_uid in user_states:
        del user_states[target_uid]
    if target_uid in pending_actions:
        pending_actions.pop(target_uid)

    await callback_query.message.edit_text(
        "❌ ارسال پیام لغو شد.", reply_markup=None)
    await callback_query.answer("عملیات لغو شد")
    return


async def voting(callback_query, pending_actions, user_states, client):
    try:
        data = callback_query.data.split(":")
        if len(data) != 3:
            await callback_query.answer("داده نامعتبر", show_alert=True)
            return

        pid = int(data[0])
        q_index = int(data[1])
        value = data[2]

        author = callback_query.author
        uid = author.id

        poll_type = get_poll_type(pid)
        if not poll_type:
            await callback_query.answer("نظرسنجی منقضی شده", show_alert=True)
            return

        if not is_poll_active(pid):
            await callback_query.answer(
                "این نظرسنجی دیگر فعال نیست.", show_alert=True)
            return

        poll_class = get_poll_class(pid)
        if poll_class is not None:
            user_classes = get_user_classes(uid)
            if poll_class not in user_classes:
                await callback_query.answer(
                    "شما مجاز به پاسخ به این نظرسنجی نیستید.", show_alert=True)
                del user_states[uid]
                pending_actions.pop(uid, None)
                return

        q_id = get_question_id(pid, q_index)
        if not q_id:
            await callback_query.answer("سوال نامعتبر", show_alert=True)
            return

        username = author.username or ""
        db_name = get_user_name(uid) or author.first_name or ""

        if poll_type == 'score':
            vote(pid, q_id, value, uid, username, db_name)
            await client.edit_message_text(
                callback_query.chat_instance,
                callback_query.message.id,
                "با تشکر، نظر شما ثبت شد."
            )

        elif poll_type == 'text':
            if value != "text":
                await callback_query.answer("داده نامعتبر", show_alert=True)
                return

            await client.edit_message_text(
                callback_query.chat_instance,
                callback_query.message.id,
                "لطفا پاسخ خود را ارسال کنید."
            )
            user_states[uid] = 'waiting_for_text'
            pending_actions[uid] = {'pid': pid, 'q_id': q_id}
    except Exception as e:
        e = str(e);
        if "UNIQUE" in e:
            await callback_query.answer("شما قبلا به این نظرسنجی پاسخ داده اید.", show_alert=True)
            await client.edit_message_text(
                callback_query.chat_instance,
                callback_query.message.id,
                "شما قبلا به این نظرسنجی پاسخ داده اید."
            )
            return

        print("callback error:", e)


async def on_callback_query(callback_query, settings, client, pending_actions, user_states):
    print("Callback received! data:", callback_query.data)

    if callback_query.data.startswith("gm:"):
        await get_money_wizard_callback(callback_query, settings, pending_actions, user_states)
        return

    if callback_query.data.startswith("pw:"):
        await poll_wizard_callback(callback_query, settings, pending_actions, user_states)
        return

    if callback_query.data.startswith("confirm_poll_") and (
            callback_query.author.id not in settings.owners
            and callback_query.author.id not in settings.admins):
        await callback_query.answer("دسترسی شما به این عملیات لغو شده است.", show_alert=True)
        return

    if callback_query.data.startswith("confirm_pay_"):
        await confirm_pay(callback_query, pending_actions,
                          client, settings, user_states)
        return

    elif callback_query.data.startswith("cancel_pay_"):
        await cancel_pay(callback_query, pending_actions,  user_states)
        return

    elif callback_query.data.startswith("confirm_poll_"):
        await confirm_poll(callback_query, pending_actions, client, user_states)
        return

    elif callback_query.data.startswith("cancel_poll_"):
        await cancel_poll(callback_query, pending_actions,  user_states)
        return

    elif callback_query.data.startswith("confirm_delclass_"):
        await confirm_delclass(callback_query, pending_actions,  user_states)
        return

    elif callback_query.data.startswith("cancel_delclass_"):
        await cancel_delclass(callback_query, pending_actions,  user_states)
        return

    elif callback_query.data.startswith("confirm_sendmsg_"):
        await confirm_sendmsg(callback_query, pending_actions, user_states, client)
        return

    elif callback_query.data.startswith("cancel_sendmsg_"):
        await cancel_sendmsg(callback_query, pending_actions, user_states)
        return

    else:
        await voting(callback_query, pending_actions, user_states, client)
