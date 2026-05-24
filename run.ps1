$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
if (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }
$env:PYTHONPATH = "$root\backend"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend
