import sqlite3
import datetime

DB_NAME = "pollbot.db"

def conn():
    connection = sqlite3.connect(DB_NAME, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

# ---------- users ----------
def add_user(uid, name):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT OR IGNORE INTO users (chat_id, name) VALUES (?, ?)", (uid, name))
    c.commit()
    cur.close()
    c.close()

def get_users():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT chat_id FROM users")
    r = [row[0] for row in cur.fetchall()]
    cur.close()
    c.close()
    return r

def get_all_users_with_names():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT chat_id, name FROM users ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [(i+1, row['chat_id'], row['name'] or "بدون نام") for i, row in enumerate(rows)]

def get_user_name(uid):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT name FROM users WHERE chat_id=?", (uid,))
    r = cur.fetchone()
    cur.close()
    c.close()
    return r['name'] if r else None

def get_user_classes(uid):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT c.name
                FROM classes c
                         JOIN user_classes uc ON c.id = uc.class_id
                WHERE uc.user_id = ?
                """, (uid,))
    r = [row['name'] for row in cur.fetchall()]
    cur.close()
    c.close()
    return r

# ---------- classes ----------
def create_class(class_name):
    c = conn()
    cur = c.cursor()
    try:
        cur.execute("INSERT INTO classes (name) VALUES (?)", (class_name,))
        c.commit()
        class_id = cur.lastrowid
    except sqlite3.IntegrityError:
        class_id = None
    cur.close()
    c.close()
    return class_id

def get_all_classes():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id, name FROM classes ORDER BY name")
    r = cur.fetchall()
    cur.close()
    c.close()
    return [(row['id'], row['name']) for row in r]

def get_class_id_by_name(name):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id FROM classes WHERE name=?", (name,))
    r = cur.fetchone()
    cur.close()
    c.close()
    return r['id'] if r else None

def get_users_in_class(class_id):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT u.chat_id
                FROM users u
                         JOIN user_classes uc ON u.chat_id = uc.user_id
                WHERE uc.class_id = ?
                """, (class_id,))
    r = [row['chat_id'] for row in cur.fetchall()]
    cur.close()
    c.close()
    return r

def add_users_to_class(class_id, user_ids):
    c = conn()
    cur = c.cursor()
    data = [(uid, class_id) for uid in user_ids]
    cur.executemany("INSERT OR IGNORE INTO user_classes (user_id, class_id) VALUES (?, ?)", data)
    c.commit()
    cur.close()
    c.close()

# ---------- polls ----------
def create_poll(poll_type, class_=None):
    c = conn()
    cur = c.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO polls (type, class, active, created_at) VALUES (?, ?, 0, ?)", (poll_type, class_, now))
    pid = cur.lastrowid
    c.commit()
    cur.close()
    c.close()
    return pid

def stop_poll(pid):
    c = conn()
    cur = c.cursor()
    cur.execute("UPDATE polls SET active=0 WHERE id=?", (pid,))
    c.commit()
    cur.close()
    c.close()

def deactivate_old_polls(days=7):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    c = conn()
    cur = c.cursor()
    cur.execute("UPDATE polls SET active=0 WHERE active=1 AND created_at < ?", (cutoff_str,))
    affected = cur.rowcount
    c.commit()
    cur.close()
    c.close()
    return affected

def show_active_polls():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id, class, type FROM polls WHERE active=1")
    r = cur.fetchall()
    cur.close()
    c.close()
    return [(row[0], row[1], row[2]) for row in r]

def show_all_polls():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id, type, class, active, created_at FROM polls ORDER BY id DESC")
    r = cur.fetchall()
    cur.close()
    c.close()
    return [(row['id'], row['type'], row['class'], row['active'], row['created_at']) for row in r]

def get_poll_type(pid):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT type FROM polls WHERE id=?", (pid,))
    r = cur.fetchone()
    cur.close()
    c.close()
    return r['type'] if r else None

def get_poll_class(pid):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT class FROM polls WHERE id=?", (pid,))
    r = cur.fetchone()
    cur.close()
    c.close()
    return r['class'] if r else None

# ---------- questions ----------
def add_question(pid, index, text):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT INTO questions (poll_id, `index`, text) VALUES (?, ?, ?)", (pid, index, text))
    qid = cur.lastrowid
    c.commit()
    cur.close()
    c.close()
    return qid

