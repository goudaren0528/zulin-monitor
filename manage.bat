@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo    订单积分服务管理
echo ============================================================
echo.
(echo     1. 查看状态)
(echo     2. 查看日志)
(echo     3. 重启服务)
(echo     4. 停止服务)
(echo     5. 启动服务)
(echo     6. 重新构建并重启)
(echo     7. 进入容器)
(echo     0. 退出)
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
echo    正在获取状态...
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:logs
echo.
echo    正在查看日志 (按 Ctrl+C 退出)...
echo.
docker logs -f order-point
goto end

:restart
echo.
echo    正在重启服务...
docker restart order-point
echo    重启完成
timeout /t 2 /nobreak >nul
echo.
echo    服务状态:
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:stop
echo.
echo    正在停止服务...
docker stop order-point
echo    服务已停止
echo.
pause
goto end

:start
echo.
echo    正在启动服务...
docker start order-point
echo    服务已启动
timeout /t 2 /nobreak >nul
echo.
echo    服务状态:
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:rebuild
echo.
echo    正在重新构建镜像 (--no-cache)...
docker-compose -f docker-compose.local.yml build --no-cache
if errorlevel 1 (
    echo    构建失败，请检查错误信息
    pause
    goto end
)
echo    构建成功，正在重启...
docker-compose -f docker-compose.local.yml up -d
echo    完成
timeout /t 2 /nobreak >nul
echo.
echo    服务状态:
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:shell
echo.
echo    正在进入容器 (输入 exit 退出)...
echo.
docker exec -it order-point bash
goto end

:invalid
echo.
echo    无效选项，请输入 0-7 之间的数字
echo.
pause
goto end

