# Zulin-Monitor 租赁订单监控系统

自动化订单处理和接口监控系统，用于电商平台的订单自动分配、接口余量监控和订单状态同步。

## 安装

### 方式一：Docker 部署（推荐）

#### 前提条件
- 已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并运行

#### 一键部署

**双击运行 `deploy_fixed.bat` 脚本会自动完成：**
1. 检查 Docker 环境
2. 检查项目文件完整性
3. 创建配置文件（如不存在）
4. 构建 Docker 镜像
5. 启动服务

#### 服务管理

**双击运行 `manage.bat` 提供以下功能：**
1. 查看运行状态
2. 查看实时日志
3. 重启服务
4. 停止服务
5. 启动服务
6. 重新构建并启动
7. 进入容器内部

### VNC 密码配置

在 `docker-compose.local.yml` 中修改：

```yaml
environment:
  - VNC_PASSWORD=vnc123
```

修改后请重新运行脚本
或使用docker命令重新构建并启动（命令如下）：

```bash
docker compose -f docker-compose.local.yml up -d --build
```

## 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| Web 管理后台 | http://localhost:5050 | 配置管理、日志查看 |
| noVNC 远程桌面 | http://localhost:6080 | 实时查看浏览器操作（密码: vnc123） |
| VNC 端口 | localhost:5900 | VNC 客户端连接（密码: vnc123） |

## 项目结构

```
zulin-monitor/
├── app.py                          # Flask Web 管理后台
├── main.py                         # 订单扫描器核心模块
├── monitor.py                      # 接口监控模块
├── sync_orders.py                  # 订单同步模块
├── db.py                           # 数据库操作模块
├── highlight_helper.py             # Playwright 元素高亮辅助模块
├── config.json                     # 基础配置文件
├── config.local.json               # 本地覆盖配置（优先级更高）
├── config.example.json             # 配置示例文件
├── requirements.txt                # Python 依赖
├── records.db                      # SQLite 数据库文件
├── storage_state_order_scanner.json # Playwright 登录状态文件
├── Dockerfile                      # Docker 镜像构建文件
├── docker-compose.yml              # Docker Compose 配置（含 Traefik）
├── docker-compose.local.yml        # Docker Compose 本地配置（无 Traefik）
├── deploy_fixed.bat                # 一键部署脚本（Windows）
├── manage.bat                      # 服务管理脚本（Windows）
├── templates/                      # HTML 模板
│   └── index.html                  # 单页管理后台
├── tests/                          # 测试文件
└── docs/                           # 文档目录
```

## 功能特性

### 1. 订单自动分配（main.py）
- 定时扫描订单列表页面（待审核 Tab）
- 按 `target_platform` 过滤目标商户的订单行
- 根据关键词匹配规则自动匹配订单
- 按权重轮询分配订单给对应商户
- 轮询索引持久化到数据库，服务重启后不归零
- 自动完成订单分配操作（点击按钮、选择商户、提交）
- 记录分配历史到数据库
- 支持商户每日限额控制，达到限额自动停止分配
- 企业微信 Webhook 通知
- Playwright 运行时元素高亮（红色边框 + 操作标签 + 脉冲动画）

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
- 关键词映射编辑（在线修改映射规则）
- RPA 群映射管理
- 实时日志查看（分类过滤、搜索、清空）
- 统计数据展示
- 数据导入/导出
- 备份管理

### 5. Docker 可视化部署
- 一键部署脚本（`deploy_fixed.bat`）
- 服务管理脚本（`manage.bat`）
- 内置 Xvfb + x11vnc + noVNC，支持远程桌面查看浏览器操作
- VNC 密码保护

## 派单流程详解

### 完整流程

