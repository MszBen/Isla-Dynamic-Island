# Builds dist\Isla.exe (one file, no Python needed to run it).
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$root = $PWD.Path

python -m pip install -r requirements.txt pyinstaller
python packaging\make_icon.py

# 1) the small hook relay Claude Code runs on every tool call. A console exe (it reads stdin / writes
#    stdout) in folder form, because a one-file exe unpacks itself on every run (~1 s per hook).
python -m PyInstaller --noconfirm --clean --onedir --console --name isla-hook `
    --distpath "$root\build\hook-dir" --workpath "$root\build\hook-work" --specpath "$root\build" `
    hooks\isla_hook.py
if ($LASTEXITCODE -ne 0) { throw "hook build failed" }

# 2) the app itself, with the relay folder bundled inside
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Isla `
    --icon "$root\packaging\isla.ico" `
    --add-data "$root\build\hook-dir\isla-hook;isla-hook" `
    --hidden-import winrt.windows.media.control `
    --hidden-import winrt.windows.storage.streams `
    --hidden-import winrt.windows.foundation `
    --hidden-import winrt.windows.foundation.collections `
    --collect-binaries winrt `
    --distpath "$root\dist" --workpath "$root\build\app-work" --specpath "$root\build" `
    Isla.pyw
if ($LASTEXITCODE -ne 0) { throw "app build failed" }

Write-Host "`nBuilt: $root\dist\Isla.exe"
