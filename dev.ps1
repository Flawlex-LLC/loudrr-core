# Loudrr Local Development Startup Script
# Run: .\dev.ps1

$projectRoot = $PSScriptRoot

Write-Host "Starting Loudrr Development Environment..." -ForegroundColor Cyan

# Make sure Docker Desktop is running before trying to start containers
Write-Host ""
Write-Host "[0/7] Checking Docker Desktop..." -ForegroundColor Yellow
$dockerOk = $false
try { docker info *>$null; if ($LASTEXITCODE -eq 0) { $dockerOk = $true } } catch {}
if (-not $dockerOk) {
    Write-Host "  Docker daemon not reachable. Launching Docker Desktop..." -ForegroundColor Yellow
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
    } else {
        Write-Host "  Docker Desktop not found at $dockerExe" -ForegroundColor Red
    }
    Write-Host "  Waiting for Docker daemon (max 90s)..." -ForegroundColor Yellow
    $waited = 0
    while ($waited -lt 90) {
        Start-Sleep -Seconds 3
        $waited += 3
        try { docker info *>$null; if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break } } catch {}
    }
    if (-not $dockerOk) {
        Write-Host "  Docker still not ready after 90s. Aborting." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    Write-Host "  Docker is up." -ForegroundColor Green
}

$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) { $cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }

# Each entry becomes a tab: @{ Title = "..."; Cmd = "..." }
$tabs = @(
    @{ Title = "Redis :6379";        Cmd = "docker start loudrr-redis; docker logs -f loudrr-redis" }
    @{ Title = "Postgres :5432";     Cmd = "docker start loudrr-pg; docker logs -f loudrr-pg" }
    @{ Title = "Cloudflare Tunnel";  Cmd = "& '$cloudflared' tunnel run loudrr-dev" }
    @{ Title = "Django :8000";       Cmd = "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; python manage.py runserver 8000" }
    @{ Title = "django-q2 cluster";  Cmd = "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; python manage.py qcluster" }
    @{ Title = "Telegram Bot";       Cmd = "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; cd backend; python manage.py run_telegram_bot" }
    @{ Title = "Next.js :3000";      Cmd = "cd '$projectRoot\frontend'; npm run dev" }
)

# Locate Windows Terminal. Prefer the `wt.exe` alias if it's linked; otherwise
# find the real executable via Get-AppxPackage (which works without admin,
# unlike scanning C:\Program Files\WindowsApps directly).
$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if ($wt -and (Get-Item $wt.Source).Length -eq 0) { $wt = $null }  # 0-byte stub = disabled alias
if (-not $wt) {
    $pkg = Get-AppxPackage -Name Microsoft.WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pkg) {
        $candidate = Join-Path $pkg.InstallLocation "wt.exe"
        if (Test-Path $candidate) { $wt = @{ Source = $candidate } }
    }
}
if ($wt) {
    # wt.exe splits on `;` before processing quotes, so embedded semicolons
    # in -Command strings break everything. Workaround: write each tab's
    # commands to a .ps1 script file, then invoke `powershell -File <path>`
    # from wt — no `;` on the wt line.
    Write-Host "Launching all 7 services as tabs in one Windows Terminal window..." -ForegroundColor Yellow
    $scriptDir = Join-Path $env:TEMP "loudrr-dev-tabs"
    if (-not (Test-Path $scriptDir)) { New-Item -ItemType Directory -Path $scriptDir | Out-Null }

    $parts = @()
    for ($i = 0; $i -lt $tabs.Count; $i++) {
        $t = $tabs[$i]
        $scriptPath = Join-Path $scriptDir ("tab_{0:D2}.ps1" -f $i)
        Set-Content -Path $scriptPath -Value $t.Cmd -Encoding UTF8
        $title = $t.Title -replace '"', '\"'
        # --suppressApplicationTitle locks the title so child processes (django,
        # npm, docker) can't override it via ANSI escape sequences.
        $parts += "new-tab --title `"$title`" --suppressApplicationTitle powershell -NoExit -ExecutionPolicy Bypass -File `"$scriptPath`""
    }
    $wtLine = ($parts -join " ; ")
    $batContent = "@echo off`r`n`"$($wt.Source)`" -w 0 $wtLine`r`n"
    $batPath = Join-Path $env:TEMP "loudrr-dev-wt.bat"
    Set-Content -Path $batPath -Value $batContent -Encoding ASCII
    Start-Process cmd.exe -ArgumentList "/c", $batPath
} else {
    # Fallback: separate windows
    Write-Host "Windows Terminal not found. Opening separate PowerShell windows..." -ForegroundColor Yellow
    foreach ($t in $tabs) {
        $wrapped = "`$Host.UI.RawUI.WindowTitle = '$($t.Title)'; $($t.Cmd)"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $wrapped
        Start-Sleep -Milliseconds 500
    }
}

Write-Host ""
Write-Host "All services starting!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  Backend (local):   http://localhost:8000"
Write-Host "  Backend (tunnel):  https://dev-api.loudrr.com"
Write-Host "  API Docs:          http://localhost:8000/api/docs/"
Write-Host "  Frontend (local):  http://localhost:3000"
Write-Host "  Frontend (tunnel): https://dev-app.loudrr.com"
Write-Host "  Mini App:          https://dev-app.loudrr.com/app"
Write-Host "  Telegram Bot:      @loudrr_bot"
Write-Host ""
Write-Host "Press any key to exit this window..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
