# 数据管理功能设计文档

## 概述

在现有系统中新增一个「数据管理」Tab，提供配置和数据的导出/导入功能，支持多设备间数据同步。

## 功能需求

### 导出功能
- 将配置文件和数据库打包成 ZIP 文件下载
- 包含导出元数据（时间戳、版本信息）

### 导入功能
- 上传 ZIP 文件，完全替换当前设备的数据
- 导入前自动创建备份
- 导入后自动重载配置

### 备份管理
- 显示最近几次自动备份
- 支持一键恢复备份

## 数据范围

| 类型 | 文件 | 内容 |
|------|------|------|
| 配置文件 | config.json / config.local.json | 全部配置（keyword_mapping、webhook_configs、商户列表等） |
| 数据库 | records.db | assignment_records（分单记录）+ merchant_config（商户限额配置） |

## 导出格式

ZIP 压缩包结构：
```
order-point-export-YYYYMMDD-HHMMSS.zip
├── config.json          # 配置文件（优先使用 config.local.json）
├── records.db           # SQLite 数据库
└── export_info.json     # 导出元数据
```

export_info.json 结构：
```json
{
    "export_time": "2024-04-13T10:30:00",
    "version": "1.0",
    "source": "order-point",
    "config_file": "config.local.json",
    "db_tables": ["assignment_records", "merchant_config"],
    "db_record_count": {
        "assignment_records": 150,
        "merchant_config": 5
    }
}
```

## 导入流程

```
上传ZIP → 验证文件结构 → 解压临时目录 → 验证数据完整性 → 备份当前数据 → 替换数据 → 清理临时文件 → 刷新服务状态
```

### 导入验证
1. 验证 ZIP 文件格式
2. 验证必需文件存在（config.json 或 config.local.json，records.db）
3. 验证数据库文件可打开且表结构正确

### 备份策略
- 导入前自动备份到 `backups/backup_YYYYMMDD_HHMMSS.zip`
- 保留最近 10 个备份文件，自动清理旧备份

### 导入后处理
- 重载 scanner 配置（调用 scanner.load_config()）
- 不重启服务，仅刷新配置状态

## API 设计

### 后端 API (app.py)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/data/export` | GET | 导出数据，返回 ZIP 文件 |
| `/api/data/import` | POST | 导入数据，接收 ZIP 文件 |
| `/api/data/backups` | GET | 获取备份列表 |
| `/api/data/backup/<filename>` | GET | 下载指定备份 |
| `/api/data/backup/<filename>` | POST | 恢复指定备份 |

### 导出 API 详情

```
GET /api/data/export
Response: Content-Type: application/zip
          Content-Disposition: attachment; filename="order-point-export-YYYYMMDD-HHMMSS.zip"
```

### 导入 API 详情

```
POST /api/data/import
Request: multipart/form-data, file field: "file"
Response: {
    "status": "success" | "error",
    "message": "描述信息",
    "backup_file": "backup_YYYYMMDD_HHMMSS.zip" (仅成功时)
}
```

### 备份 API 详情

```
GET /api/data/backups
Response: {
    "backups": [
        {
            "filename": "backup_20240413_103000.zip",
            "created_at": "2024-04-13T10:30:00",
            "size": 12345
        }
    ]
}

GET /api/data/backup/<filename>
Response: ZIP 文件下载

POST /api/data/backup/<filename>
Response: {
    "status": "success" | "error",
    "message": "描述信息"
}
```

## UI 设计

### Tab 结构
新增「数据管理」Tab，位于「统计分析」之后。

### 布局设计
采用 Bootstrap 卡片布局，分为三个区块：

#### 1. 导出区块
- 一键导出按钮（带图标）
- 显示最近导出时间（如果有）

#### 2. 导入区块
- 文件上传区域（支持拖拽上传）
- 上传进度指示器
- 导入结果提示

#### 3. 备份管理区块
- 备份列表表格（文件名、时间、大小、操作）
- 恢复按钮、下载按钮、删除按钮

### 交互设计
- 导出成功后自动触发下载
- 导入前显示确认对话框（提示会完全替换当前数据）
- 导入成功后显示 toast 提示
- 备份恢复前显示确认对话框

## 实现要点

### 后端实现 (app.py)
1. 新增导出函数 `_export_data()`：
   - 读取 config.local.json 或 config.json
   - 复制 records.db 到临时目录
   - 创建 export_info.json
   - 打包成 ZIP 并返回

2. 新增导入函数 `_import_data()`：
   - 解压到临时目录
   - 验证文件结构
   - 创建备份
   - 替换配置文件和数据库
   - 调用 scanner.load_config() 重载配置

3. 新增备份管理函数：
   - `_list_backups()`：列出 backups 目录下的 ZIP 文件
   - `_restore_backup()`：恢复指定备份
   - `_cleanup_old_backups()`：清理超过 10 个的旧备份

### 前端实现 (templates/index.html)
1. 新增 Tab 导航项：
   - 图标使用数据库/文件夹图标
   - 标题为「数据管理」

2. 新增 Tab 内容区域：
   - 使用 Bootstrap 卡片和按钮组件
   - 使用原生 File API 处理上传
   - 使用 fetch API 调用后端接口

## 安全考虑

- 导入验证确保只接受有效的 ZIP 文件
- 导入前强制备份，防止数据丢失
- 备份文件存储在本地 backups 目录
- 不暴露敏感配置项的明文显示（导出的配置文件已包含密码等，用户需自行保管）

## 测试要点

- 导出功能：验证 ZIP 文件结构正确，数据完整
- 导入功能：验证替换流程正确，服务状态刷新
- 备份功能：验证备份创建、恢复、清理逻辑
- 边界情况：空数据库导入、配置文件不存在等