@echo off
chcp 65001 >nul
echo ========================================
echo   订单管理系统启动器
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

echo [2/2] 启动 Web 服务...
echo.
echo ========================================
echo   访问地址: http://localhost:5050
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

python app.py

pause