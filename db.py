# db.py
import sqlite3
import threading
import os
import json
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
    """创建商户配置表（限额+webhooks）"""
    if db_path is None:
        db_path = DB_PATH

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merchant_config'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # 检查列结构
            cursor.execute("PRAGMA table_info(merchant_config)")
            columns = {col[1]: col[2] for col in cursor.fetchall()}

            # 如果有 webhook_url 列但没有 webhook_urls，需要迁移
            if 'webhook_url' in columns and 'webhook_urls' not in columns:
                # 创建新表
                cursor.execute("""
                    CREATE TABLE merchant_config_new (
                        merchant TEXT PRIMARY KEY NOT NULL,
                        limit_value INTEGER DEFAULT 0,
                        webhook_urls TEXT,
                        last_reset_at TEXT NOT NULL,
                        updated_at TEXT
                    )
                """)
                # 迁移数据，把单个 webhook_url 转成 JSON 数组
                cursor.execute("SELECT merchant, limit_value, webhook_url, last_reset_at, updated_at FROM merchant_config")
                rows = cursor.fetchall()
                for row in rows:
                    merchant, limit_value, webhook_url, last_reset_at, updated_at = row
                    webhook_urls_json = json.dumps([webhook_url]) if webhook_url else None
                    cursor.execute("""
                        INSERT INTO merchant_config_new (merchant, limit_value, webhook_urls, last_reset_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (merchant, limit_value, webhook_urls_json, last_reset_at, updated_at))
                # 删除旧表，重命名新表
                cursor.execute("DROP TABLE merchant_config")
                cursor.execute("ALTER TABLE merchant_config_new RENAME TO merchant_config")
            # 如果已经有 webhook_urls 列，无需迁移
        else:
            # 检查是否有旧的 merchant_limits 表需要迁移
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merchant_limits'")
            if cursor.fetchone():
                # 创建新表
                cursor.execute("""
                    CREATE TABLE merchant_config (
                        merchant TEXT PRIMARY KEY NOT NULL,
                        limit_value INTEGER DEFAULT 0,
                        webhook_urls TEXT,
                        last_reset_at TEXT NOT NULL,
                        updated_at TEXT
                    )
                """)
                # 迁移数据
                cursor.execute("""
                    INSERT INTO merchant_config (merchant, limit_value, last_reset_at, updated_at)
                    SELECT merchant, limit_value, last_reset_at, updated_at FROM merchant_limits
                """)
                cursor.execute("DROP TABLE merchant_limits")
            else:
                # 直接创建新表
                cursor.execute("""
                    CREATE TABLE merchant_config (
                        merchant TEXT PRIMARY KEY NOT NULL,
                        limit_value INTEGER DEFAULT 0,
                        webhook_urls TEXT,
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
        cursor.execute("SELECT merchant, limit_value, webhook_urls, last_reset_at FROM merchant_config WHERE merchant=?", (merchant,))
        row = cursor.fetchone()
        conn.close()
        if row:
            webhook_urls = []
            if row[2]:
                try:
                    webhook_urls = json.loads(row[2])
                except:
                    webhook_urls = []
            return {"merchant": row[0], "limit_value": row[1], "webhook_urls": webhook_urls, "last_reset_at": row[3]}
        return None

def set_merchant_config(db_path=None, merchant=None, limit_value=None, webhook_urls=None):
    """设置商户配置（限额或webhooks，可单独更新）"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        init_db(db_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 检查是否存在
        cursor.execute("SELECT merchant, limit_value, webhook_urls FROM merchant_config WHERE merchant=?", (merchant,))
        existing = cursor.fetchone()
        if existing:
            # 保留未更新的字段
            if limit_value is None:
                limit_value = existing[1]
            if webhook_urls is None:
                webhook_urls_json = existing[2]
            else:
                webhook_urls_json = json.dumps(webhook_urls) if webhook_urls else None
            cursor.execute("UPDATE merchant_config SET limit_value=?, webhook_urls=?, updated_at=? WHERE merchant=?",
                          (limit_value, webhook_urls_json, now, merchant))
        else:
            if limit_value is None:
                limit_value = 0
            webhook_urls_json = json.dumps(webhook_urls) if webhook_urls else None
            cursor.execute("INSERT INTO merchant_config (merchant, limit_value, webhook_urls, last_reset_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                          (merchant, limit_value, webhook_urls_json, now, now))
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

def get_merchant_webhooks(db_path=None, merchant=None):
    """获取商户的所有 webhook 地址列表"""
    config = get_merchant_config(db_path, merchant)
    if config:
        return config.get("webhook_urls", [])
    return []

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
        cursor.execute("SELECT merchant, limit_value, webhook_urls, last_reset_at FROM merchant_config")
        rows = cursor.fetchall()
        conn.close()

    results = []
    for row in rows:
        merchant, limit_value, webhook_urls_json, last_reset_at = row
        webhook_urls = []
        if webhook_urls_json:
            try:
                webhook_urls = json.loads(webhook_urls_json)
            except:
                webhook_urls = []
        current_count = get_merchant_count_since(db_path, merchant, last_reset_at)
        results.append({
            "merchant": merchant,
            "limit_value": limit_value,
            "webhook_urls": webhook_urls,
            "current_count": current_count,
            "last_reset_at": last_reset_at,
            # 限额为 0 表示禁用分配，>0 时检查是否达到限额
            "is_at_limit": limit_value == 0 or (limit_value > 0 and current_count >= limit_value)
        })
    return results

def get_merchants_at_limit(db_path=None):
    """获取已达到限额的商户列表"""
    configs = get_all_merchant_configs(db_path)
    return [m["merchant"] for m in configs if m["is_at_limit"]]

def delete_merchant_config(db_path=None, merchant=None):
    """删除商户配置"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        return False

    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM merchant_config WHERE merchant=?", (merchant,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
    return deleted

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

def get_merchant_webhook(db_path=None, merchant=None):
    """兼容旧函数名，返回第一个 webhook"""
    webhooks = get_merchant_webhooks(db_path, merchant)
    return webhooks[0] if webhooks else None