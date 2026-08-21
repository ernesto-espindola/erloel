@echo off
setlocal EnableDelayedExpansion
title SAP HANA Mini Checks Console v2.0 -- Installer

:: ============================================================
:: SAP HANA Mini Checks Console v2.0 - Windows Installer
:: minichecks_console_V2.0.py  |  RDE LAC
:: ============================================================

echo.
echo  =================================================================
echo   SAP HANA Mini Checks Console v2.0 -- Installer
echo   minichecks_console_V2.0.py  ^|  RDE LAC
echo  =================================================================
echo.

:: Source directory = folder containing this .bat file
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

:: ── [1/5] Check Python ────────────────────────────────────────────────────────
echo [1/5] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  A Python 3.14 installer is included in this folder: python-3.14.6-amd64.exe
    echo  Run it and check "Add Python to PATH" during installation.
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
    echo  Your current version is too old.
    echo  A Python 3.14 installer is included in this folder: python-3.14.6-amd64.exe
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Found: %PY_VER% (64-bit) -- OK
echo.

:: ── [2/5] Verify source files ─────────────────────────────────────────────────
echo [2/5] Verifying source files...
set "SRC_MISSING=0"

if not exist "!SCRIPT_DIR!\minichecks_console_V2.0.py" (
    echo  ERROR: minichecks_console_V2.0.py not found in: !SCRIPT_DIR!
    set "SRC_MISSING=1"
)
if not exist "!SCRIPT_DIR!\lib\pyhdbcli.pyd" (
    echo  ERROR: lib\pyhdbcli.pyd not found -- hdbcli library is missing.
    echo  Ensure the lib\ folder with pyhdbcli.pyd and hdbcli\ is present.
    set "SRC_MISSING=1"
)
if not exist "!SCRIPT_DIR!\lib\hdbcli" (
    echo  ERROR: lib\hdbcli\ folder not found -- hdbcli package directory is missing.
    set "SRC_MISSING=1"
)
if not exist "!SCRIPT_DIR!\mini_checks" (
    echo  WARNING: mini_checks\ folder not found -- the SQL scripts library will be empty.
    echo  You can add .sql or .txt scripts to mini_checks\ at any time after installation.
)

if "!SRC_MISSING!"=="1" (
    echo.
    echo  Critical files are missing. Ensure this installer is in the hana_tool\ folder
    echo  alongside:
    echo    - minichecks_console_V2.0.py
    echo    - lib\  (pyhdbcli.pyd, hdbcli\)
    echo    - mini_checks\  (SQL script .txt files)
    echo.
    pause
    exit /b 1
)

:: Check for Chart.js (optional but needed for chart tab)
if not exist "!SCRIPT_DIR!\lib\chart.umd.min.js" (
    echo  NOTE: lib\chart.umd.min.js not found.
    echo  The Chart tab will be unavailable without it.
    echo  To enable charts, download chart.umd.min.js from:
    echo    https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js
    echo  and place it in lib\.
    echo.
) else (
    echo  chart.umd.min.js found -- Chart tab enabled.
)

echo  Source files OK.
echo.

:: ── [3/5] Ask for target directory ───────────────────────────────────────────
echo [3/5] Installation directory
echo.
echo  Enter the full path where you want to install Mini Checks Console.
echo  Example: C:\HANA_Tools\minichecks_console
echo  (Press Enter to use default: C:\HANA_Tools\minichecks_console)
echo.
set /p "TARGET_DIR=  Install to: "
if "!TARGET_DIR!"=="" set "TARGET_DIR=C:\HANA_Tools\minichecks_console"
if "!TARGET_DIR:~-1!"=="\" set "TARGET_DIR=!TARGET_DIR:~0,-1!"
echo  Installing to: !TARGET_DIR!
echo.

:: ── [4/5] Copy files ──────────────────────────────────────────────────────────
echo [4/5] Copying files...

mkdir "!TARGET_DIR!" 2>nul
if not exist "!TARGET_DIR!" (
    echo  ERROR: Cannot create directory: !TARGET_DIR!
    echo  Try running as Administrator or choose a different path.
    pause
    exit /b 1
)

:: Copy everything (app, lib, mini_checks) using robocopy
echo  Copying application files (this may take a moment)...
robocopy "!SCRIPT_DIR!" "!TARGET_DIR!" /E /NP /NFL /NDL /NJH /NJS /XF "*.exe" "*.zip" "*.tar" /XD "Old_versions" "packages" "packages (2).zip" >nul 2>&1
if errorlevel 8 (
    echo  WARNING: Some files may not have copied correctly.
    echo  Check !TARGET_DIR! manually before running the app.
) else (
    echo  Files copied OK.
)