def get_questions(pid):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT `index`, id, text FROM questions WHERE poll_id=? ORDER BY `index`", (pid,))
    r = cur.fetchall()
    cur.close()
    c.close()
    return [(row['index'], row['id'], row['text']) for row in r]

def get_question_id(pid, index):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id FROM questions WHERE poll_id=? AND `index`=? ", (pid, index))
    r = cur.fetchone()
    cur.close()
    c.close()
    return r['id'] if r else None

# ---------- votes ----------
def vote(pid, q_id, value, uid, username, name):
    c = conn()
    cur = c.cursor()
    cur.execute(
        "INSERT INTO votes (poll_id, question_id, value, user_id, username, name) VALUES (?, ?, ?, ?, ?, ?)",
        (pid, q_id, value, uid, username, name)
    )
    c.commit()
    cur.close()
    c.close()

def stats(pid):
    c = conn()
    cur = c.cursor()
    poll_type = get_poll_type(pid)
    if poll_type == 'score':
        cur.execute(
            "SELECT question_id, COUNT(*), SUM(CAST(value AS REAL)) FROM votes WHERE poll_id=? GROUP BY question_id",
            (pid,)
        )
        r = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    else:
        cur.execute(
            "SELECT question_id, COUNT(*), NULL FROM votes WHERE poll_id=? GROUP BY question_id",
            (pid,)
        )
        r = {row[0]: (row[1], None) for row in cur.fetchall()}
    cur.close()
    c.close()
    return r

def get_responses(pid):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT q.`index`, q.text, v.value, v.name, v.username
                FROM votes v
                         JOIN questions q ON v.question_id = q.id
                WHERE v.poll_id = ?
                ORDER BY q.`index`, v.id
                """, (pid,))
    r = cur.fetchall()
    cur.close()
    c.close()
    return [(row['index'], row['text'], row['value'], row['name'], row['username']) for row in r]

# ---------- tasks ----------
def add_task(ts, pid):
    c = conn()
    cur = c.cursor()
    run_at = datetime.datetime.fromtimestamp(ts)
    cur.execute(
        "INSERT INTO tasks (run_at, poll_id) VALUES (?, ?)",
        (run_at, pid)
    )
    tid = cur.lastrowid
    c.commit()
    cur.close()
    c.close()
    return tid

def next_task():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id, poll_id, strftime('%s', run_at) AS t FROM tasks ORDER BY run_at LIMIT 1")
    r = cur.fetchone()
    cur.close()
    c.close()
    if r:
        return {'id': r['id'], 'poll_id': r['poll_id'], 't': int(r['t'])}
    return None

def del_task(tid):
    c = conn()
    cur = c.cursor()
    cur.execute("DELETE FROM tasks WHERE id=?", (tid,))
    c.commit()
    cur.close()
    c.close()

# ---------- payments ----------
def save_payment(user_id, amount, payload, name=None, phone=None, email=None, telegram_charge_id=None, provider_charge_id=None, status='completed'):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                INSERT INTO payments
                (user_id, amount, payload, name, phone, email,
                 telegram_charge_id, provider_charge_id, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, amount, payload, name, phone, email, telegram_charge_id, provider_charge_id, int(datetime.datetime.now().timestamp()), status))
    pid = cur.lastrowid
    c.commit()
    cur.close()
    c.close()
    return pid

def get_payments_stats(days=None, min_amount=None):
    c = conn()
    cur = c.cursor()

    query = "SELECT COUNT(*) as count, SUM(amount) as total, COUNT(DISTINCT user_id) as unique_users FROM payments WHERE 1=1"
    params = []

    if days:
        timestamp_limit = int(datetime.datetime.now().timestamp()) - (days * 24 * 3600)
        query += " AND timestamp >= ?"
        params.append(timestamp_limit)

    if min_amount:
        query += " AND amount >= ?"
        params.append(min_amount)

    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    c.close()

    if row:
        return {
            'count': row['count'] or 0,
            'total': row['total'] or 0,
            'unique_users': row['unique_users'] or 0
        }
    return {'count': 0, 'total': 0, 'unique_users': 0}

def get_recent_payments(limit=10):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT p.*, u.name as user_name
                FROM payments p
                         LEFT JOIN users u ON p.user_id = u.chat_id
                ORDER BY p.timestamp DESC
                    LIMIT ?
                """, (limit,))
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]

