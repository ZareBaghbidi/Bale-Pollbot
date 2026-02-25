from balethon.objects import LabeledPrice

from app.db.cruds.classes import get_class_id_by_name, get_users_in_class
from app.db.cruds.invoices import get_invoice_by_payload, save_invoice, update_invoice_status
from app.db.cruds.payments import save_payment
from app.db.cruds.users import get_user_name

import time
import datetime
import traceback


# ---------- PAYMENT VALIDATION ----------

def validate_payment_input(amount_str, class_name, title, description):
    errors = []

    amount_rial = _parse_amount(amount_str, errors)

    class_id, users_count = _validate_class_and_users(class_name, errors)

    title = _validate_title(title, errors)
    description = _validate_description(description, errors)

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'amount_rial': amount_rial,
        'class_id': class_id,
        'class_name': class_name.strip(),
        'title': title,
        'description': description,
        'users_count': users_count
    }


def _parse_amount(amount_str, errors):
    try:
        amount_toman = int(amount_str.strip())
        if amount_toman <= 0:
            errors.append("❌ مبلغ باید بزرگتر از صفر باشد")
            return None
        return amount_toman * 10
    except ValueError:
        errors.append("❌ مبلغ باید یک عدد معتبر باشد (مثال: 5000)")
        return None


def _validate_class_and_users(class_name, errors):
    class_id = get_class_id_by_name(class_name.strip())
    if class_id is None:
        errors.append(f"❌ کلاس '{class_name}' یافت نشد")
        return None, 0

    users_in_class = get_users_in_class(class_id)
    users_count = len(users_in_class)
    if users_count == 0:
        errors.append(f"❌ هیچ کاربری در کلاس '{class_name}' وجود ندارد")

    return class_id, users_count


def _validate_title(title, errors):
    title = title.strip()
    if not title:
        errors.append("❌ عنوان نمی‌تواند خالی باشد")
    elif len(title) > 32:
        errors.append("❌ عنوان نباید بیشتر از 32 کاراکتر باشد")
    return title


def _validate_description(description, errors):
    description = description.strip()
    if not description:
        errors.append("❌ توضیحات نمی‌تواند خالی باشد")
    elif len(description) > 255:
        errors.append("❌ توضیحات نباید بیشتر از 255 کاراکتر باشد")
    return description


# ---------- SEND PAY ------------

def send_pay_to_class(client, settings, class_name, amount_rial, title, description):
    try:
        class_id = get_class_id_by_name(class_name)
        if class_id is None:
            return False, f"کلاس '{class_name}' یافت نشد."

        users_in_class = get_users_in_class(class_id)
        if not users_in_class:
            return False, f"هیچ کاربری در کلاس '{class_name}' وجود ندارد."

        success_count, fail_count, fail_details = _send_invoices_to_users(
            client=client,
            settings=settings,
            class_name=class_name,
            users_in_class=users_in_class,
            amount_rial=amount_rial,
            title=title,
            description=description
        )

        result_msg = _build_send_result_message(
            class_name=class_name,
            users_in_class=users_in_class,
            amount_rial=amount_rial,
            success_count=success_count,
            fail_count=fail_count,
            fail_details=fail_details
        )

        return True, result_msg

    except Exception as e:
        error_msg = f"❌ خطای سیستمی: {str(e)[:100]}"
        print(f"خطا در send_pay_to_class: {e}")
        return False, error_msg


def _send_invoices_to_users(client, settings, class_name, users_in_class, amount_rial, title, description):
    success_count = 0
    fail_count = 0
    fail_details = []

    for uid in users_in_class:
        try:
            payload = _build_invoice_payload(class_name, uid)

            save_invoice(
                user_id=uid,
                class_name=class_name,
                amount=amount_rial,
                title=title,
                description=description,
                payload=payload,
                provider_token=settings.provider_token
            )

            client.send_invoice(
                chat_id=uid,
                title=title,
                description=description,
                payload=payload,
                provider_token=settings.provider_token,
                prices=[LabeledPrice(label=title, amount=amount_rial)],
                need_name=True,
                need_phone_number=True
            )
            success_count += 1
            time.sleep(0.3)

        except Exception as e:
            fail_count += 1
            user_name = get_user_name(uid) or f"کاربر {uid}"
            fail_details.append(f"{user_name}: {str(e)[:50]}")
            print(f"خطا در ارسال به {uid}: {e}")

    return success_count, fail_count, fail_details


def _build_invoice_payload(class_name, uid):
    return f"class_{class_name}_user_{uid}_time_{int(time.time())}"


