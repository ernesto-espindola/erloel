@echo off
setlocal EnableDelayedExpansion
title SAP HANA SQL Console -- Installer

:: ============================================================
:: SAP HANA SQL Console (hana_tui_web_8.py) - Windows Installer
:: ============================================================

echo.
echo  =================================================================
echo   SAP HANA SQL Console -- Installer
echo   hana_tui_web_8.py  ^|  RDE LAC
echo  =================================================================
echo.

:: Source directory = folder containing this .bat file
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

:: ── Check Python ─────────────────────────────────────────────────────────────
echo [1/5] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download the 64-bit installer from: https://www.python.org/downloads/
    echo  During installation check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: Check 64-bit
python -c "import struct; assert struct.calcsize('P')*8 == 64, 'not 64-bit'" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python found but it is NOT 64-bit.
    echo  The bundled hdbcli library (pyhdbcli.pyd) requires 64-bit Python.
    echo  Install the 64-bit Python distribution and retry.
    echo.
    pause
    exit /b 1
)

:: Check version >= 3.10
python -c "import sys; assert sys.version_info >= (3,10), 'too old'" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python 3.10 or later is required.
    echo  Your current version is too old. Please upgrade Python.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Found: %PY_VER% (64-bit) -- OK
echo.

:: ── Verify source files ──────────────────────────────────────────────────────
echo [2/5] Verifying source files...
set "SRC_MISSING=0"

if not exist "!SCRIPT_DIR!\hana_tui_web_8.py" (
    echo  ERROR: hana_tui_web_8.py not found in: !SCRIPT_DIR!
    set "SRC_MISSING=1"
)
if not exist "!SCRIPT_DIR!\lib\pyhdbcli.pyd" (
    echo  ERROR: lib\pyhdbcli.pyd not found -- hdbcli library is missing.
    set "SRC_MISSING=1"
)
if not exist "!SCRIPT_DIR!\mini_checks" (
    echo  WARNING: mini_checks\ folder not found -- scripts library will be empty.
)

if "!SRC_MISSING!"=="1" (
    echo.
    echo  Critical files are missing from the source folder.
    echo  Ensure this installer is in the hana_tool\ folder together with:
    echo    - hana_tui_web_8.py
    echo    - lib\  (containing pyhdbcli.pyd and hdbcli\)
    echo    - mini_checks\  (SQL script files)
    echo.
    pause
    exit /b 1
)
echo  Source files OK.
echo.

:: ── Ask for target directory ──────────────────────────────────────────────────
echo [3/5] Installation directory
echo.
echo  Enter the full path where you want to install the HANA SQL Console.
echo  Example: C:\HANA_Tools\hana_tool
echo  (Press Enter to install here: C:\HANA_Tools\hana_tool)
echo.
set /p "TARGET_DIR=  Install to: "
if "!TARGET_DIR!"=="" set "TARGET_DIR=C:\HANA_Tools\hana_tool"
if "!TARGET_DIR:~-1!"=="\" set "TARGET_DIR=!TARGET_DIR:~0,-1!"
echo  Installing to: !TARGET_DIR!
echo.

:: ── Copy files ────────────────────────────────────────────────────────────────
echo [4/5] Copying files...

:: Create target directory
mkdir "!TARGET_DIR!" 2>nul
if not exist "!TARGET_DIR!" (
    echo  ERROR: Cannot create directory: !TARGET_DIR!
    echo  Try running as Administrator or choose a different path.
    pause
    exit /b 1
)

:: Use robocopy for reliable folder copy
echo  Copying application files...
robocopy "!SCRIPT_DIR!" "!TARGET_DIR!" /E /NP /NFL /NDL /NJH /NJS >nul 2>&1
:: robocopy returns 0-7 for success/warnings, 8+ for errors
if errorlevel 8 (
    echo  WARNING: Some files may not have copied correctly.
    echo  Check the target directory manually.
) else (
    echo  Files copied OK.
)

:: Create output directory
mkdir "!TARGET_DIR!\output" 2>nul
echo  output\ directory created.
echo.

:: ── Verify hdbcli loads ───────────────────────────────────────────────────────
echo  Verifying hdbcli import...
pushd "!TARGET_DIR!"
python -c "
import sys, os
_lib = os.path.join(os.path.dirname(os.path.abspath('hana_tui_web_8.py')), 'lib')
if os.path.isdir(_lib):
    sys.path.insert(0, _lib)
from hdbcli import dbapi
print('hdbcli OK')
" 2>&1
if errorlevel 1 (
    echo  WARNING: hdbcli import test failed. Check that lib\pyhdbcli.pyd exists
    echo  and that Python is 64-bit 3.10+.
) else (
    echo  hdbcli import verified OK.
)
popd
echo.

:: ── Check port 5000 ──────────────────────────────────────────────────────────
echo  Checking port 5000...
netstat -an 2>nul | findstr ":5000 " >nul 2>&1
if not errorlevel 1 (
    echo  WARNING: Port 5000 appears to be in use by another process.
    echo  The app may fail to start. Either stop the other app, or edit line 3140
    echo  of hana_tui_web_8.py and change the port number.
) else (
    echo  Port 5000 is available -- OK.
)
echo.

:: ── Create run.bat launcher ───────────────────────────────────────────────────
echo [5/5] Creating launcher and shortcut...

(
echo @echo off
echo cd /d "!TARGET_DIR!"
echo echo Starting SAP HANA SQL Console...
echo echo Press Ctrl+C to stop.
echo echo.
echo python hana_tui_web_8.py
echo pause
) > "!TARGET_DIR!\run.bat"
echo  run.bat created.

:: ── Desktop shortcut ─────────────────────────────────────────────────────────
set "SHORTCUT=%USERPROFILE%\Desktop\HANA SQL Console.lnk"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '!TARGET_DIR!\run.bat'; $s.WorkingDirectory = '!TARGET_DIR!'; $s.Description = 'SAP HANA SQL Console'; $s.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  Desktop shortcut created: HANA SQL Console
) else (
    echo  (Desktop shortcut could not be created -- use run.bat directly)
)
echo.

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo  =================================================================
echo   Installation complete!
echo  =================================================================
echo.
echo   Installed to    : !TARGET_DIR!
echo   Launcher        : !TARGET_DIR!\run.bat
echo   Desktop shortcut: %USERPROFILE%\Desktop\HANA SQL Console.lnk
echo   Output folder   : !TARGET_DIR!\output\
echo.
echo   HOW TO USE:
echo   1. Double-click "HANA SQL Console" on the Desktop (or run.bat).
echo   2. The browser opens at http://127.0.0.1:5000 automatically.
echo   3. Enter your HANA host, port, database, user, and password.
echo   4. Click Connect -- the green dot confirms a live connection.
echo   5. Write SQL in the editor and press F5 (or Execute) to run.
echo   6. Use "Run Basic Bundle" to collect all mini-check results.
echo.
echo   Keep the console window open while using the app.
echo   Press Ctrl+C in the console window to stop the server.
echo.
echo   See the Deployment Guide for full documentation:
echo   !TARGET_DIR!\HANA_SQL_Console_Deployment_Guide.html
echo.
pause
endlocal
