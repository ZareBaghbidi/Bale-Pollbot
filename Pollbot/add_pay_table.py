import sqlite3
import datetime

DB_NAME = "pollbot.db"

def conn():
    connection = sqlite3.connect(DB_NAME, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def create_invoices_table():
    c = conn()
    cur = c.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                        user_id INTEGER NOT NULL,
                                                        class_name TEXT,
                                                        amount INTEGER NOT NULL,
                                                        title TEXT NOT NULL,
                                                        description TEXT,
                                                        payload TEXT,
                                                        provider_token TEXT,
                                                        sent_at INTEGER,
                                                        status TEXT DEFAULT 'sent',  -- sent, delivered, paid, failed
                                                        paid_at INTEGER,
                                                        payment_id INTEGER,  -- پیوند به جدول payments در صورت پرداخت موفق
                                                        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL
                    )
                """)
    c.commit()
    cur.close()
    c.close()

create_invoices_table()