```
页面加载 → 登录 → 导航到订单列表 → 点击待审核 Tab
    │
    ▼
遍历页面 DOM 子元素
    │
    ▼
检查商户名称 == target_platform ?
    │ 否 → 跳过（日志: [扫描] 跳过 [商户名] 非目标商户）
    │ 是 ↓
    │
    ▼
关键词匹配遍历 keyword_mapping
    │
    ▼
订单文本中是否包含某个关键词（或其别名）？
    │ 否 → 分配给默认商户「米奇租赁官方」（兜底逻辑）
    │ 是 ↓
    │
    ▼
取出该关键词的 merchants 列表
    │
    ▼
排除已达每日限额的商户
    │
    ▼
按权重轮询选中一个商户
    │
    ▼
执行 UI 操作: 点击订单分配 → 下拉选商户 → 确定
    │
    ▼
记录到数据库 + 发送 Webhook 通知
```

### 关键词匹配机制

`keyword_mapping` 的每个 key 支持逗号分隔的多个别名（中英文逗号均可），匹配时不区分大小写：

```json
"pocket3, Pocket3, pocket 3, Pocket 3": {
    "merchants": [
        {"merchant": "团团享租奥丰店", "weight": 1},
        {"merchant": "星享生活", "weight": 1}
    ],
    "product": "大疆Pocket3"
}
```

- 订单标题 `"大疆Pocket3相机 128G 高速内存"` 会命中 `pocket3`（不区分大小写）
- 一旦命中即停止遍历，不再匹配后续关键词

### 权重轮询机制

- 每个 merchant 的 `weight` 值决定在轮询序列中出现的次数
- weight=1 → 出现 1 次；weight=2 → 出现 2 次（分配概率翻倍）
- **weight=0 → 等同于 weight=1**（代码会将 <1 的值强制改为 1）
- 轮询索引持久化到 `weight_router` 数据库表，**服务重启后不会归零**

### 商户限额机制

| limit_value | 含义 |
|---|---|
| `0` | 无限制，永不被排除 |
| `>0` | 每日限额，`current_count >= limit_value` 时该商户被排除 |

- `current_count` 从 `assignment_records` 表动态计算（自 `last_reset_at` 之后的记录数）
- 可在 Web 管理后台手动重置

### target_platform 过滤

- `target_platform` 配置决定了系统只处理哪个商户名下的订单
- 只有商户名称**精确等于** `target_platform` 的订单行才会进入关键词匹配流程
- 其他商户的订单直接跳过，不参与分配

### 兜底逻辑

当以下情况发生时，系统会将订单分配给硬编码的默认商户「米奇租赁官方」：
1. 订单文本没有匹配到任何关键词
2. 匹配到了关键词但所有商户均已达限额
3. merchants 列表为空

## 数据库结构

### merchant_config 表

| 字段 | 类型 | 说明 |
|------|------|------|
| merchant | TEXT PK | 商户名称 |
| limit_value | INTEGER | 每日限额（0=无限制） |
| webhook_urls | TEXT | JSON 格式的 Webhook 地址列表 |
| last_reset_at | TEXT | 上次重置时间 |
| updated_at | TEXT | 最后更新时间 |

### assignment_records 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| created_at | TEXT | 创建时间 |
| keyword_entry | TEXT | 匹配到的关键词配置 key |
| matched_keyword | TEXT | 具体命中的别名 |
| merchant | TEXT | 分配的商户 |
| product | TEXT | 产品名称 |
| order_no | TEXT | 订单编号 |
| order_title | TEXT | 订单标题 |

### weight_router 表

| 字段 | 类型 | 说明 |
|------|------|------|
| keyword_entry | TEXT PK | 关键词配置 key |
| current_index | INTEGER | 当前轮询索引（0-based） |
| updated_at | TEXT | 最后更新时间 |

## 技术栈

- **语言**: Python 3.x
- **框架**: Flask
- **数据库**: SQLite（带线程锁）
- **浏览器自动化**: Playwright
- **通知**: 企业微信 Webhook
- **容器化**: Docker + docker-compose
- **远程桌面**: Xvfb + x11vnc + noVNC

