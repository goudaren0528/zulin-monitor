@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo    Order Point 服务管理脚本
echo ============================================================
echo.
echo    1. 查看运行状态
echo    2. 查看实时日志
echo    3. 重启服务
echo    4. 停止服务
echo    5. 启动服务
echo    6. 重新构建并启动
echo    7. 进入容器内部
echo    0. 退出
echo.

set /p "choice=请输入选项: "

if "%choice%"=="1" goto status
if "%choice%"=="2" goto logs
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto start
if "%choice%"=="6" goto rebuild
if "%choice%"=="7" goto shell
if "%choice%"=="0" goto end
goto invalid

:status
echo.
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:logs
echo.
echo    按 Ctrl+C 退出日志查看
echo.
docker logs -f order-point
goto end

:restart
echo.
echo    正在重启...
docker restart order-point
echo    重启完成
timeout /t 2 /nobreak >nul
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:stop
echo.
echo    正在停止...
docker stop order-point
echo    已停止
echo.
pause
goto end

:start
echo.
echo    正在启动...
docker start order-point
echo    已启动
timeout /t 2 /nobreak >nul
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:rebuild
echo.
echo    正在重新构建（--no-cache）...
docker-compose -f docker-compose.local.yml build --no-cache
if errorlevel 1 (
    echo    构建失败
    pause
    goto end
)
echo    构建成功，正在重启...
docker-compose -f docker-compose.local.yml up -d
echo    完成
timeout /t 2 /nobreak >nul
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:shell
echo.
echo    进入容器内部（输入 exit 退出）...
docker exec -it order-point bash
goto end

:invalid
echo.
echo    无效选项
echo.
pause
goto end

:end
