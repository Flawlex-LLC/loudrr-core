@echo off
echo ========================================
echo   Cloudflare Tunnel for ECHO Dev
echo ========================================
echo.

REM Find cloudflared - check PATH first, then common locations
set CLOUDFLARED=cloudflared
where cloudflared >nul 2>&1 || (
    if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
        set CLOUDFLARED="C:\Program Files (x86)\cloudflared\cloudflared.exe"
    ) else if exist "C:\Program Files\cloudflared\cloudflared.exe" (
        set CLOUDFLARED="C:\Program Files\cloudflared\cloudflared.exe"
    )
)

REM Check which service to tunnel
if "%1"=="backend" goto backend
if "%1"=="frontend" goto frontend
if "%1"=="both" goto both

echo Usage: start-tunnel.bat [backend^|frontend^|both]
echo.
echo   backend  - Tunnel port 8000 (Django API)
echo   frontend - Tunnel port 3000 (Next.js Mini App)
echo   both     - Start both tunnels (opens 2 windows)
echo.
goto end

:backend
echo Starting tunnel for Backend (port 8000)...
echo The URL will appear below - look for "https://xxxxx.trycloudflare.com"
echo Use this URL for your Telegram webhook.
echo.
%CLOUDFLARED% tunnel --url http://localhost:8000
goto end

:frontend
echo Starting tunnel for Frontend (port 3000)...
echo The URL will appear below - look for "https://xxxxx.trycloudflare.com"
echo Use this URL for MINIAPP_URL in your .env
echo.
%CLOUDFLARED% tunnel --url http://localhost:3000
goto end

:both
echo Starting tunnels for both services...
echo.
start "Backend Tunnel (8000)" cmd /k "%CLOUDFLARED% tunnel --url http://localhost:8000"
timeout /t 3 >nul
start "Frontend Tunnel (3000)" cmd /k "%CLOUDFLARED% tunnel --url http://localhost:3000"
echo.
echo Two tunnel windows opened!
echo.
echo Look for URLs like: https://xxxxx.trycloudflare.com
echo   - Backend URL: For TELEGRAM webhook
echo   - Frontend URL: For MINIAPP_URL in .env
echo.
echo Note: URLs change each time you restart the tunnel.
goto end

:end
