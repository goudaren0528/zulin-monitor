# 分单记录与统计功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现订单分单记录存储和每日商家分单统计功能，关键词增加商品字段。

**架构:** 使用 SQLite 存储分单记录，Flask 提供 API 接口，Bootstrap 前端展示统计页面。关键词映射结构从数组改为对象格式。

**Tech Stack:** Python 3.11, SQLite3, Flask, Bootstrap 5

---

## Task 1: 创建数据库模块

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

**Step 1: 创建测试文件**

```python
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
```

**Step 2: 运行测试验证失败**

Run: `cd D:/order-auto/order-point && python -m pytest tests/test_db.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'db'"

**Step 3: 创建数据库模块**

```python
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
```

**Step 4: 运行测试验证通过**

Run: `cd D:/order-auto/order-point && python -m pytest tests/test_db.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add database module for assignment records"
```

---

## Task 2: 更新关键词映射规范化函数

**Files:**
- Modify: `main.py:223-239`

**Step 1: 更新 `_normalize_keyword_mapping` 函数**

修改 `main.py` 中 `_normalize_keyword_mapping` 函数，支持新的对象结构格式：

```python
def _normalize_keyword_mapping(keyword_mapping):
    """
    将 keyword_mapping 转换为统一的新格式。
    支持三种格式：
    1. 旧字符串格式: {"keyword": "merchant"}
    2. 旧数组格式: {"keyword": [{"merchant": "X", "weight": 1}]}
    3. 新对象格式: {"keyword": {"product": "商品", "merchants": [{"merchant": "X", "weight": 1}]}}

    Returns:
        dict: {keyword: {"product": str, "merchants": list}}
    """
    normalized = {}
    for keyword, value in keyword_mapping.items():
        if isinstance(value, str):
            # 旧格式：字符串，转换为单商家权重1
            normalized[keyword] = {"product": "", "merchants": [{"merchant": value, "weight": 1}]}
        elif isinstance(value, list):
            # 旧格式：数组，直接使用
            normalized[keyword] = {"product": "", "merchants": value}
        elif isinstance(value, dict):
            # 新格式：对象，提取 product 和 merchants
            product = value.get("product", "")
            merchants = value.get("merchants", [])
            if not merchants:
                # 兼容：如果没有 merchants 字段但有商家数据
                merchants = [{"merchant": m, "weight": 1} for m in value.get("merchants", [])]
            normalized[keyword] = {"product": product, "merchants": merchants}
        else:
            # 未知格式，跳过
            continue
    return normalized
```

**Step 2: Commit**

```bash
git add main.py
git commit -m "feat: update _normalize_keyword_mapping for new structure"
```

---

## Task 3: 在分配成功后调用记录函数

**Files:**
- Modify: `main.py` (import db module, add recording call)

**Step 1: 添加 db 模块导入**

在 `main.py` 文件顶部添加：

```python
from db import record_assignment, init_db
```

**Step 2: 在 Scanner 类初始化时初始化数据库**

在 `Scanner.__init__` 方法中添加：

```python
# 初始化数据库
init_db()
```

**Step 3: 在分配成功后调用记录函数**

找到分配成功的位置（约 `main.py:1130`），在 `log("分配操作提交完成")` 后添加记录调用：

需要修改的位置有三处（对应不同的分支），在每处 `log("分配操作提交完成")` 后添加：

```python
# 记录分单
product = ""
if matched_keyword and matched_keyword in normalized_mapping:
    product = normalized_mapping[matched_keyword].get("product", "")
record_assignment(
    keyword_entry=matched_keyword,
    matched_keyword=matched_kw if matched_kw else matched_keyword,
    merchant=target_option,
    product=product,
    order_no=order_fields.get("order_no", ""),
    order_title=order_title_masked if order_title_masked else ""
)
```

注意：需要确保 `order_title_masked` 变量可用（使用 `_mask_sensitive` 函数处理）。

**Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add assignment recording after successful dispatch"
```

---

## Task 4: 添加统计 API 接口

**Files:**
- Modify: `app.py`

**Step 1: 导入 db 模块**

在 `app.py` 文件顶部添加：

```python
from db import get_daily_stats, get_merchant_totals
```

**Step 2: 添加统计 API 接口**

在文件末尾 `if __name__ == '__main__'` 之前添加：

