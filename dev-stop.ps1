# Stop all Loudrr development services
# Run: .\dev-stop.ps1

Write-Host "Stopping Loudrr Development Services..." -ForegroundColor Cyan

# Stop Redis container
Write-Host "Stopping Redis..." -ForegroundColor Yellow
docker stop $(docker ps -q --filter ancestor=redis:7) 2>$null

# Stop Python processes (Django, Celery)
Write-Host "Stopping Python processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop Node processes (Frontend)
Write-Host "Stopping Node processes..." -ForegroundColor Yellow
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "`n✓ All services stopped!" -ForegroundColor Green