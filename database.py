import sqlite3

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# ================= USERS ================= #

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    model TEXT DEFAULT 'google/gemini-2.5-flash-image',
    format TEXT DEFAULT '1:1'
)
""")

# ================= PAYMENTS ================= #

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ================= GENERATIONS ================= #

cursor.execute("""
CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# ================= USER FUNCTIONS ================= #

def add_user(user_id: int):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)",
        (user_id, 50)
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


def set_balance(user_id: int, amount: int):
    cursor.execute(
        "UPDATE users SET balance = ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()


def deduct_balance(user_id: int, amount: int):
    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()


def get_users_count():
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]


def get_all_user_ids():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]


# ================= PAYMENTS FUNCTIONS ================= #

def add_payment(user_id: int, amount: int, status: str):
    cursor.execute(
        "INSERT INTO payments (user_id, amount, status) VALUES (?, ?, ?)",
        (user_id, amount, status)
    )
    conn.commit()


def get_payments_stats():
    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE status='success'"
    )
    return cursor.fetchone()


# ================= GENERATION FUNCTIONS ================= #

def add_generation(user_id: int, model: str):
    cursor.execute(
        "INSERT INTO generations (user_id, model) VALUES (?, ?)",
        (user_id, model)
    )
    conn.commit()


def get_generations_count():
    cursor.execute("SELECT COUNT(*) FROM generations")
    return cursor.fetchone()[0]


def get_top_users(limit=5):
    cursor.execute("""
        SELECT user_id, COUNT(*) as gen_count
        FROM generations
        GROUP BY user_id
        ORDER BY gen_count DESC
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()
