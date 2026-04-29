@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo    Order Point Service Management
echo ============================================================
echo.
echo    1. Check Status
echo    2. View Logs
echo    3. Restart Service
echo    4. Stop Service
echo    5. Start Service
echo    6. Rebuild and Restart
echo    7. Enter Container
echo    0. Exit
echo.

set /p "choice=Enter option: "

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
echo    Getting status...
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:logs
echo.
echo    Viewing logs (Press Ctrl+C to exit)...
echo.
docker logs -f order-point
goto end

:restart
echo.
echo    Restarting service...
docker restart order-point
echo    Restart completed
timeout /t 2 /nobreak >nul
echo.
echo    Service status:
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:stop
echo.
echo    Stopping service...
docker stop order-point
echo    Service stopped
echo.
pause
goto end

:start
echo.
echo    Starting service...
docker start order-point
echo    Service started
timeout /t 2 /nobreak >nul
echo.
echo    Service status:
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:rebuild
echo.
echo    Rebuilding image (--no-cache)...
docker-compose -f docker-compose.local.yml build --no-cache
if errorlevel 1 (
    echo    Build failed, check error message
    pause
    goto end
)
echo    Build successful, restarting...
docker-compose -f docker-compose.local.yml up -d
echo    Completed
timeout /t 2 /nobreak >nul
echo.
echo    Service status:
docker ps --filter "name=order-point" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
pause
goto end

:shell
echo.
echo    Entering container (type exit to quit)...
echo.
docker exec -it order-point bash
goto end

:invalid
echo.
echo    Invalid option, please enter number 0-7
echo.
pause
goto end