def get_user_payments(user_id, limit=20):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT p.*, u.name as user_name
                FROM payments p
                         LEFT JOIN users u ON p.user_id = u.chat_id
                WHERE p.user_id = ?
                ORDER BY p.timestamp DESC
                    LIMIT ?
                """, (user_id, limit))
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]

def get_daily_payments_stats(days=30):
    c = conn()
    cur = c.cursor()
    timestamp_limit = int(datetime.datetime.now().timestamp()) - (days * 24 * 3600)
    cur.execute("""
                SELECT
                    DATE(datetime(p.timestamp, 'unixepoch')) as date,
                    COUNT(*) as count,
                    SUM(p.amount) as total
                FROM payments p
                WHERE p.timestamp >= ?
                GROUP BY DATE(datetime(p.timestamp, 'unixepoch'))
                ORDER BY date DESC
                    LIMIT 30
                """, (timestamp_limit,))
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]

# ---------- invoices ----------
def save_invoice(user_id, class_name, amount, title, description, payload, provider_token):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                INSERT INTO invoices
                (user_id, class_name, amount, title, description, payload, provider_token, sent_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, class_name, amount, title, description, payload, provider_token,
                      int(datetime.datetime.now().timestamp()), 'sent'))
    invoice_id = cur.lastrowid
    c.commit()
    cur.close()
    c.close()
    return invoice_id

def update_invoice_status(payload, status, payment_id=None):
    c = conn()
    cur = c.cursor()
    paid_at = int(datetime.datetime.now().timestamp()) if status == 'paid' else None
    cur.execute("""
                UPDATE invoices
                SET status = ?, paid_at = ?, payment_id = ?
                WHERE payload = ? AND status != 'paid'
                """, (status, paid_at, payment_id, payload))
    c.commit()
    updated = cur.rowcount > 0
    cur.close()
    c.close()
    return updated

def get_invoice_by_payload(payload):
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT * FROM invoices WHERE payload = ?
                """, (payload,))
    row = cur.fetchone()
    cur.close()
    c.close()
    return dict(row) if row else None

def get_all_invoices(days=None, status=None, class_name=None, limit=50):
    c = conn()
    cur = c.cursor()

    query = """
            SELECT i.*, u.name as user_name, p.telegram_charge_id
            FROM invoices i
                     LEFT JOIN users u ON i.user_id = u.chat_id
                     LEFT JOIN payments p ON i.payment_id = p.id
            WHERE 1=1 \
            """
    params = []

    if days:
        timestamp_limit = int(datetime.datetime.now().timestamp()) - (days * 24 * 3600)
        query += " AND i.sent_at >= ?"
        params.append(timestamp_limit)

    if status:
        query += " AND i.status = ?"
        params.append(status)

    if class_name:
        query += " AND i.class_name = ?"
        params.append(class_name)

    query += " ORDER BY i.sent_at DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]

