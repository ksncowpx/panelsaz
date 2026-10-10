import sqlite3

DB_NAME = "users_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # جدول کاربران
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                railway_token TEXT
            )
        """)
        # جدول پنل‌ها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS panels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                repo TEXT,
                default_user TEXT,
                default_pass TEXT
            )
        """)
        # اضافه کردن پابلو پنل به عنوان پنل پیش‌فرض در صورت خالی بودن جدول
        cursor.execute("SELECT COUNT(*) FROM panels")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO panels (name, repo, default_user, default_pass)
                VALUES (?, ?, ?, ?)
            """, ("🟢 پابلو پنل (Pablo Panel)", "hdzirxluci-hub/pablo-panel", "admin", "admin"))
        conn.commit()

def save_user_token(user_id: int, token: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (user_id, railway_token) VALUES (?, ?)", (user_id, token))
        conn.commit()

def get_user_token(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT railway_token FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def get_all_panels():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, repo FROM panels")
        return cursor.fetchall()

def get_panel_by_id(panel_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, repo, default_user, default_pass FROM panels WHERE id = ?", (panel_id,))
        return cursor.fetchone()

def add_new_panel(name: str, repo: str, default_user: str = "admin", default_pass: str = "admin"):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO panels (name, repo, default_user, default_pass) VALUES (?, ?, ?, ?)", 
                       (name, repo, default_user, default_pass))
        conn.commit()

def delete_panel_by_id(panel_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM panels WHERE id = ?", (panel_id,))
        conn.commit()

def get_total_users():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]
