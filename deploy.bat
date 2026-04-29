@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo    Order Point 一键部署脚本 (Windows Docker Desktop)
echo ============================================================
echo.

:: ============================================================
:: 第 1 步：检查 Docker 环境
:: ============================================================
echo [1/6] 检查 Docker 环境...

where docker >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 docker 命令，请先安装 Docker Desktop
    echo        下载地址: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

echo       Docker 已就绪

:: 检查 docker-compose
where docker-compose >nul 2>&1
if errorlevel 1 (
    echo       docker-compose 未找到，尝试使用 docker compose ...
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [错误] docker compose 也不可用，请安装 Docker Desktop 最新版
        pause
        exit /b 1
    )
    set "COMPOSE_CMD=docker compose"
) else (
    set "COMPOSE_CMD=docker-compose"
)
echo       Compose 命令: !COMPOSE_CMD!
echo.

:: ============================================================
:: 第 2 步：检查项目文件完整性
:: ============================================================
echo [2/6] 检查项目文件...

set "MISSING=0"

if not exist "app.py" (
    echo       [缺失] app.py
    set "MISSING=1"
)
if not exist "main.py" (
    echo       [缺失] main.py
    set "MISSING=1"
)
if not exist "monitor.py" (
    echo       [缺失] monitor.py
    set "MISSING=1"
)
if not exist "db.py" (
    echo       [缺失] db.py
    set "MISSING=1"
)
if not exist "highlight_helper.py" (
    echo       [缺失] highlight_helper.py
    set "MISSING=1"
)
if not exist "requirements.txt" (
    echo       [缺失] requirements.txt
    set "MISSING=1"
)
if not exist "Dockerfile" (
    echo       [缺失] Dockerfile
    set "MISSING=1"
)

if "!MISSING!"=="1" (
    echo.
    echo [错误] 项目文件不完整，请确保所有源码文件与本脚本在同一目录下
    pause
    exit /b 1
)

echo       所有必需文件已就位
echo.

:: ============================================================
:: 第 3 步：生成配置文件（如果不存在）
:: ============================================================
echo [3/6] 检查配置文件...

if not exist "config.json" (
    echo       config.json 不存在，正在生成模板...
    (
    echo {
    echo     "common": {
    echo         "username": "请填写你的账号",
    echo         "password": "请填写你的密码",
    echo         "headless": true
    echo     },
    echo     "order_scanner": {
    echo         "url": "https://szguokuai.zlj.xyzulin.top/web/index.php?c=site^&a=entry^&m=ewei_shopv2^&do=web^&r=order.list.status1",
    echo         "scan_interval": 120,
    echo         "scan_interval_min": 100,
    echo         "scan_interval_max": 220,
    echo         "target_platform": "米奇租赁",
    echo         "keyword_mapping": {},
    echo         "webhook_configs": []
    echo     },
    echo     "interface_monitor": {
    echo         "url": "https://szguokuai.zlj.xyzulin.top/web/index.php?c=site^&a=entry^&m=ewei_shopv2^&do=web^&r=statistics.interface_log",
    echo         "scan_interval": 43200,
    echo         "webhook_url": "",
    echo         "headless": true,
    echo         "items": []
    echo     }
    echo }
    ) > config.json
    echo       已生成 config.json 模板，请稍后编辑填写实际账号密码
) else (
    echo       config.json 已存在
)

if not exist "config.local.json" (
    echo       config.local.json 不存在，创建空配置...
    echo {} > config.local.json
) else (
    echo       config.local.json 已存在
)

if not exist "records.db" (
    echo       records.db 不存在，创建空数据库...
    type nul > records.db
) else (
    echo       records.db 已存在
)

if not exist "storage_state_order_scanner.json" (
    echo       storage_state_order_scanner.json 不存在，创建空文件...
    echo {} > storage_state_order_scanner.json
) else (
    echo       storage_state_order_scanner.json 已存在
)

echo.

:: ============================================================
:: 第 4 步：使用本地版 docker-compose（去除 Traefik 依赖）
:: ============================================================
echo [4/6] 准备 Docker Compose 配置...

:: 检查是否存在本地版 compose 文件
if exist "docker-compose.local.yml" (
    echo       使用 docker-compose.local.yml（已去除 Traefik 依赖）
    set "COMPOSE_FILE=docker-compose.local.yml"
) else (
    echo       使用 docker-compose.yml
    set "COMPOSE_FILE=docker-compose.yml"
)
echo.

:: ============================================================
:: 第 5 步：构建 Docker 镜像
:: ============================================================
echo [5/6] 构建 Docker 镜像（首次构建约需 5-10 分钟）...
echo.

!COMPOSE_CMD! -f "!COMPOSE_FILE!" build

if errorlevel 1 (
    echo.
    echo [错误] Docker 镜像构建失败，请检查上方错误信息
    pause
    exit /b 1
)

echo.
echo       镜像构建成功
echo.

:: ============================================================
:: 第 6 步：启动容器
:: ============================================================
echo [6/6] 启动容器...

!COMPOSE_CMD! -f "!COMPOSE_FILE!" up -d

if errorlevel 1 (
    echo.
    echo [错误] 容器启动失败，请检查上方错误信息
    echo        常见原因：
    echo        - 端口 5050/5900/6080 被占用（用 netstat -ano ^| findstr :5050 检查）
    echo        - config.json 格式错误（用 python -m json.tool config.json 检查）
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    部署完成！
echo ============================================================
echo.
echo    访问地址：
echo      Web 管理面板:  http://localhost:5050
echo      noVNC 远程桌面: http://localhost:6080  (密码: vnc123)
echo      VNC 端口:       localhost:5900         (密码: vnc123)
echo.
echo    如果通过 UU 远程访问，请将 localhost 替换为该电脑的局域网 IP
echo    例如: http://192.168.x.x:5050
echo.
echo    常用命令：
echo      查看日志:   docker logs -f order-point
echo      停止服务:   !COMPOSE_CMD! -f "!COMPOSE_FILE!" down
echo      重启服务:   !COMPOSE_CMD! -f "!COMPOSE_FILE!" restart
echo      重新构建:   !COMPOSE_CMD! -f "!COMPOSE_FILE!" build --no-cache ^&^& !COMPOSE_CMD! -f "!COMPOSE_FILE!" up -d
echo.
echo ============================================================

:: 等待 3 秒后检查容器状态
timeout /t 3 /nobreak >nul
echo.
echo    容器状态：
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
pause
