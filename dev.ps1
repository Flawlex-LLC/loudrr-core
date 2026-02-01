# Loudrr Local Development Startup Script
# Run: .\dev.ps1

$projectRoot = "c:\Users\mamoo\projects\reply-community-bot"

Write-Host "Starting Loudrr Development Environment..." -ForegroundColor Cyan

# Start Redis in Docker
Write-Host ""
Write-Host "[1/7] Starting Redis..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "docker run --rm -p 6379:6379 redis:7"

Start-Sleep -Seconds 2

# Start Django Backend
Write-Host "[2/7] Starting Django Backend (port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; python manage.py runserver 8000"

Start-Sleep -Seconds 2

# Start Celery Worker
Write-Host "[3/7] Starting Celery Worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; celery -A echo worker -l info -P solo"

Start-Sleep -Seconds 1

# Start Celery Beat
Write-Host "[4/7] Starting Celery Beat..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; celery -A echo beat -l info"

Start-Sleep -Seconds 1

# Start Telegram Bot
Write-Host "[5/7] Starting Telegram Bot..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; python manage.py run_telegram_bot"

Start-Sleep -Seconds 1

# Start Frontend (Mini App)
Write-Host "[6/7] Starting Frontend Mini App (port 3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\frontend'; npm run dev"

Start-Sleep -Seconds 1

# Start Landing Page
Write-Host "[7/7] Starting Landing Page (port 3001)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\landing'; npm run dev"

Write-Host ""
Write-Host "All services starting!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  Backend API:   http://localhost:8000"
Write-Host "  API Docs:      http://localhost:8000/api/docs/"
Write-Host "  Frontend App:  http://localhost:3000"
Write-Host "  Landing Page:  http://localhost:3001"
Write-Host "  Telegram Bot:  @loudrr_bot"
Write-Host ""
Write-Host "Press any key to exit this window..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
