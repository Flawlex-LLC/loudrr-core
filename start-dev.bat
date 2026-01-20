@echo off
echo Starting Reply Circle Development Environment...
echo.

echo [1/3] Starting Django Backend...
start "Django Backend" cmd /k "cd backend && python manage.py runserver 0.0.0.0:8000"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Next.js Frontend...
start "Next.js Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 3 /nobreak >nul

echo [3/3] Starting ngrok Tunnel...
start "ngrok" cmd /k "ngrok http 3000"

echo.
echo All services starting in separate windows!
echo.
echo URLs:
echo   - Frontend: http://localhost:3000
echo   - Backend:  http://localhost:8000
echo   - ngrok:    http://127.0.0.1:4040 (dashboard)
echo.
echo To verify backend is running:
echo   curl http://localhost:8000/api/miniapp/health/
echo.
pause
