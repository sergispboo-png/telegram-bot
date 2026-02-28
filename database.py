import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Создание таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    model TEXT DEFAULT 'Nano-Banana',
    format TEXT DEFAULT '1:1'
)
""")

conn.commit()


def add_user(user_id: int):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)",
        (user_id, 50)  # даём 50₽ на тест
    )
    conn.commit()


def get_user(user_id: int):
    cursor.execute(
        "SELECT balance, model, format FROM users WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()


def update_model(user_id: int, model: str):
    cursor.execute(
        "UPDATE users SET model = ? WHERE user_id = ?",
        (model, user_id)
    )
    conn.commit()


def update_format(user_id: int, format_value: str):
    cursor.execute(
        "UPDATE users SET format = ? WHERE user_id = ?",
        (format_value, user_id)
    )
    conn.commit()


def update_balance(user_id: int, amount: int):
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()


def deduct_balance(user_id: int, amount: int):
    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
