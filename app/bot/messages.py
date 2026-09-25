WRONG_SEND_MESSAGE_HELP = (
    "❌ *فرمت صحیح:*\n"
    "`send_message <نام کلاس>`\n"
    "`<متن پیام (می‌تواند چند خط باشد)>`\n\n"
    "مثال:\n"
    "send_message 05\n"
    "سلام بر کلاس ۰۵\nجلسه فردا ساعت ۱۰"
)

WRONG_REMOVE_FROM_CLASS_HELP = (
    "📝 *فرمت دستور:*\n"
    "remove_from_class <نام کلاس> <آیدی کاربر>\n"
    "*مثال:*\n"
    "remove_from_class 05 123456789"
)

CREATE_POLL_HELP = (
    "برای ساخت نظرسنجی فقط `create_poll` را بفرست.\n"
    "سپس نوع نظرسنجی، کلاس، متن سوال و زمان ارسال را با دکمه‌ها انتخاب می‌کنی."
)

ADMIN_HELP = (
    "🛡 *راهنمای ادمین*\n\n"
    "دسترسی ادمین محدود است و فقط این دستورها را دارد:\n"
    "• `create_poll` → ساخت نظرسنجی با انتخاب نوع و کلاس؛ پس از تقویم، زمان را به شکل `h:m` بفرست (مثلاً `18:05`)\n"
    "• `list_classes` → دیدن کلاس‌ها\n"
    "• `help` → همین راهنما\n\n"
    "برای ثبت‌نام، نامت را در پاسخ به پیام ربات بفرست."
)

OWNER_HELP = (
    "👑 *راهنمای اونر*\n\n"
    "اونر دسترسی کامل دارد.\n\n"
    "*بخش اونر*\n"
    "• `roles` → دیدن اونرها و ادمین‌ها\n"
    "• `add_admin <شناسه>` → افزودن ادمین محدود\n"
    "• `remove_admin <شناسه>` → حذف ادمین محدود\n"
    "• فهرست اونرها فقط از `OWNERS` در فایل `.env` تغییر می‌کند.\n\n"
    "*بخش ادمین*\n"
    "• `create_poll` → ساخت نظرسنجی تعاملی؛ پس از تقویم، زمان را به شکل `h:m` بفرست (مثلاً `18:05`)\n"
    "• `list_classes` → دیدن کلاس‌ها\n\n"
    "*کاربران و کلاس‌ها*\n"
    "• `users` یا `list_users` → فهرست کاربران\n"
    "• `add_users` → افزودن کاربران به کلاس\n"
    "• `create_class <نام>`، `list_classes`، `class_users <نام>`\n"
    "• `remove_from_class <کلاس> <شناسه>`، `delete_class <نام>`\n"
    "• `send_message <کلاس>` و متن پیام در خط بعد\n\n"
    "*نظرسنجی‌ها*\n"
    "• `stop <شناسه>`، `clear`، `list_polls`، `view_responses <شناسه>`\n"
    "• `scheduled_polls` → دیدن زمان‌بندی‌های در انتظار\n"
    "• `cancel_scheduled <شناسه‌زمان‌بندی>` → لغو زمان‌بندی (شناسه در فهرست بالا)\n"
    "• `report` → گزارش نظرسنجی‌های فعال\n"
    "• `export_votes` → دریافت خروجی Excel\n\n"
    "*پرداخت‌ها و صورتحساب‌ها*\n"
    "• `get_money` → ساخت مرحله‌ای صورتحساب با انتخاب کلاس از دکمه‌ها\n"
    "• `payments`، `user_payments <شناسه>`، `payments_filter days=7 min=5000`\n"
    "• `invoices`، `invoices_filter days=7 status=paid class=05`\n"
    "• `invoices_class <نام>`، `invoices_unpaid`، `invoice_stats`\n\n"
    "• `help` → نمایش این راهنما"
)
