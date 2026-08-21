@echo off
setlocal EnableDelayedExpansion
title SAP HANA Mini Checks Console v2.0 -- Installer

:: ============================================================
:: SAP HANA Mini Checks Console v2.0 - Windows Installer
:: minichecks_console_V2.0.py  |  RDE LAC
:: Supports: bundled hdbcli OR fresh pip install from zero
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
    echo  Download the 64-bit installer from: https://www.python.org/downloads/
    echo  During installation check "Add Python to PATH".
    echo.
    if exist "!SCRIPT_DIR!\python-3.14.6-amd64.exe" (
        echo  A Python 3.14 installer was found in this folder: python-3.14.6-amd64.exe
        echo  Run it first, then re-run this installer.
    )
    echo.
    pause
    exit /b 1
)

:: Check 64-bit
python -c "import struct; assert struct.calcsize('P')*8 == 64, 'not 64-bit'" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python found but it is NOT 64-bit.
    echo  The hdbcli library requires 64-bit Python.
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
    echo  Please upgrade Python and retry.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Found: !PY_VER! (64-bit) -- OK
echo.

:: ── [2/5] Verify / install hdbcli ────────────────────────────────────────────
echo [2/5] Setting up hdbcli (SAP HANA Python driver)...
echo.

set "HDBCLI_MODE=none"

:: Check for bundled lib\ (offline / pre-packaged install)
if exist "!SCRIPT_DIR!\lib\pyhdbcli.pyd" (
    if exist "!SCRIPT_DIR!\lib\hdbcli" (
        echo  Bundled hdbcli found in lib\ -- will use it.
        set "HDBCLI_MODE=bundled"
    )
)

:: Check if already pip-installed
if "!HDBCLI_MODE!"=="none" (
    python -c "from hdbcli import dbapi" >nul 2>&1
    if not errorlevel 1 (
        echo  hdbcli already installed in Python environment -- OK.
        set "HDBCLI_MODE=pip"
    )
)

:: Neither bundled nor installed: pip install from PyPI
if "!HDBCLI_MODE!"=="none" (
    echo  hdbcli not found. Installing from PyPI...
    echo  ^(requires internet access to pypi.org^)
    echo.
    pip install hdbcli --quiet
    if errorlevel 1 (
        echo.
        echo  ERROR: pip install hdbcli failed.
        echo  Possible causes:
        echo    - No internet access
        echo    - pip not available or blocked by corporate proxy
        echo  Solutions:
        echo    - Run on a machine with internet, or
        echo    - Obtain the hdbcli wheel from SAP and run:
        echo        pip install hdbcli-*.whl
        echo    - Place the pre-bundled lib\ folder alongside this installer
        echo.
        pause
        exit /b 1
    )
    python -c "from hdbcli import dbapi" >nul 2>&1
    if errorlevel 1 (
        echo  ERROR: hdbcli installed but import still fails. Check Python environment.
        pause
        exit /b 1
    )
    echo  hdbcli installed via pip -- OK.
    set "HDBCLI_MODE=pip"
)
echo.

:: ── Check for Chart.js ────────────────────────────────────────────────────────
set "CHARTJS_FOUND=0"
if exist "!SCRIPT_DIR!\lib\chart.umd.min.js" set "CHARTJS_FOUND=1"

if "!CHARTJS_FOUND!"=="0" (
    echo  Chart.js not found in lib\.
    echo  Attempting to download chart.umd.min.js from CDN...
    powershell -NoProfile -Command ^
        "try { Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js' -OutFile '!SCRIPT_DIR!\lib\chart.umd.min.js' -TimeoutSec 15 -ErrorAction Stop; Write-Host '  chart.umd.min.js downloaded OK.' } catch { Write-Host '  WARNING: Could not download Chart.js. Chart tab will be unavailable.' }" 2>nul
    if exist "!SCRIPT_DIR!\lib\chart.umd.min.js" set "CHARTJS_FOUND=1"
) else (
    echo  chart.umd.min.js found -- Chart tab enabled.
)
echo.

:: ── [3/5] Ask for target directory ───────────────────────────────────────────
echo [3/5] Installation directory
echo.
echo  Enter the full path where you want to install Mini Checks Console.
echo  Example: C:\HANA_Tools\minichecks_console
echo  ^(Press Enter to use default: C:\HANA_Tools\minichecks_console^)
echo.
set /p "TARGET_DIR=  Install to: "
if "!TARGET_DIR!"=="" set "TARGET_DIR=C:\HANA_Tools\minichecks_console"
if "!TARGET_DIR:~-1!"=="\" set "TARGET_DIR=!TARGET_DIR:~0,-1!"
echo  Installing to: !TARGET_DIR!
echo.

:: ── [4/5] Create directory structure and copy files ──────────────────────────
echo [4/5] Creating directory structure and copying files...

mkdir "!TARGET_DIR!" 2>nul
mkdir "!TARGET_DIR!\lib" 2>nul
mkdir "!TARGET_DIR!\mini_checks" 2>nul
mkdir "!TARGET_DIR!\output" 2>nul