def _build_send_result_message(class_name, users_in_class, amount_rial, success_count, fail_count, fail_details):
    result_msg = f"📊 **نتیجه ارسال صورتحساب:**\n"
    result_msg += f"🎯 کلاس: {class_name}\n"
    result_msg += f"👥 تعداد کاربران: {len(users_in_class)}\n"
    result_msg += f"💰 مبلغ هر صورتحساب: {amount_rial // 10:,} تومان\n"
    result_msg += f"✅ موفق: {success_count} کاربر\n"
    result_msg += f"❌ ناموفق: {fail_count} کاربر\n"

    if fail_details:
        result_msg += "**جزئیات خطاها:**\n"
        for detail in fail_details[:3]:
            result_msg += f"• {detail}\n"
        if len(fail_details) > 3:
            result_msg += f"• و {len(fail_details) - 3} خطای دیگر...\n"

    return result_msg


# ---------- PAYMENT HANDLER ----------

def process_successful_payment(client, settings, message):
    try:
        uid = message.author.id
        payment = message.successful_payment

        _log_success_payment(uid, payment)

        name, phone, email = _extract_order_info(payment)

        payment_id = save_payment(
            user_id=uid,
            amount=payment.total_amount,
            payload=payment.invoice_payload,
            name=name,
            phone=phone,
            email=email,
            telegram_charge_id=payment.telegram_payment_charge_id,
            provider_charge_id=payment.provider_payment_charge_id,
            status='completed'
        )

        print(f"💾 پرداخت با ID {payment_id} ذخیره شد")

        invoice_updated = update_invoice_status(
            payment.invoice_payload, 'paid', payment_id)
        print(f"📄 وضعیت صورتحساب بروزرسانی شد: {invoice_updated}")

        invoice_info = get_invoice_by_payload(payment.invoice_payload)

        user_msg = _build_user_payment_message(
            payment, invoice_info, name, phone)
        message.reply(user_msg)

        admin_msg = _build_admin_payment_message(uid, payment, invoice_info)
        _notify_admins(client, settings.admins, admin_msg)

        return True

    except Exception as e:
        print(f"❌ خطا در پردازش پرداخت: {e}")
        traceback.print_exc()
        return False


def _log_success_payment(uid, payment):
    print(f"🎉 پرداخت موفق از کاربر {uid}")
    print(f"   مبلغ: {payment.total_amount} ریال")
    print(f"   شناسه: {payment.invoice_payload}")


def _extract_order_info(payment):
    order_info = payment.order_info if hasattr(payment, 'order_info') else None
    name = order_info.name if order_info and hasattr(
        order_info, 'name') else None
    phone = order_info.phone_number if order_info and hasattr(
        order_info, 'phone_number') else None
    email = order_info.email if order_info and hasattr(
        order_info, 'email') else None
    return name, phone, email


def _build_user_payment_message(payment, invoice_info, name, phone):
    user_msg = f"""✅ **پرداخت شما با موفقیت ثبت شد!**
💰 مبلغ: {payment.total_amount//10:,} تومان
🆔 شماره پیگیری: {payment.telegram_payment_charge_id}
📅 زمان: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
"""

    if invoice_info:
        user_msg += f"""
📝 عنوان: {invoice_info.get('title', '')}
🏫 کلاس: {invoice_info.get('class_name', '')}
"""

    if name:
        user_msg += f"👤 نام: {name}\n"
    if phone:
        user_msg += f"📞 تلفن: {phone}\n"

    user_msg += "\nبا تشکر از پرداخت شما! 🙏"
    return user_msg


def _build_admin_payment_message(uid, payment, invoice_info):
    user_name = get_user_name(uid) or f"کاربر {uid}"
    admin_msg = f"""💰 **پرداخت جدید ثبت شد**

👤 کاربر: {user_name} (آیدی: {uid})
💳 مبلغ: {payment.total_amount//10:,} تومان
🆔 شماره پیگیری: {payment.telegram_payment_charge_id}
📝 Payload: {payment.invoice_payload}
📅 زمان: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}
"""

    if invoice_info:
        admin_msg += f"🏫 کلاس: {invoice_info.get('class_name', 'نامشخص')}\n"
        admin_msg += f"📋 عنوان: {invoice_info.get('title', 'نامشخص')}\n"

    return admin_msg


def _notify_admins(client, admin_ids, admin_msg):
    for admin_id in admin_ids:
        try:
            client.send_message(admin_id, admin_msg)
            print(f"📤 پیام پرداخت به ادمین {admin_id} ارسال شد")
        except Exception as e:
            print(f"❌ خطا در ارسال به ادمین {admin_id}: {e}")
