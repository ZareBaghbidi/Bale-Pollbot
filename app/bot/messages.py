WRONG_SEND_MESSAGE_HELP = ("❌ *فرمت صحیح:*\n"
                           "`send_message <نام کلاس>`\n"
                           "`<متن پیام (می‌تواند چند خط باشد)>`\n\n"
                           "مثال:\n"
                           "send_message 05\n"
                           "سلام بر کلاس ۰۵\nجلسه فردا ساعت ۱۰"
                           )

WRONG_REMOVE_FROM_CLASS_HELP = ("📝 *فرمت دستور:*\n"
                                "remove_from_class <نام کلاس> <آیدی کاربر>\n"
                                "*مثال:*\n"
                                "remove_from_class 05 123456789"
                                )
CREATE_POLL_HELP=("فرمت: create_poll <type> <class> <ts> <question>\n"
                                  "type: score یا text\n"
                                  "class: نام کلاس\n"
                                  "ts: timestamp یونیکس یا . برای شروع فوری\n"
                                  "مثال: create_poll score 05 . ارزیابی امروز چطور بود؟")