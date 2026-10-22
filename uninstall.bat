@echo off
rem Stellar Eve - remove everything it installed (the game goes back as it was) and its shortcuts.
rem Opens the uninstall step of StellarEve.exe when it exists; otherwise runs in this console.
cd /d "%~dp0"
if exist "%~dp0StellarEve.exe" (
  start "" "%~dp0StellarEve.exe" --uninstall
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall %*
echo.
pause
