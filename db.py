# db.py
import sqlite3
import threading
import os
from datetime import datetime

# 线程锁防止并发冲突
db_lock = threading.Lock()

DB_PATH = "records.db"

def init_db(db_path=None):
    """初始化数据库，创建表和索引"""
    if db_path is None:
        db_path = DB_PATH

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assignment_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                keyword_entry TEXT,
                matched_keyword TEXT,
                merchant TEXT NOT NULL,
                product TEXT,
                order_no TEXT,
                order_title TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_date ON assignment_records(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_merchant ON assignment_records(merchant)")
        conn.commit()
        conn.close()

def record_assignment(db_path=None, keyword_entry=None, matched_keyword=None,
                      merchant=None, product=None, order_no=None, order_title=None):
    """记录一条分单记录"""
    if db_path is None:
        db_path = DB_PATH

    # 确保数据库存在
    if not os.path.exists(db_path):
        init_db(db_path)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO assignment_records
            (created_at, keyword_entry, matched_keyword, merchant, product, order_no, order_title)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (created_at, keyword_entry, matched_keyword, merchant, product, order_no, order_title))
        conn.commit()
        conn.close()

def get_daily_stats(db_path=None, date=None):
    """获取指定日期各商家分单数量"""
    if db_path is None:
        db_path = DB_PATH
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(db_path):
        return []

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT merchant, COUNT(*) as count
            FROM assignment_records
            WHERE created_at LIKE ?
            GROUP BY merchant
            ORDER BY count DESC
        """, (date + "%",))
        results = [{"merchant": row[0], "count": row[1]} for row in cursor.fetchall()]
        conn.close()
        return results

def get_merchant_totals(db_path=None):
    """获取所有商家累计分单数量"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        return []

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT merchant, COUNT(*) as total
            FROM assignment_records
            GROUP BY merchant
            ORDER BY total DESC
        """)
        results = [{"merchant": row[0], "total": row[1]} for row in cursor.fetchall()]
        conn.close()
        return results