if not exist "!TARGET_DIR!" (
    echo  ERROR: Cannot create directory: !TARGET_DIR!
    echo  Try running as Administrator or choose a different path.
    pause
    exit /b 1
)
echo  Directories created.

:: Copy main application file
if exist "!SCRIPT_DIR!\minichecks_console_V2.0.py" (
    copy /y "!SCRIPT_DIR!\minichecks_console_V2.0.py" "!TARGET_DIR!\" >nul
    echo  minichecks_console_V2.0.py ... OK
) else (
    echo  ERROR: minichecks_console_V2.0.py not found in !SCRIPT_DIR!
    echo  Place minichecks_console_V2.0.py alongside this installer and retry.
    pause
    exit /b 1
)

:: Copy lib\ (bundled mode) or create lib\ placeholder (pip mode)
if "!HDBCLI_MODE!"=="bundled" (
    robocopy "!SCRIPT_DIR!\lib" "!TARGET_DIR!\lib" /E /NP /NFL /NDL /NJH /NJS >nul 2>&1
    echo  lib\ ^(bundled hdbcli^) ... OK
) else (
    :: pip mode: create lib\ marker so the app's sys.path.insert is harmless
    echo hdbcli installed via pip - see Python site-packages > "!TARGET_DIR!\lib\hdbcli_source.txt"
    echo  lib\ created ^(hdbcli from pip site-packages^) ... OK
)

:: Copy Chart.js if available
if exist "!SCRIPT_DIR!\lib\chart.umd.min.js" (
    copy /y "!SCRIPT_DIR!\lib\chart.umd.min.js" "!TARGET_DIR!\lib\" >nul
    echo  chart.umd.min.js ... OK
)

:: Copy mini_checks scripts if folder exists and has content
if exist "!SCRIPT_DIR!\mini_checks\*" (
    robocopy "!SCRIPT_DIR!\mini_checks" "!TARGET_DIR!\mini_checks" /E /NP /NFL /NDL /NJH /NJS >nul 2>&1
    for /f %%c in ('dir /b "!TARGET_DIR!\mini_checks\*" 2^>nul ^| find /c /v ""') do set MC_COUNT=%%c
    echo  mini_checks\ ^(!MC_COUNT! scripts^) ... OK
) else (
    echo  mini_checks\ created ^(empty - add .sql/.txt scripts here later^)
)

echo  output\ directory ready.
echo.

:: ── Verify hdbcli loads from install location ─────────────────────────────────
echo  Verifying hdbcli import...
python -c "
import sys, os
lib = os.path.join(r'!TARGET_DIR!', 'lib')
if os.path.isdir(lib):
    sys.path.insert(0, lib)
from hdbcli import dbapi
ver = getattr(dbapi, '__version__', 'unknown')
print('  hdbcli import OK -- version:', ver)
" 2>&1
if errorlevel 1 (
    echo  WARNING: hdbcli import test failed from install location.
    echo  If hdbcli was pip-installed, ensure you run the app with the same Python.
) else (
    echo  hdbcli verified OK.
)
echo.

:: ── Check port 5000 ───────────────────────────────────────────────────────────
echo  Checking port 5000 ^(default server port^)...
netstat -an 2>nul | findstr ":5000 " >nul 2>&1
if not errorlevel 1 (
    echo  WARNING: Port 5000 is in use by another process.
    echo  The app may fail to start. Stop the other process, or change the
    echo  port in the last lines of minichecks_console_V2.0.py.
) else (
    echo  Port 5000 is available -- OK.
)
echo.

:: ── [5/5] Create launcher and desktop shortcut ────────────────────────────────
echo [5/5] Creating launcher and desktop shortcut...

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
    echo  ^(Desktop shortcut could not be created -- use run_minichecks.bat directly^)
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
echo   hdbcli source   : !HDBCLI_MODE!
echo   SQL scripts     : !TARGET_DIR!\mini_checks\
echo   Output folder   : !TARGET_DIR!\output\
echo.
if "!CHARTJS_FOUND!"=="0" (
    echo   NOTE: Chart.js was not installed. The Chart tab will show a message.
    echo   To enable it later, download chart.umd.min.js and place it in:
    echo     !TARGET_DIR!\lib\
    echo.
)
echo   HOW TO USE:
echo   1. Double-click "HANA Mini Checks v2" on the Desktop
echo      ^(or run run_minichecks.bat from !TARGET_DIR!\^).
echo   2. Browser opens at http://127.0.0.1:5000 automatically.
echo   3. Enter HANA host, port ^(default 30241^), database, user, password
echo      then click Connect.
echo   4. Write SQL in the editor and press F5 or Run to execute.
echo   5. Click Mini Checks to browse and load bundled SQL scripts.
echo   6. Click ^>^> Basic Bundle to run all basic-bundle scripts at once.
echo.
echo   Keep the console window open while using the app.
echo   Press Ctrl+C in the console window to stop the server.
echo.
pause
endlocal
