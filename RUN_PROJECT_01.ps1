# ==============================================================================
# PROJECT 01 - ONLINE HOSTEL FACILITIES MANAGEMENT REPORTING PLATFORM
# Auto-Run Script (PowerShell)
# Double-click RUN_PROJECT_01.bat to launch
# ==============================================================================

$ErrorActionPreference = 'Continue'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
cd $scriptDir

# --- Find Python ---
function Find-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    }
    $paths = @(
        "C:\Users\Jfx\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python310\python.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    return $null
}

$pythonPath = Find-Python
if (-not $pythonPath) {
    Write-Host "  [X] Python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    Write-Host "      Enable 'Add Python to PATH' during install." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  [OK] Python: $pythonPath" -ForegroundColor Green
& $pythonPath --version 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor Gray }

# --- Seed database ---
Write-Host "  [*] Seeding demo database..." -ForegroundColor Yellow
& $pythonPath -m hostelhub.seed --reset 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Demo database seeded" -ForegroundColor Green
} else {
    Write-Host "  [!] Seed may have failed (continuing anyway)" -ForegroundColor Yellow
}

# --- Launch server ---
Write-Host "  [*] Starting HostelHub on http://127.0.0.1:8000..." -ForegroundColor Yellow
$proc = Start-Process -FilePath $pythonPath -ArgumentList "app.py" -WorkingDirectory $scriptDir -WindowStyle Hidden -PassThru

# Wait for server
$start = Get-Date
$ready = $false
while ((Get-Date) -lt $start.AddSeconds(30)) {
    try { $s = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 8000); $s.Close(); $ready = $true; break } catch { Start-Sleep -Milliseconds 500 }
}
if ($ready) {
    Write-Host "  [OK] HostelHub is ready at http://127.0.0.1:8000" -ForegroundColor Green
    Start-Process "http://127.0.0.1:8000"
} else {
    Write-Host "  [!] Server may still be starting" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  PROJECT 01 IS RUNNING!" -ForegroundColor Green
Write-Host "  URL: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Demo accounts:" -ForegroundColor Cyan
Write-Host "    Student : student@hostelhub.edu.ng / Student@123" -ForegroundColor Cyan
Write-Host "    Staff   : grace.okafor@hostelhub.edu.ng / Staff@123" -ForegroundColor Cyan
Write-Host "    Admin   : admin@hostelhub.edu.ng / Admin@123" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Keep this window open. Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

try { while ($true) { Start-Sleep -Seconds 5 } } catch {
    try { $proc.Kill() } catch {}
    Write-Host "Server stopped." -ForegroundColor Green
}