```python
# --- Statistics API ---
@app.route('/api/stats/daily')
def get_daily_statistics():
    """获取指定日期各商家分单数量"""
    date = request.args.get('date', '')
    from datetime import datetime
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    stats = get_daily_stats(date=date)
    total_count = sum(s['count'] for s in stats)

    # 获取累计数据
    totals = get_merchant_totals()
    totals_dict = {t['merchant']: t['total'] for t in totals}

    # 合并当日和累计数据
    result = []
    for s in stats:
        result.append({
            'merchant': s['merchant'],
            'daily_count': s['count'],
            'total_count': totals_dict.get(s['merchant'], 0)
        })

    # 补充当日无分单但有累计的商家
    merchants_with_daily = {s['merchant'] for s in stats}
    for t in totals:
        if t['merchant'] not in merchants_with_daily:
            result.append({
                'merchant': t['merchant'],
                'daily_count': 0,
                'total_count': t['total']
            })

    return jsonify({
        'date': date,
        'total': total_count,
        'merchants': result
    })

@app.route('/api/stats/records')
def get_assignment_records():
    """获取分单记录列表"""
    date = request.args.get('date', '')
    merchant = request.args.get('merchant', '')
    limit = int(request.args.get('limit', 100))

    import sqlite3
    from db import DB_PATH, db_lock

    if not os.path.exists(DB_PATH):
        return jsonify({'records': []})

    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query = "SELECT created_at, keyword_entry, matched_keyword, merchant, product, order_no, order_title FROM assignment_records"
        conditions = []
        params = []

        if date:
            conditions.append("created_at LIKE ?")
            params.append(date + "%")
        if merchant:
            conditions.append("merchant = ?")
            params.append(merchant)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        records = [{
            'created_at': row[0],
            'keyword_entry': row[1],
            'matched_keyword': row[2],
            'merchant': row[3],
            'product': row[4],
            'order_no': row[5],
            'order_title': row[6]
        } for row in cursor.fetchall()]
        conn.close()

    return jsonify({'records': records})
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add statistics API endpoints"
```

---

## Task 5: 更新关键词映射 API 处理新结构

**Files:**
- Modify: `app.py:162-186` (handle_config_keyword_mapping)

**Step 1: 更新 GET 接口**

修改 `handle_config_keyword_mapping` 的 GET 处理，返回新结构：

```python
if request.method == 'GET':
    config = _load_full_config()
    order_config = config.get('order_scanner', {})
    keyword_mapping = order_config.get('keyword_mapping', {})
    # 转换为新格式返回
    normalized = {}
    for keyword, value in keyword_mapping.items():
        if isinstance(value, str):
            normalized[keyword] = {"product": "", "merchants": [{"merchant": value, "weight": 1}]}
        elif isinstance(value, list):
            normalized[keyword] = {"product": "", "merchants": value}
        elif isinstance(value, dict):
            normalized[keyword] = value
        else:
            normalized[keyword] = {"product": "", "merchants": [{"merchant": str(value), "weight": 1}]}
    return jsonify(normalized)
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: update keyword_mapping API for new structure"
```

---

## Task 6: 更新关键词映射 UI 添加商品字段

**Files:**
- Modify: `templates/index.html`

**Step 1: 更新关键词卡片渲染函数**

找到 `renderKeywordMappingTable` 函数，修改卡片内容添加商品显示：

在卡片 header 区域添加商品名称显示：

```html
<div class="keyword-card-header">
    <span class="keyword-name">${keyword}</span>
    ${item.product ? `<span class="keyword-product">${item.product}</span>` : ''}
</div>
```

**Step 2: 更新编辑弹窗添加商品输入**

找到关键词编辑弹窗，添加商品名称输入字段：

```html
<div class="mb-3">
    <label class="form-label">商品名称</label>
    <input type="text" class="form-control" id="edit-product" placeholder="如：大疆Pocket3">
</div>
```

**Step 3: 更新保存逻辑**

在保存关键词时，将商品名称保存到新结构中：

```javascript
function saveKeyword() {
    const keyword = document.getElementById('edit-keyword').value.trim();
    const product = document.getElementById('edit-product').value.trim();
    // ... merchants 获取逻辑

    keywordMappingData[keyword] = {
        product: product,
        merchants: merchants
    };
    // ...
}
```

**Step 4: 更新加载逻辑**

确保加载时正确解析新结构。

**Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat: add product field to keyword mapping UI"
```

---

## Task 7: 添加统计 Tab 页面

**Files:**
- Modify: `templates/index.html`

**Step 1: 添加统计 Tab 按钮**

在现有 Tab 列表（约第848行"全局配置"按钮后）添加：

```html
<li class="nav-item" role="presentation">
    <button class="nav-link" id="stats-tab" data-bs-toggle="tab" data-bs-target="#stats" type="button" role="tab" aria-selected="false">
        <!-- Bar Chart Icon -->
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" x2="12" y1="20" y2="10"/>
            <line x1="18" x2="18" y1="20" y2="4"/>
            <line x1="6" x2="6" y1="20" y2="16"/>
        </svg>
        统计
    </button>
