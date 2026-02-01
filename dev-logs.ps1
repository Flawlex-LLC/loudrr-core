# View logs for a specific service
# Usage: .\dev-logs.ps1 [service]
# Services: backend, celery, redis, frontend, all

param(
    [string]$service = "all"
)

$projectRoot = "c:\Users\mamoo\projects\reply-community-bot"

switch ($service) {
    "backend" {
        Write-Host "Tailing Django logs..." -ForegroundColor Cyan
        Get-Content "$projectRoot\backend\logs\django.log" -Wait -Tail 50
    }
    "redis" {
        Write-Host "Redis logs (Docker):" -ForegroundColor Cyan
        docker logs -f $(docker ps -q --filter ancestor=redis:7)
    }
    "all" {
        Write-Host "All services running in separate windows." -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Each PowerShell window shows its service logs:" -ForegroundColor Yellow
        Write-Host "  - Redis:    Docker container output"
        Write-Host "  - Django:   HTTP requests + errors"
        Write-Host "  - Celery:   Task execution logs"
        Write-Host "  - Frontend: Next.js compilation"
        Write-Host ""
        Write-Host "Tip: Use Docker Compose for unified logs:" -ForegroundColor Green
        Write-Host "  docker compose up --build"
    }
    default {
        Write-Host "Unknown service: $service" -ForegroundColor Red
        Write-Host "Options: backend, redis, frontend, all"
    }
}