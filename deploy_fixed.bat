@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo    Order Point 一键部署脚本 (Windows Docker Desktop)
echo ============================================================
echo.

:: ============================================================
:: 步骤 1: 检查 Docker 环境
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
    echo [错误] Docker 未运行，请启动 Docker Desktop
    pause
    exit /b 1
)

echo       Docker 已就绪

:: 检测 docker-compose
where docker-compose >nul 2>&1
if errorlevel 1 (
    echo       docker-compose 未找到，尝试使用 docker compose ...
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [错误] docker compose 也未找到，请升级 Docker Desktop 版本
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
:: 步骤 2: 检查项目文件完整性
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
    echo [错误] 项目文件不完整，请确保所有源文件与脚本在同一目录
    pause
    exit /b 1
)

echo       所有必需文件已就位
echo.

:: ============================================================
:: 步骤 3: 创建配置文件（如果不存在）
:: ============================================================
echo [3/6] 检查配置文件...

if not exist "config.json" (
    echo       config.json 不存在，创建模板...
    (
    echo {
    echo     "common": {
    echo         "username": "请填写登录账号",
    echo         "password": "请填写登录密码",
    echo         "headless": true
    echo     },
    echo     "order_scanner": {
    echo         "url": "https://szguokuai.zlj.xyzulin.top/web/index.php?c=site^&a=entry^&m=ewei_shopv2^&do=web^&r=order.list.status1",
    echo         "scan_interval": 120,
    echo         "scan_interval_min": 100,
    echo         "scan_interval_max": 220,
    echo         "target_platform": "团团享",
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
    echo       已创建 config.json 模板，请后续编辑填写实际账号密码
) else (
    echo       config.json 已存在
)

if not exist "config.local.json" (
    echo       config.local.json 不存在，创建空文件...
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
:: 步骤 4: 准备使用本地版 docker-compose（去除 Traefik 依赖）
:: ============================================================
echo [4/6] 准备 Docker Compose 配置...

:: 判断是否存在本地版 compose 文件
if exist "docker-compose.local.yml" (
    echo       使用 docker-compose.local.yml（去除 Traefik 依赖）
    set "COMPOSE_FILE=docker-compose.local.yml"
) else (
    echo       使用 docker-compose.yml
    set "COMPOSE_FILE=docker-compose.yml"
)
echo.

:: ============================================================
:: 步骤 5: 构建 Docker 镜像
:: ============================================================
echo [5/6] 构建 Docker 镜像（请耐心等待 5-10 分钟）...
echo.

!COMPOSE_CMD! -f "!COMPOSE_FILE!" build

if errorlevel 1 (
    echo.
    echo [错误] Docker 构建失败，请查看错误信息
    pause
    exit /b 1
)

echo.
echo       构建成功
echo.

:: ============================================================
:: 步骤 6: 启动服务
:: ============================================================
echo [6/6] 启动服务...

!COMPOSE_CMD! -f "!COMPOSE_FILE!" up -d

if errorlevel 1 (
    echo.
    echo [错误] 启动服务失败，请查看错误信息
    echo        可能原因
    echo        - 端口 5050/5900/6080 被占用（执行 netstat -ano ^| findstr :5050 检查）
    echo        - config.json 格式错误（执行 python -m json.tool config.json 检查）
    pause
    exit /b 1
)

echo ============================================================
echo.
echo.
echo.
echo.
echo 服务正在启动，请耐心等待3秒..........
echo.
echo.
echo.
echo ============================================================
echo.

:: 等待 3 秒后显示状态
timeout /t 3 /nobreak >nul
echo.
echo    服务状态：
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ============================================================
echo    🎉 部署成功！🎉
echo ============================================================
echo.
echo    恭喜你！Order Point 服务已经成功启动！
echo.
echo    现在你可以访问：
echo.
echo     Web 管理后台:  http://localhost:5050
echo     noVNC 远程桌面: http://localhost:6080  (密码: vnc123) 
echo.  
echo    请直接复制密码到 vnc.html ，不要使用键盘输入密码 （Please copy the password, do not type it in ！！！）
echo.
echo.
echo    提示：打开 noVNC 可以实时观看订单扫描过程
echo.
echo    如果通过 UU 远程连接，请将 localhost 替换为服务器的局域网 IP
echo    例如: http://192.168.x.x:5050
echo.
echo ============================================================
echo.
pause