</li>
```

**Step 2: 添加统计 Tab 内容区域**

在 Tab Content 区域添加：

```html
<div class="tab-pane fade" id="stats" role="tabpanel" aria-labelledby="stats-tab">
    <div class="stats-container">
        <!-- 日期选择器 -->
        <div class="stats-header mb-4">
            <div class="d-flex align-items-center gap-3">
                <button class="btn btn-outline-secondary btn-sm" onclick="changeStatsDate(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                </button>
                <input type="date" class="form-control" id="stats-date" style="width: 150px;">
                <button class="btn btn-outline-secondary btn-sm" onclick="changeStatsDate(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                </button>
                <button class="btn btn-outline-primary btn-sm" onclick="loadStats()">刷新</button>
            </div>
            <div class="stats-summary mt-3">
                <span class="stats-total-label">当日总分单：</span>
                <span class="stats-total-value" id="stats-total">0</span>
            </div>
        </div>

        <!-- 商家统计表格 -->
        <div class="card">
            <div class="card-body">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>商家名称</th>
                            <th class="text-center">当日分单</th>
                            <th class="text-center">累计分单</th>
                        </tr>
                    </thead>
                    <tbody id="stats-table-body">
                        <tr>
                            <td colspan="3" class="text-center text-muted">加载中...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 分单记录列表 -->
        <div class="card mt-4">
            <div class="card-header">
                分单记录
            </div>
            <div class="card-body">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>时间</th>
                            <th>关键词</th>
                            <th>商品</th>
                            <th>商家</th>
                            <th>订单号</th>
                        </tr>
                    </thead>
                    <tbody id="stats-records-body">
                        <tr>
                            <td colspan="5" class="text-center text-muted">加载中...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
```

**Step 3: 添加统计页面样式**

在 `<style>` 区域添加：

```css
.stats-container {
    padding: 20px;
}
.stats-summary {
    display: flex;
    align-items: center;
    gap: 8px;
}
.stats-total-label {
    color: #64748B;
    font-size: 14px;
}
.stats-total-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--color-primary);
}
```

**Step 4: 添加统计页面 JavaScript 函数**

在 `<script>` 区域添加：

```javascript
// Statistics Tab
function initStatsDate() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('stats-date').value = today;
}

function changeStatsDate(delta) {
    const dateInput = document.getElementById('stats-date');
    const current = new Date(dateInput.value);
    current.setDate(current.getDate() + delta);
    dateInput.value = current.toISOString().split('T')[0];
    loadStats();
}

function loadStats() {
    const date = document.getElementById('stats-date').value;

    // Load daily stats
    fetch(`/api/stats/daily?date=${date}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('stats-total').textContent = data.total;

            const tbody = document.getElementById('stats-table-body');
            if (data.merchants.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">无分单记录</td></tr>';
            } else {
                tbody.innerHTML = data.merchants.map(m => `
                    <tr>
                        <td>${m.merchant}</td>
                        <td class="text-center"><strong>${m.daily_count}</strong></td>
                        <td class="text-center">${m.total_count}</td>
                    </tr>
                `).join('');
            }
        })
        .catch(e => {
            document.getElementById('stats-table-body').innerHTML = '<tr><td colspan="3" class="text-center text-danger">加载失败</td></tr>';
        });

    // Load records
    fetch(`/api/stats/records?date=${date}&limit=50`)
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('stats-records-body');
            if (data.records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">无分单记录</td></tr>';
            } else {
                tbody.innerHTML = data.records.map(r => `
                    <tr>
                        <td>${r.created_at.split(' ')[1] || r.created_at}</td>
                        <td>${r.matched_keyword || r.keyword_entry || '-'}</td>
                        <td>${r.product || '-'}</td>
                        <td>${r.merchant}</td>
                        <td>${r.order_no || '-'}</td>
                    </tr>
                `).join('');
            }
        })
        .catch(e => {
            document.getElementById('stats-records-body').innerHTML = '<tr><td colspan="5" class="text-center text-danger">加载失败</td></tr>';
        });
}

// 初始化统计页面
document.getElementById('stats-tab').addEventListener('shown.bs.tab', function() {
    initStatsDate();
    loadStats();
});
```

**Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat: add statistics tab with daily merchant counts"
```

---

## Task 8: 运行完整测试并验证功能

**Step 1: 运行所有测试**

Run: `cd D:/order-auto/order-point && python -m pytest tests/ -v`
Expected: PASS

**Step 2: 启动服务手动测试**

Run: `python app.py`

测试内容：
1. 访问 http://localhost:5050
2. 切换到"统计"Tab，验证日期选择器和表格显示
3. 切换到"配置"Tab，验证关键词卡片显示商品字段
4. 编辑关键词，验证商品名称输入和保存

**Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: complete assignment records and statistics feature"
```