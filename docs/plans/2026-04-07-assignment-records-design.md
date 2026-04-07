# 分单记录与统计功能设计

## 概述

记录订单分配的关键词和商家信息，统计每日商家分单数量，关键词增加"商品"字段。

## 一、数据库设计

**文件位置**: `records.db`（与 `config.json` 同目录）

**表结构**:

```sql
CREATE TABLE assignment_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,           -- 分单时间 YYYY-MM-DD HH:MM:SS
    keyword_entry TEXT,                 -- 关键词规则（如 "pocket3, Pocket3"）
    matched_keyword TEXT,               -- 实际匹配的关键词（如 "pocket3"）
    merchant TEXT NOT NULL,             -- 分配的商家名称
    product TEXT,                       -- 商品名称
    order_no TEXT,                      -- 订单号
    order_title TEXT                    -- 订单标题（脱敏）
);

CREATE INDEX idx_created_date ON assignment_records(created_at);
CREATE INDEX idx_merchant ON assignment_records(merchant);
```

## 二、关键词映射结构调整

**现有结构**:
```json
{
  "pocket3": [{"merchant": "米奇租赁官方", "weight": 1}]
}
```

**新结构**:
```json
{
  "pocket3": {
    "product": "大疆Pocket3",
    "merchants": [{"merchant": "米奇租赁官方", "weight": 1}]
  }
}
```

**兼容性处理**:
- 加载配置时自动转换旧格式
- 缺少 `product` 字段时默认空字符串

**UI 调整**:
- 关键词卡片增加"商品名称"显示
- 编辑弹窗增加"商品名称"输入框

## 三、分单记录写入逻辑

**触发时机**: 订单分配成功后

**写入字段来源**:
| 字段 | 来源 |
|------|------|
| created_at | 当前时间 |
| keyword_entry | 匹配的关键词规则 |
| matched_keyword | 实际匹配的具体关键词 |
| merchant | target_option |
| product | keyword_mapping[keyword_entry].product |
| order_no | 正则提取 |
| order_title | 订单标题脱敏 |

**实现**:
- `main.py` 新增 `record_assignment()` 函数
- 使用 `sqlite3` 模块，写入加锁

## 四、统计页面设计

**页面位置**: 新增"统计"Tab

**布局**:
- 顶部：日期选择器（默认当日）+ 前后一天快捷按钮
- 显示：当日总分单数
- 主体：商家分单数量表格

**表格**:
| 商家名称 | 当日分单数 | 累计分单数 |

**API**:
- `GET /api/stats/daily?date=YYYY-MM-DD` - 指定日期各商家分单数
- `GET /api/stats/merchants` - 所有商家累计分单数

## 五、文件变更清单

| 文件 | 变更 |
|------|------|
| `main.py` | 新增 `record_assignment()` 函数，分配成功后调用 |
| `app.py` | 新增统计 API 接口 |
| `templates/index.html` | 新增统计 Tab，关键词 UI 增加商品字段 |
| `config.local.json` | keyword_mapping 结构调整 |