## 配置说明

### 配置文件优先级

程序加载配置的顺序：
1. **先加载 `config.json`** - 作为基础配置
2. **再用 `config.local.json` 覆盖/合并** - 本地配置优先级更高

> 建议保持 `config.json` 作为模板，`config.local.json` 用于实际配置。

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
        "keyword_mapping": {
            "关键词": {
                "merchants": [{"merchant": "商户1", "weight": 1}],
                "product": "产品名称"
            }
        },
        "webhook_configs": [
            {"targets": ["*"], "url": "Webhook地址"},
            {"targets": ["商户1"], "url": "商户专属Webhook地址"}
        ],
        "rpa_group_mapping": {
            "商户名": "RPA分组名"
        }
    },
    "interface_monitor": {
        "url": "接口监控页面URL",
        "scan_interval": 43200,
        "items": [
            {"name": "接口名称", "threshold": 100}
        ],
        "webhook_url": "告警Webhook地址"
    }
}
```

### 关键词映射规则

`keyword_mapping` 支持两种格式：

**新格式（推荐，支持产品名称）：**

```json
{
    "关键词": {
        "merchants": [{"merchant": "商户名称", "weight": 权重值}],
        "product": "产品名称"
    }
}
```

**旧格式（兼容）：**

```json
{
    "关键词": [{"merchant": "商户名称", "weight": 权重值}]
}
```

- 关键词：订单标题中需要匹配的关键词（不区分大小写，支持逗号分隔多个别名）
- merchant：分配的目标商户
- weight：权重值，数值越大被分配到的概率越高（0 等同于 1）
- product：分配时选择的产品名称

### target_platform 说明

`target_platform` 决定了系统只处理哪个商户名下的订单。例如配置为 `"团团享"`：
- 页面上商户名 = `"团团享"` 的订单行 → 进入关键词匹配流程
- 页面上商户名 = `"米奇租赁官方"` 的订单行 → 跳过
- 页面上商户名 = `"团团享租奥丰店"` 的订单行 → 跳过（精确匹配，不是包含匹配）

## 日志系统

### 日志分类

日志输出采用结构化分类前缀，前端按分类着色显示：

| 前缀 | 颜色 | 说明 |
|------|------|------|
| [扫描] | 青色 | 页面扫描、行遍历 |
| [命中] | 亮青 | 发现目标商户订单 |
| [详情] | 蓝 | 订单内容详情 |
| [分配] | 金黄 | 商户选择、轮询结果 |
| [统计] | 紫 | 每轮扫描统计 |
| [通知] | 翠绿 | Webhook 通知 |
| [完成] | 青绿 | 分配操作完成 |
| [等待] | 灰 | 等待下一轮 |
| [操作] | 蓝 | UI 操作（点击按钮等） |
| [检查] | 靛 | 轮次开始 |
| [页面] | 天蓝 | 页面加载/URL |
| [导航] | 紫 | 菜单导航 |
| [登录] | 橙 | 登录流程 |
| [系统] | 浅灰 | 启动/停止/配置 |
| [高亮] | 粉 | 元素高亮 |
| [风控] | 红橙 | 反爬/风控检测 |
| [RPA] | 紫 | RPA 通知 |
| [调试] | 深灰 | 调试信息 |
| [警告] | 琥珀 | 警告 |
| [错误] | 红 | 错误 |

### 日志控制台功能

- **级别过滤**：全部 / 信息 / 调试 / 警告 / 错误
- **搜索**：实时搜索日志内容
- **清除**：清空当前日志显示
- **自动滚动**：新日志自动滚动到底部（可关闭）

## 元素高亮功能

项目内置了 Playwright 运行时元素高亮功能，方便调试和观察脚本执行情况。

### 功能特性

- 脚本正常执行，不暂停
- 自动高亮当前操作的元素
- 红色边框 + 操作类型标签 + 脉冲动画
- 高亮 1.5 秒后自动消失
- 页面导航后自动重新初始化高亮
- 弹窗出现后自动重新初始化高亮

### 开关控制

在 `highlight_helper.py` 中修改：

```python
HIGHLIGHT_ENABLED = True  # 改为 False 禁用高亮
```

## API 接口

Web 管理后台提供以下 REST API：

### 服务控制

- `POST /api/order/status` - 获取订单扫描器状态
- `POST /api/order/start` - 启动订单扫描器
- `POST /api/order/stop` - 停止订单扫描器
- `POST /api/monitor/status` - 获取接口监控状态
- `POST /api/monitor/start` - 启动接口监控
- `POST /api/monitor/stop` - 停止接口监控

### 商户管理

- `GET /api/merchants/limits` - 获取所有商户配置及限额状态
- `POST /api/merchants` - 设置商户配置
- `POST /api/merchants/reset` - 重置单个商户进度
- `POST /api/merchants/reset-all` - 重置所有商户进度
- `POST /api/merchants/add` - 新增商户
- `POST /api/merchants/delete` - 删除商户

### 关键词映射

- `GET /api/keyword-mapping` - 获取关键词映射配置
- `POST /api/keyword-mapping` - 保存关键词映射配置

### 数据管理

- `GET /api/data/import` - 导入数据
- `GET /api/data/export` - 导出数据
- `GET /api/data/backups` - 获取备份列表
- `GET /api/data/backup/<filename>` - 下载/恢复备份
- `DELETE /api/data/backup/<filename>` - 删除备份

### 日志和统计

- `GET /api/logs` - 获取实时日志
- `GET /api/stats` - 获取统计数据

## 安装方式二：手动 Docker 命令

```bash
# 构建并启动
docker compose -f docker-compose.local.yml up -d --build

