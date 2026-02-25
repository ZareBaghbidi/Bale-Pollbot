from balethon.objects import InlineKeyboard

from app.db.cruds.classes import get_class_id_by_name, get_users_in_class
from app.db.cruds.polls import do_activate_poll, get_poll_class, get_poll_type, stop_poll
from app.db.cruds.questions import get_questions


def send_poll(client, uid, pid):
    poll_type = get_poll_type(pid)
    if not poll_type:
        return

    questions = get_questions(pid)

    for q_index, q_id, q_text in questions:
        if poll_type == 'score':
            kb = InlineKeyboard(
                [("1", f"{pid}:{q_index}:1"),
                 ("2", f"{pid}:{q_index}:2"),
                 ("3", f"{pid}:{q_index}:3"),
                 ("4", f"{pid}:{q_index}:4"),
                 ("5", f"{pid}:{q_index}:5")],
                [("6", f"{pid}:{q_index}:6"),
                 ("7", f"{pid}:{q_index}:7"),
                 ("8", f"{pid}:{q_index}:8"),
                 ("9", f"{pid}:{q_index}:9"),
                 ("10", f"{pid}:{q_index}:10")]
            )
        else:
            kb = InlineKeyboard(
                [("پاسخ دادن", f"{pid}:{q_index}:text")]
            )

        try:
            client.send_message(uid, q_text, reply_markup=kb)
        except Exception as e:
            print("send_poll error:", e)

# ---------- ACTIVATE POLL ----------


def activate_poll(client, pid):
    do_activate_poll(pid)

    class_name = get_poll_class(pid)
    if class_name is None:
        print(f"⚠️ کلاس '{class_name}' برای نظرسنجی {pid} یافت نشد.")
        return

    class_id = get_class_id_by_name(class_name)
    if not class_id:
        return
    users_to_send = get_users_in_class(class_id)

    for u in users_to_send:
        send_poll(client, u, pid)

    print("Poll activated PID:", pid)


# ---------- STOP POLL ----------


def stop_poll_by_pid(pid):
    try:
        stop_poll(pid)
        print("Poll stopped:", pid)
        return True
    except Exception as e:
        print("Stop error:", e)
        return False
