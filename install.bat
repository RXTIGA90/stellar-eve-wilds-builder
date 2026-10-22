@echo off
rem Stellar Eve for Monster Hunter Wilds - double-click: language choice, outfit pictures, progress, uninstall.
rem The window is StellarEve.exe, built on this PC from tools\launcher\StellarEve.cs with the C# compiler that comes with
rem Windows (no program is downloaded). Text mode in this console: install.bat -NoGui ^| -Rows 158,147 ^| -All (see README)
cd /d "%~dp0"
rem files extracted from a downloaded ZIP carry Windows' "came from the internet" mark, which makes Windows ask
rem "publisher could not be verified" for them: clear it once for this folder so the next runs start without that question
if not exist "tools\launcher\unblocked.txt" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0.' -Recurse -File | Unblock-File" >nul 2>&1
  echo done>"tools\launcher\unblocked.txt"
)
echo.%* | findstr /i /c:"-NoGui" /c:"-Rows" /c:"-All" /c:"-Uninstall" >nul
if not errorlevel 1 goto text
rem several quick double-clicks: one builds at a time (the lock file is held open while building), the others wait
set "LOCKED="
set "BUILD_OK="
:lock
2>nul (9>"tools\launcher\build.lock" (set "LOCKED=1" & call :build))
if not defined LOCKED (timeout /t 1 /nobreak >nul & goto lock)
rem a failed rebuild (e.g. the window is open and the exe is in use) still starts the existing one
if not defined BUILD_OK if not exist "StellarEve.exe" goto text
rem StellarEve.exe allows one window per folder: a second start brings the open window to the front
start "" "%~dp0StellarEve.exe" %*
exit /b 0

:text
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Yes %*
echo.
pause
exit /b

:build
rem (re)build StellarEve.exe when it is missing or its source changed
if exist "StellarEve.exe" if exist "tools\launcher\StellarEve.built.cs" fc /b "tools\launcher\StellarEve.cs" "tools\launcher\StellarEve.built.cs" >nul 2>&1 && (set "BUILD_OK=1" & exit /b 0)
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" exit /b 1
"%CSC%" /nologo /target:winexe /codepage:65001 /out:StellarEve.exe /win32icon:data\ui\icon.ico /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll /r:Microsoft.CSharp.dll /r:System.Core.dll tools\launcher\StellarEve.cs >nul || exit /b 1
copy /y "tools\launcher\StellarEve.cs" "tools\launcher\StellarEve.built.cs" >nul
set "BUILD_OK=1"
exit /b 0
