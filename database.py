import sqlite3
from datetime import datetime


DB_NAME = "database.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


# ================= INIT DATABASE ================= #

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        model TEXT DEFAULT 'google/gemini-2.5-flash-image',
        format TEXT DEFAULT '1:1',
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ================= USER FUNCTIONS ================= #

def add_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO users 
        (user_id, balance, created_at) 
        VALUES (?, ?, ?)
        """,
        (user_id, 50, datetime.utcnow().isoformat())  # 50 тестовых кредитов
    )

    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance, model, format FROM users WHERE user_id = ?",
        (user_id,)
    )

    user = cursor.fetchone()
    conn.close()
    return user


def get_users_count():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]

    conn.close()
    return count


# ================= UPDATE SETTINGS ================= #

def update_model(user_id: int, model: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET model = ? WHERE user_id = ?",
        (model, user_id)
    )

    conn.commit()
    conn.close()


def update_format(user_id: int, format_value: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET format = ? WHERE user_id = ?",
        (format_value, user_id)
    )

    conn.commit()
    conn.close()


# ================= BALANCE ================= #

def update_balance(user_id: int, amount: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )

    conn.commit()
    conn.close()


def deduct_balance(user_id: int, amount: int):
    conn = get_connection()
    cursor = conn.cursor()

    # защита от отрицательного баланса
    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )
    result = cursor.fetchone()

    if result:
        current_balance = result[0]
        if current_balance >= amount:
            cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id)
            )
            conn.commit()

    conn.close()
