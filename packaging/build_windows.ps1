# Build a Windows folder distribution (PyInstaller onedir) containing ACID2Reaper.exe
# Run in PowerShell from the project root after installing Python 3.9+.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Verifying CHANGELOG matches pyproject version"
python scripts/verify_changelog.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Installing package + PyInstaller"
python -m pip install --upgrade pip wheel
python -m pip install ".[pyinstaller]"

Write-Host "==> Running PyInstaller"
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
python -m PyInstaller packaging\pyinstaller.spec

$Exe = Join-Path $Root "dist\ACID2Reaper\ACID2Reaper.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "Expected $Exe — check PyInstaller output."
}
Write-Host "Done: $Exe"

$Zip = Join-Path $Root "dist\ACID2Reaper-windows.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Write-Host "==> Creating $Zip"
Compress-Archive -Path (Join-Path $Root "dist\ACID2Reaper") -DestinationPath $Zip
Write-Host "Distribution archive: $Zip"
Write-Host "Optional: wrap with Inno Setup / WiX for a classic installer."
