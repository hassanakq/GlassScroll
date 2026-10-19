param([string]$Version = "")

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Run($cmd) {
    Write-Host ">> $cmd"
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
}

if ($Version) {
    $v = $Version.TrimStart("v")
    $file = "glassscroll/__init__.py"
    (Get-Content $file -Raw) -replace '__version__ = "[^"]*"', "__version__ = `"$v`"" | Set-Content $file -NoNewline
    Write-Host "Version set to $v"
}

Run "python -m pip install --upgrade pip"
Run "python -m pip install -r requirements.txt -r requirements-dev.txt"

Run ("python -m PyInstaller --noconfirm --clean --onefile --windowed " +
     "--name GlassScroll --icon assets/icon.ico " +
     "--collect-submodules pycaw --collect-submodules comtypes " +
     "--exclude-module tkinter main.py")

if (-not (Test-Path "dist/GlassScroll.exe")) { throw "dist/GlassScroll.exe was not created" }
Write-Host "Built dist/GlassScroll.exe"