# 查看日志
docker logs -f order-point

# 停止服务
docker compose -f docker-compose.local.yml down

# 重启服务
docker compose -f docker-compose.local.yml restart
```

## 安装方式三：本地运行

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 安装 Playwright 浏览器

```bash
playwright install chromium
```

#### 3. 配置系统

复制示例配置文件并修改：

```bash
copy config.example.json config.local.json
```

编辑 `config.local.json` 配置以下信息：

- 登录用户名和密码
- 目标网站 URL
- 商户列表和关键词映射
- Webhook 通知地址
- 扫描间隔时间

> 如果通过远程连接，请将 `localhost` 替换为服务器的局域网 IP，例如 `http://192.168.x.x:5050`

## Docker 部署详解

### 端口说明

| 端口 | 用途 |
|------|------|
| 5050 | Web 管理后台 |
| 5900 | VNC 服务端口 |
| 6080 | noVNC Web 访问端口 |

### docker-compose.local.yml vs docker-compose.yml

| 特性 | docker-compose.local.yml | docker-compose.yml |
|------|--------------------------|---------------------|
| Traefik 反向代理 | 不需要 | 需要 |
| 外部网络 | 不需要 | 需要 `web` 网络 |
| 适用场景 | 本地开发/单机部署 | 服务器/Traefik 环境 |

### Docker 镜像内容

基于 `mcr.microsoft.com/playwright/python:v1.57.0-jammy` 镜像，内置：
- Xvfb（虚拟显示器）
- x11vnc（VNC 服务）
- fluxbox（窗口管理器）
- noVNC（Web VNC 客户端）
- websockify（WebSocket 代理）

### 登录状态文件

`storage_state_order_scanner.json` 保存了 Playwright 的登录 Cookie，避免每次启动都需要重新登录。该文件会在成功登录后自动更新。

## 注意事项

