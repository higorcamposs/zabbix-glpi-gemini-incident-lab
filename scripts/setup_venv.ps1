[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPath)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 -m venv $venvPath
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv $venvPath
    }
    else {
        throw "Python 3.11+ nao encontrado no PATH."
    }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $repoRoot "app\requirements.txt")

Write-Host "Venv pronta."
Write-Host ""
Write-Host "Ativar (PowerShell):"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Executar API local (na raiz do repo):"
Write-Host "  .\.venv\Scripts\python -m uvicorn main:app --app-dir app --host 0.0.0.0 --port 8000 --reload"
