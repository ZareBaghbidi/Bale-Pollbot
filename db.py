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
    cur.execute("INSERT INTO polls (type, class, active) VALUES (?, ?, 0)", (poll_type, class_))
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

# ---------- messages ----------
def save_msg(uid, username, name, text):
    c = conn()
    cur = c.cursor()
    cur.execute(
        "INSERT INTO messages (user_id, username, name, text) VALUES (?, ?, ?, ?)",
        (uid, username, name, text)
    )
    c.commit()
    cur.close()
    c.close()

# ---------- score distribution ----------
def get_score_distribution(pid, q_id):
    """Returns {score: count} for a specific question in a score poll"""
    c = conn()
    cur = c.cursor()
    cur.execute("""
        SELECT CAST(value AS INTEGER), COUNT(*)
        FROM votes
        WHERE poll_id = ? AND question_id = ?
        GROUP BY CAST(value AS INTEGER)
        ORDER BY CAST(value AS INTEGER)
    """, (pid, q_id))
    rows = cur.fetchall()
    cur.close()
    c.close()
    return {score: count for score, count in rows}
