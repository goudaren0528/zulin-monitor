# tests/test_db.py
import os
import sqlite3
import tempfile
import pytest
from db import init_db, record_assignment, get_daily_stats, get_merchant_totals

@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_records.db")
    init_db(db_path)
    yield db_path
    # 清理
    if os.path.exists(db_path):
        os.unlink(db_path)
    os.rmdir(temp_dir)

def test_init_db_creates_table(temp_db):
    """测试数据库表创建"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assignment_records'")
    result = cursor.fetchone()
    conn.close()
    assert result is not None
    assert result[0] == "assignment_records"

def test_record_assignment(temp_db):
    """测试分单记录写入"""
    record_assignment(
        db_path=temp_db,
        keyword_entry="pocket3, Pocket3",
        matched_keyword="pocket3",
        merchant="米奇租赁官方",
        product="大疆Pocket3",
        order_no="ORD123",
        order_title="测试订单"
    )

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM assignment_records")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1

def test_get_daily_stats(temp_db):
    """测试获取每日统计"""
    # 写入两条记录
    record_assignment(temp_db, "pocket3", "pocket3", "米奇租赁官方", "大疆Pocket3", "ORD1", "订单1")
    record_assignment(temp_db, "mini90", "mini90", "星享生活", "富士mini90", "ORD2", "订单2")

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    stats = get_daily_stats(temp_db, today)

    assert len(stats) == 2
    assert any(s["merchant"] == "米奇租赁官方" and s["count"] == 1 for s in stats)
    assert any(s["merchant"] == "星享生活" and s["count"] == 1 for s in stats)

def test_get_merchant_totals(temp_db):
    """测试获取商家累计统计"""
    record_assignment(temp_db, "pocket3", "pocket3", "米奇租赁官方", "大疆Pocket3", "ORD1", "订单1")
    record_assignment(temp_db, "mini90", "mini90", "米奇租赁官方", "富士mini90", "ORD2", "订单2")
    record_assignment(temp_db, "g7x3", "g7x3", "星享生活", "佳能G7X3", "ORD3", "订单3")

    totals = get_merchant_totals(temp_db)
    assert len(totals) == 2
    assert any(t["merchant"] == "米奇租赁官方" and t["total"] == 2 for t in totals)
    assert any(t["merchant"] == "星享生活" and t["total"] == 1 for t in totals)