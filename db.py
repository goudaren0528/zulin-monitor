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

    init_merchant_config_table(db_path)

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

def init_merchant_config_table(db_path=None):
    """创建商户配置表（限额+webhook）"""
    if db_path is None:
        db_path = DB_PATH

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 如果旧表存在，迁移数据到新表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merchant_limits'")
        if cursor.fetchone():
            # 创建新表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merchant_config (
                    merchant TEXT PRIMARY KEY NOT NULL,
                    limit_value INTEGER DEFAULT 0,
                    webhook_url TEXT,
                    last_reset_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            # 迁移数据
            cursor.execute("""
                INSERT OR IGNORE INTO merchant_config (merchant, limit_value, last_reset_at, updated_at)
                SELECT merchant, limit_value, last_reset_at, updated_at FROM merchant_limits
            """)
            # 删除旧表
            cursor.execute("DROP TABLE merchant_limits")
        else:
            # 直接创建新表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merchant_config (
                    merchant TEXT PRIMARY KEY NOT NULL,
                    limit_value INTEGER DEFAULT 0,
                    webhook_url TEXT,
                    last_reset_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
        conn.commit()
        conn.close()

def get_merchant_config(db_path=None, merchant=None):
    """获取单个商户的配置"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        return None

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT merchant, limit_value, webhook_url, last_reset_at FROM merchant_config WHERE merchant=?", (merchant,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"merchant": row[0], "limit_value": row[1], "webhook_url": row[2], "last_reset_at": row[3]}
        return None

def set_merchant_config(db_path=None, merchant=None, limit_value=None, webhook_url=None):
    """设置商户配置（限额或webhook，可单独更新）"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        init_db(db_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 检查是否存在
        cursor.execute("SELECT merchant, limit_value, webhook_url FROM merchant_config WHERE merchant=?", (merchant,))
        existing = cursor.fetchone()
        if existing:
            # 保留未更新的字段
            if limit_value is None:
                limit_value = existing[1]
            if webhook_url is None:
                webhook_url = existing[2]
            cursor.execute("UPDATE merchant_config SET limit_value=?, webhook_url=?, updated_at=? WHERE merchant=?",
                          (limit_value, webhook_url, now, merchant))
        else:
            if limit_value is None:
                limit_value = 0
            cursor.execute("INSERT INTO merchant_config (merchant, limit_value, webhook_url, last_reset_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                          (merchant, limit_value, webhook_url, now, now))
        conn.commit()
        conn.close()

def reset_merchant_progress(db_path=None, merchant=None):
    """重置商户进度"""
    if db_path is None:
        db_path = DB_PATH

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE merchant_config SET last_reset_at=? WHERE merchant=?", (now, merchant))
        conn.commit()
        conn.close()

def get_merchant_webhook(db_path=None, merchant=None):
    """获取商户的 webhook 地址"""
    config = get_merchant_config(db_path, merchant)
    if config:
        return config.get("webhook_url")
    return None

def get_merchant_count_since(db_path=None, merchant=None, since_timestamp=None):
    """获取商户自指定时间以来的分单数量"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        return 0

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        if since_timestamp:
            cursor.execute("SELECT COUNT(*) FROM assignment_records WHERE merchant=? AND created_at > ?",
                          (merchant, since_timestamp))
        else:
            cursor.execute("SELECT COUNT(*) FROM assignment_records WHERE merchant=?", (merchant,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

def get_all_merchant_configs(db_path=None):
    """获取所有商户配置及当前进度"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        return []

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT merchant, limit_value, webhook_url, last_reset_at FROM merchant_config")
        rows = cursor.fetchall()
        conn.close()

    results = []
    for row in rows:
        merchant, limit_value, webhook_url, last_reset_at = row
        current_count = get_merchant_count_since(db_path, merchant, last_reset_at)
        results.append({
            "merchant": merchant,
            "limit_value": limit_value,
            "webhook_url": webhook_url or "",
            "current_count": current_count,
            "last_reset_at": last_reset_at,
            "is_at_limit": limit_value > 0 and current_count >= limit_value
        })
    return results

def get_merchants_at_limit(db_path=None):
    """获取已达到限额的商户列表"""
    configs = get_all_merchant_configs(db_path)
    return [m["merchant"] for m in configs if m["is_at_limit"]]

# 保留旧函数名兼容性
def init_merchant_limits_table(db_path=None):
    init_merchant_config_table(db_path)

def get_merchant_limit(db_path=None, merchant=None):
    return get_merchant_config(db_path, merchant)

def set_merchant_limit(db_path=None, merchant=None, limit_value=0):
    set_merchant_config(db_path, merchant, limit_value=limit_value)

def reset_merchant_limit(db_path=None, merchant=None):
    reset_merchant_progress(db_path, merchant)

def get_all_merchant_limits(db_path=None):
    return get_all_merchant_configs(db_path)