:: Ensure output directory exists
mkdir "!TARGET_DIR!\output" 2>nul
echo  output\ directory ready.
echo.

:: ── Verify hdbcli loads ───────────────────────────────────────────────────────
echo  Verifying hdbcli import from lib\...
pushd "!TARGET_DIR!"
python -c "
import sys, os
_lib = os.path.join(r'!TARGET_DIR!', 'lib')
if os.path.isdir(_lib):
    sys.path.insert(0, _lib)
from hdbcli import dbapi
print('  hdbcli import OK -- version:', dbapi.__version__ if hasattr(dbapi, '__version__') else 'unknown')
" 2>&1
if errorlevel 1 (
    echo  WARNING: hdbcli import test failed.
    echo  Ensure lib\pyhdbcli.pyd exists and Python is 64-bit 3.10+.
) else (
    echo  hdbcli verified OK.
)
popd
echo.

:: ── Check port 5000 ───────────────────────────────────────────────────────────
echo  Checking port 5000 (default server port)...
netstat -an 2>nul | findstr ":5000 " >nul 2>&1
if not errorlevel 1 (
    echo  WARNING: Port 5000 appears to be in use by another process.
    echo  The app may fail to start. Stop the other process, or edit the last lines
    echo  of minichecks_console_V2.0.py and change the port number.
) else (
    echo  Port 5000 is available -- OK.
)
echo.

:: ── [5/5] Create launcher and desktop shortcut ────────────────────────────────
echo [5/5] Creating launcher and shortcut...

(
echo @echo off
echo title SAP HANA Mini Checks Console v2.0
echo cd /d "!TARGET_DIR!"
echo echo.
echo echo  Starting SAP HANA Mini Checks Console v2.0...
echo echo  Browser will open automatically at http://127.0.0.1:5000
echo echo  Press Ctrl+C in this window to stop the server.
echo echo.
echo python minichecks_console_V2.0.py
echo pause
) > "!TARGET_DIR!\run_minichecks.bat"
echo  run_minichecks.bat created.

:: Desktop shortcut
set "SHORTCUT=%USERPROFILE%\Desktop\HANA Mini Checks v2.lnk"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '!TARGET_DIR!\run_minichecks.bat'; $s.WorkingDirectory = '!TARGET_DIR!'; $s.Description = 'SAP HANA Mini Checks Console v2.0'; $s.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  Desktop shortcut created: "HANA Mini Checks v2"
) else (
    echo  (Desktop shortcut could not be created -- use run_minichecks.bat directly)
)
echo.

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo  =================================================================
echo   Installation complete!
echo  =================================================================
echo.
echo   Installed to    : !TARGET_DIR!
echo   Launcher        : !TARGET_DIR!\run_minichecks.bat
echo   Desktop shortcut: %USERPROFILE%\Desktop\HANA Mini Checks v2.lnk
echo   SQL scripts     : !TARGET_DIR!\mini_checks\
echo   Output folder   : !TARGET_DIR!\output\
echo.
echo   HOW TO USE:
echo   1. Double-click "HANA Mini Checks v2" on the Desktop
echo      (or run run_minichecks.bat from !TARGET_DIR!\).
echo   2. The browser opens at http://127.0.0.1:5000 automatically.
echo   3. Enter your HANA host, port (default 30241), database, user
echo      and password -- then click Connect.
echo   4. The green dot confirms a live HANA connection.
echo   5. Write SQL in the editor and press F5 (or Run) to execute.
echo   6. Click "Mini Checks" to browse and load bundled SQL scripts.
echo   7. Click ">> Basic Bundle" to run all basic-bundle scripts at
echo      once and download a consolidated output file.
echo.
echo   REQUIREMENTS SUMMARY:
echo   - Python 3.10+ 64-bit (bundled installer: python-3.14.6-amd64.exe)
echo   - hdbcli:  bundled in lib\  (SAP HANA Client Python driver v2.29.23)
echo   - Chart.js: optional -- place chart.umd.min.js in lib\ for charts
echo   - Network access to the target HANA system on port 30241 (or custom)
echo.
echo   Keep the console window open while using the app.
echo   Press Ctrl+C in the console window to stop the server.
echo.
pause
endlocal