1. **首次运行**：确保已安装 Playwright 浏览器（Docker 部署无需手动安装）
2. **配置文件**：敏感信息（密码、Webhook地址）请妥善保管，`config.local.json` 优先级高于 `config.json`
3. **并发控制**：数据库操作已内置线程锁，支持多线程安全访问
4. **日志管理**：日志缓冲区最大保留 500 条记录
5. **备份管理**：系统会自动保留最多 10 个备份文件
6. **VNC 密码**：默认密码为 `vnc123`，可在 `docker-compose.local.yml` 中修改
7. **编码问题**：`deploy_fixed.bat` 和 `manage.bat` 使用 GBK 编码保存，确保 Windows CMD 正确显示中文
8. **target_platform**：必须精确匹配页面上显示的商户名称，不是包含匹配

## 常见问题

### Q: VNC 连接密码被拒绝？
A: 默认密码为 `vnc123`，在 `docker-compose.local.yml` 的 `VNC_PASSWORD` 环境变量中。
如果输入密码时提示"密码错误"，请直接复制密码到 vnc.html 中，不要使用键盘输入密码。

### Q: 如何调试脚本执行过程？
A: 将 `headless` 设置为 `false`，并启用元素高亮功能。Docker 部署时通过 noVNC（http://localhost:6080）实时查看。

### Q: 商户达到限额后如何处理？
A: 系统会自动停止向该商户分配订单，可通过 Web 管理后台重置进度。


### Q: 权重设为 0 会怎样？
A: **权重 0 等同于权重 1**，当前代码会将小于 1 的权重强制改为 1。如果要暂停某个商户的分配，请通过限额或关键词映射删除来实现。

### Q: 服务重启后轮询会归零吗？
A: 不会。轮询索引持久化到数据库 `weight_router` 表，重启后从上次位置继续。

### Q: deploy_fixed.bat 或 manage.bat 显示乱码？
A: 这两个文件使用 GBK 编码保存，确保不要用文本编辑器重新保存为 UTF-8 编码。

### Q: 点击待审核 Tab 超时？
A: 页面顶部的「退出登录」按钮可能遮挡了 Tab。已使用 `force=True` 跳过遮挡检测，如果仍有问题请刷新页面。

### Q: 高亮功能不显示？
A: 1) 确认 `highlight_helper.py` 中 `HIGHLIGHT_ENABLED = True`；2) 页面导航后需要重新调用 `init_highlight(page)`；3) 通过 noVNC 查看而非 Web 管理后台。

## 许可证

本项目内部使用，如有任何问题或建议，欢迎提交 Pull Request。

## 更新日志

### 2026-05-06
- 修复 `is_at_limit` bug：`limit_value=0` 不再被误判为"已达限额"
- 新增轮询索引持久化到 `weight_router` 数据库表（服务重启后不归零）
- 日志系统重构：移除 emoji，添加 17 种结构化分类前缀
- 日志控制台 UI 升级：级别过滤、搜索、清空按钮
- 日志前端着色与分类前缀完全对齐
- 修复 Tab 点击被遮挡超时问题（`force=True`）
- 修复商户管理手风琴首次展开不自动加载问题
- 新增轮询分配日志：显示当前商户和下一个预计商户
- 时间戳精简为 HH:MM:SS 格式


### 2026-04-29
- 完善 Playwright 运行时元素高亮功能
- 修复页面导航后高亮丢失问题
- 修复弹窗内高亮异常问题
- 优化订单分配按钮选择器
- 添加订单菜单高亮（`a.system_menu[menu_id='order_menu']`）
- 添加 `deploy_fixed.bat` 一键部署脚本（GBK 编码，中文支持）
- 添加 `manage.bat` 服务管理脚本（GBK 编码，中文支持）
- 添加 `docker-compose.local.yml`（去除 Traefik 依赖）
- 完善 noVNC 远程桌面访问支持
- 更新 README 文档

### 2026-04-28
- 添加 Playwright 运行时元素高亮功能
- 优化订单分配逻辑
- 完善 Web 管理后台功能