[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Venv nao encontrada. Rode: .\scripts\setup_venv.ps1"
}

Set-Location $repoRoot
$port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
& $venvPython -m uvicorn main:app --app-dir app --host 0.0.0.0 --port $port --reload
