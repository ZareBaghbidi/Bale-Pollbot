"""Inline keyboards for the poll-creation wizard and Jalali date picker."""
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime
from balethon.objects import InlineKeyboard

TEHRAN = ZoneInfo("Asia/Tehran")
JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)
WEEKDAYS = ("ش", "ی", "د", "س", "چ", "پ", "ج")
_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(value):
    return str(value).translate(_DIGITS)


def poll_type_keyboard(uid):
    return InlineKeyboard(
        [("امتیازی (۱ تا ۱۰)", f"pw:type:{uid}:score")],
        [("پاسخ متنی", f"pw:type:{uid}:text")],
        [("لغو", f"pw:cancel:{uid}")],
    )


def class_keyboard(uid, classes):
    rows = [[(name, f"pw:class:{uid}:{class_id}")]
            for class_id, name in classes]
    rows.append([("لغو", f"pw:cancel:{uid}")])
    return InlineKeyboard(*rows)


def schedule_keyboard(uid):
    return InlineKeyboard(
        [("شروع فوری", f"pw:now:{uid}")],
        [("زمان‌بندی با تقویم", f"pw:calendar:{uid}")],
        [("لغو", f"pw:cancel:{uid}")],
    )


def calendar_keyboard(uid, year, month):
    date = jdatetime.date(year, month, 1)
    today = jdatetime.date.fromgregorian(date=datetime.now(TEHRAN).date())
    month_length = 31 if month <= 6 else 30 if month <= 11 else (30 if date.isleap() else 29)
    # Bale lays buttons out left-to-right. Reverse each visual row so the
    # calendar reads right-to-left for Persian users.
    rows = [[("›", f"pw:month:{uid}:{year}:{month}:next"),
             (f"{JALALI_MONTHS[month - 1]} {fa_num(year)}", f"pw:noop:{uid}"),
             ("‹", f"pw:month:{uid}:{year}:{month}:prev")]]
    rows.append([(day, f"pw:noop:{uid}") for day in reversed(WEEKDAYS)])

    # jdatetime's weekday is Saturday=0 through Friday=6.
    cells = [("·", f"pw:noop:{uid}")] * date.weekday()
    for day in range(1, month_length + 1):
        selected = jdatetime.date(year, month, day)
        action = "day" if selected >= today else "past"
        cells.append((fa_num(day), f"pw:{action}:{uid}:{year}:{month}:{day}"))
    while len(cells) % 7:
        cells.append(("·", f"pw:noop:{uid}"))
    rows.extend([list(reversed(cells[i:i + 7]))
                 for i in range(0, len(cells), 7)])
    rows.append([("لغو", f"pw:cancel:{uid}")])
    return InlineKeyboard(*rows)


def hour_keyboard(uid):
    hours = [(fa_num(f"{hour:02d}"), f"pw:hour:{uid}:{hour}")
             for hour in range(24)]
    rows = [hours[i:i + 6] for i in range(0, len(hours), 6)]
    rows.append([("بازگشت به تقویم", f"pw:backdate:{uid}"),
                 ("لغو", f"pw:cancel:{uid}")])
    return InlineKeyboard(*rows)


def minute_keyboard(uid):
    minutes = [(fa_num(f"{minute:02d}"), f"pw:minute:{uid}:{minute}")
               for minute in range(60)]
    rows = [minutes[i:i + 10] for i in range(0, len(minutes), 10)]
    rows.append([("بازگشت به ساعت", f"pw:backhour:{uid}"),
                 ("لغو", f"pw:cancel:{uid}")])
    return InlineKeyboard(*rows)


def current_jalali_month():
    today = jdatetime.date.fromgregorian(date=datetime.now(TEHRAN).date())
    return today.year, today.month