def get_invoice_stats():
    c = conn()
    cur = c.cursor()
    cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent_count,
                    SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                    SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT class_name) as unique_classes
                FROM invoices
                """)
    row = cur.fetchone()
    cur.close()
    c.close()

    if row:
        return {
            'total': row['total'] or 0,
            'sent': row['sent_count'] or 0,
            'paid': row['paid_count'] or 0,
            'paid_amount': row['paid_amount'] or 0,
            'unique_users': row['unique_users'] or 0,
            'unique_classes': row['unique_classes'] or 0
        }
    return {'total': 0, 'sent': 0, 'paid': 0, 'paid_amount': 0, 'unique_users': 0, 'unique_classes': 0}

def get_class_invoice_summary(class_name=None):
    c = conn()
    cur = c.cursor()

    query = """
            SELECT
                class_name,
                COUNT(*) as total_invoices,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount,
                COUNT(DISTINCT user_id) as total_users,
                MIN(sent_at) as first_sent,
                MAX(sent_at) as last_sent
            FROM invoices \
            """
    params = []

    if class_name:
        query += " WHERE class_name = ?"
        params.append(class_name)

    query += " GROUP BY class_name ORDER BY class_name"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]

def get_unpaid_invoices(days=None):
    c = conn()
    cur = c.cursor()

    query = """
            SELECT i.*, u.name as user_name
            FROM invoices i
                     LEFT JOIN users u ON i.user_id = u.chat_id
            WHERE i.status != 'paid' \
            """
    params = []

    if days:
        timestamp_limit = int(datetime.datetime.now().timestamp()) - (days * 24 * 3600)
        query += " AND i.sent_at >= ?"
        params.append(timestamp_limit)

    query += " ORDER BY i.sent_at DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]

def get_grouped_invoices(days=None, status=None, class_name=None, limit=50):
    c = conn()
    cur = c.cursor()

    query = """
            SELECT
                class_name,
                title,
                amount,
                COUNT(*) as total_count,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount,
                MIN(sent_at) as first_sent,
                MAX(sent_at) as last_sent
            FROM invoices
            WHERE 1=1
            """
    params = []

    if days:
        timestamp_limit = int(datetime.datetime.now().timestamp()) - (days * 24 * 3600)
        query += " AND sent_at >= ?"
        params.append(timestamp_limit)

    if status:
        query += " AND status = ?"
        params.append(status)

    if class_name:
        query += " AND class_name = ?"
        params.append(class_name)

    query += " GROUP BY class_name, title, amount ORDER BY last_sent DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    c.close()
    return [dict(row) for row in rows]
def get_class_users_with_names(class_name):
    c = conn()
    cur = c.cursor()

    # ابتدا ID کلاس را پیدا می‌کنیم
    cur.execute("SELECT id FROM classes WHERE name=?", (class_name,))
    class_row = cur.fetchone()

    if not class_row:
        cur.close()
        c.close()
        return None  # کلاس وجود ندارد

    class_id = class_row['id']

    # دریافت کاربران کلاس با نام‌هایشان (بدون username)
    cur.execute("""
                SELECT u.chat_id, u.name
                FROM users u
                         JOIN user_classes uc ON u.chat_id = uc.user_id
                WHERE uc.class_id = ?
                ORDER BY u.name
                """, (class_id,))

    rows = cur.fetchall()
    cur.close()
    c.close()

    return [(row['chat_id'], row['name'] or "بدون نام") for row in rows]

def is_poll_active(pid):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT active FROM polls WHERE id=?", (pid,))
    r = cur.fetchone()
    cur.close()
    c.close()
    return r['active'] == 1 if r else False

def remove_user_from_class(class_name, user_id):
    c = conn()
    cur = c.cursor()
    # ابتدا شناسه کلاس را پیدا می‌کنیم
    class_id = get_class_id_by_name(class_name)
    if class_id is None:
        cur.close()
        c.close()
        return False, "❌ کلاس یافت نشد"

    # حذف کاربر از کلاس
    cur.execute("DELETE FROM user_classes WHERE user_id=? AND class_id=?", (user_id, class_id))
    affected = cur.rowcount
    c.commit()
    cur.close()
    c.close()

    if affected > 0:
        return True, f"✅ کاربر {user_id} از کلاس '{class_name}' حذف شد."
    else:
        return False, f"❌ کاربر {user_id} در کلاس '{class_name}' یافت نشد."

def delete_class(class_name):
    conn_obj = conn()
    cursor = conn_obj.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("SELECT id FROM classes WHERE name=?", (class_name,))
        row = cursor.fetchone()
        if not row:
            conn_obj.rollback()
            return False, "❌ کلاس یافت نشد"
        class_id = row['id']

        cursor.execute("SELECT id FROM polls WHERE class=?", (class_name,))
        poll_ids = [r['id'] for r in cursor.fetchall()]

        for pid in poll_ids:
            cursor.execute("DELETE FROM tasks WHERE poll_id=?", (pid,))

        for pid in poll_ids:
            cursor.execute("DELETE FROM votes WHERE poll_id=?", (pid,))

        for pid in poll_ids:
            cursor.execute("DELETE FROM questions WHERE poll_id=?", (pid,))

        cursor.execute("DELETE FROM polls WHERE class=?", (class_name,))

        cursor.execute("DELETE FROM invoices WHERE class_name=?", (class_name,))

        cursor.execute("DELETE FROM user_classes WHERE class_id=?", (class_id,))

        cursor.execute("DELETE FROM classes WHERE id=?", (class_id,))

        conn_obj.commit()
        return True, f"✅ کلاس '{class_name}' و تمام نظرسنجی‌ها و صورتحساب‌های مربوطه حذف شدند."
    except Exception as e:
        conn_obj.rollback()
        return False, f"❌ خطا در حذف کلاس: {str(e)}"
    finally:
        cursor.close()
        conn_obj.close()