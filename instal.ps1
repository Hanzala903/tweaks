$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Tweak Pencinta Hanzala Saputra - Installer"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   Tweak Pencinta Hanzala Saputra Installer   " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$installDir = "$env:LOCALAPPDATA\TweakPencintaHanzala"
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir | Out-Null
}

Write-Host "[1/3] Memeriksa Python..." -ForegroundColor Yellow
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python tidak ditemukan! Menginstall Python via winget..." -ForegroundColor Red
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

Write-Host "[2/3] Membuat Virtual Environment..." -ForegroundColor Yellow
python -m venv "$installDir\venv"
& "$installDir\venv\Scripts\python.exe" -m pip install --upgrade pip
& "$installDir\venv\Scripts\python.exe" -m pip install PyQt6

Write-Host "[3/3] Mengunduh Aplikasi..." -ForegroundColor Yellow
# GANTI URL INI DENGAN URL RAW GITHUB LO
$rawUrl = "https://raw.githubusercontent.com/USERNAME/Tweak-Pencinta-Hanzala/main/cleaner.py"
Invoke-WebRequest -Uri $rawUrl -OutFile "$installDir\cleaner.py"

Write-Host "Membuat shortcut di Desktop..." -ForegroundColor Yellow
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Tweak Pencinta.lnk")
$Shortcut.TargetPath = "$installDir\venv\Scripts\pythonw.exe"
$Shortcut.Arguments = "`"$installDir\cleaner.py`""
$Shortcut.WorkingDirectory = "$installDir"
$Shortcut.IconLocation = "$env:SystemRoot\System32\Shell32.dll,21"
$Shortcut.Save()

Write-Host "Instalasi Selesai! Silakan cek Desktop." -ForegroundColor Green
Start-Sleep -Seconds 3