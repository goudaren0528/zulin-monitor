# Zulin-Monitor 租赁订单监控系统

自动化订单处理和接口监控系统，用于电商平台的订单自动分配、接口余量监控和订单状态同步。

## 功能特性

### 1. 订单自动分配（main.py）
- 定时扫描订单列表页面
- 根据关键词匹配规则自动匹配订单
- 按权重随机分配订单给对应商户
- 自动完成订单分配操作（点击按钮、选择商户、提交）
- 记录分配历史到数据库
- 支持商户限额控制，达到限额自动停止分配
- 企业微信 Webhook 通知

### 2. 接口余量监控（monitor.py）
- 定时检查第三方接口调用余量
- 当可用量低于设定阈值时发送告警
- 支持监控多个接口项
- 企业微信 Webhook 告警通知

### 3. 订单状态同步（sync_orders.py）
- 从外部 API 获取待同步订单
- 查询订单状态并提取物流信息
- 自动同步订单状态到外部系统
- 支持物流弹窗信息抓取

### 4. Web 管理后台（app.py）
- 商户配置管理（限额、Webhook）
- 实时日志查看
- 统计数据展示
- 数据导入/导出
- 备份管理

## 技术栈

- **语言**: Python 3.x
- **框架**: Flask
- **数据库**: SQLite（带线程锁）
- **浏览器自动化**: Playwright
- **通知**: 企业微信 Webhook

## 项目结构

```
zulin-monitor/
├── app.py                      # Flask Web 管理后台
├── main.py                     # 订单扫描器核心模块
├── monitor.py                  # 接口监控模块
├── sync_orders.py             # 订单同步模块
├── db.py                      # 数据库操作模块
├── highlight_helper.py        # Playwright 元素高亮辅助模块
├── config.json                # 系统配置文件
├── config.example.json        # 配置示例文件
├── requirements.txt           # Python 依赖
├── records.db                 # SQLite 数据库文件
├── templates/                 # HTML 模板
├── tests/                     # 测试文件
└── docs/                      # 文档目录
```

## 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 3. 配置系统

复制示例配置文件并修改：

```bash
copy config.example.json config.local.json
```

编辑 `config.json` 或 `config.local.json` 或 `config.example.json` 配置以下信息：

- 登录用户名和密码
- 目标网站 URL
- 商户列表和关键词映射
- Webhook 通知地址
- 扫描间隔时间

## 使用方法

### 启动订单扫描器

```bash
python main.py
```

### 启动接口监控

```bash
python monitor.py
```

### 启动订单同步

```bash
python sync_orders.py
```

### 启动 Web 管理后台

```bash
python app.py
```

默认访问地址：http://localhost:5050

## 配置说明

### config.json 结构

```json
{
    "common": {
        "username": "登录用户名",
        "password": "登录密码",
        "headless": true
    },
    "order_scanner": {
        "url": "订单列表页面URL",
        "merchant_url": "商户订单页面URL",
        "scan_interval": 120,
        "scan_interval_min": 100,
        "scan_interval_max": 220,
        "target_platform": "目标平台名称",
        "merchants": ["商户1", "商户2"],
        "keyword_mapping": {
            "关键词1": [{"merchant": "商户1", "weight": 1}],
            "关键词2": [{"merchant": "商户1", "weight": 1}, {"merchant": "商户2", "weight": 1}]
        },
        "webhook_configs": [
            {"targets": ["*"], "url": "Webhook地址"},
            {"targets": ["商户1"], "url": "商户专属Webhook地址"}
        ]
    },
    "interface_monitor": {
        "url": "接口监控页面URL",
        "scan_interval": 43200,
        "items": [
            {"name": "接口名称", "threshold": 100}
        ],
        "webhook_url": "告警Webhook地址"
    },
    "order_sync": {
        "url": "订单管理页面URL",
        "scan_interval": 60,
        "fetch_orders_api": "获取订单API",
        "update_order_api": "更新订单API"
    }
}
```

### 关键词映射规则

`keyword_mapping` 用于定义订单标题关键词与商户的对应关系：

```json
{
    "关键词": [
        {"merchant": "商户名称", "weight": 权重值}
    ]
}
```

- 关键词：订单标题中需要匹配的关键词（不区分大小写）
- merchant：分配的目标商户
- weight：权重值，数值越大被分配到的概率越高

## 元素高亮功能

项目内置了 Playwright 运行时元素高亮功能，方便调试和观察脚本执行情况。

### 功能特性

- 脚本正常执行，不暂停
- 自动高亮当前操作的元素
- 红色边框 + 操作类型标签 + 脉冲动画
- 高亮 1.5 秒后自动消失

### 开关控制

在 `highlight_helper.py` 中修改：

```python
HIGHLIGHT_ENABLED = True  # 改为 False 禁用高亮
```

### 使用示例

```python
from highlight_helper import init_highlight, highlight_by_selector, highlight_locator

# 初始化（在创建 page 后调用）
init_highlight(page)

# 通过 CSS 选择器高亮
highlight_by_selector(page, "#button-id", "click")

# 通过 locator 高亮
highlight_locator(page, locator, "focus: input")
```

## API 接口

Web 管理后台提供以下 REST API：

### 商户管理

- `GET /api/merchants` - 获取所有商户配置
- `POST /api/merchants` - 设置商户配置
- `POST /api/merchants/reset` - 重置单个商户进度
- `POST /api/merchants/reset-all` - 重置所有商户进度
- `POST /api/merchants/add` - 新增商户
- `POST /api/merchants/delete` - 删除商户

### 数据管理

- `GET /api/data/import` - 导入数据
- `GET /api/data/export` - 导出数据
- `GET /api/data/backups` - 获取备份列表
- `GET /api/data/backup/<filename>` - 下载/恢复备份
- `DELETE /api/data/backup/<filename>` - 删除备份

### 日志和统计

- `GET /api/logs` - 获取实时日志
- `GET /api/stats` - 获取统计数据

## Docker 部署

### 构建镜像

```bash
docker build -t zulin-monitor .
```

### 使用 docker-compose

```bash
docker-compose up -d
```

## 注意事项

1. **首次运行**：确保已安装 Playwright 浏览器
2. **配置文件**：敏感信息（密码、Webhook地址）请妥善保管
3. **并发控制**：数据库操作已内置线程锁，支持多线程安全访问
4. **日志管理**：日志缓冲区最大保留 500 条记录
5. **备份管理**：系统会自动保留最多 10 个备份文件

## 常见问题

### Q: 脚本无法找到元素？
A: 检查页面是否已加载完成，可能需要调整等待时间或更新选择器。

### Q: 如何调试脚本执行过程？
A: 将 `headless` 设置为 `false`，并启用元素高亮功能。

### Q: 商户达到限额后如何处理？
A: 系统会自动停止向该商户分配订单，可通过 Web 管理后台重置进度。

## 许可证

本项目仅供学习和内部使用。

## 更新日志

### 2026-04-28
- 添加 Playwright 运行时元素高亮功能
- 优化订单分配逻辑
- 完善 Web 管理后台功能
