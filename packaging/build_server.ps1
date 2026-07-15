# Freeze the Realmweave server into a single standalone exe with PyInstaller.
# Run from the repo root:  powershell -File packaging\build_server.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# use 'python' if present, else the Windows 'py' launcher
$py = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $py = "py" }

& $py -m pip install --quiet pyinstaller websockets
Push-Location (Join-Path $root "backend")
& $py -m PyInstaller --onefile --name RealmweaveServer `
    --distpath (Join-Path $root "build") `
    --workpath (Join-Path $root "build\tmp") `
    --specpath (Join-Path $root "build\tmp") `
    run_server.py
Pop-Location
Write-Host "Built build\RealmweaveServer.exe"
