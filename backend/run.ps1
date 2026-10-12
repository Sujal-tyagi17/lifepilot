# One-click run for Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

# Installs again when a new dependency is added (scikit-learn came with Phase 3)
if (-not (Test-Path ".venv\Lib\site-packages\fastapi") -or -not (Test-Path ".venv\Lib\site-packages\sklearn")) {
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example." -ForegroundColor Green
}

Write-Host "Starting LifePilot at http://127.0.0.1:8000 ..." -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000