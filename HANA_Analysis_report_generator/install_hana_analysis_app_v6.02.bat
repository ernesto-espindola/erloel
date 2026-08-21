@echo off
setlocal EnableDelayedExpansion
title SAP HANA Full Analysis Report Generator v6.02 -- Installer

echo.
echo  =================================================================
echo   SAP HANA Full Analysis Report Generator v6.02 -- Installer
echo   hana_analysis_app_v6.02.py  ^|  RDE LAC
echo  =================================================================
echo.

set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

:: ── [1/7] Check Python ────────────────────────────────────────────────────────
echo [1/7] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download the 64-bit installer from: https://www.python.org/downloads/
    echo  Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

python -c "import struct; assert struct.calcsize('P')*8 == 64" >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python found but it is NOT 64-bit.
    echo  Install the 64-bit Python distribution and retry.
    pause
    exit /b 1
)

python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python 3.10 or later is required. Please upgrade Python.
    pause
    exit /b 1
)

python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo  ERROR: tkinter is not available.
    echo  Reinstall Python and check the "tcl/tk and IDLE" option.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Found: !PY_VER! ^(64-bit^) -- OK
echo.

:: ── [2/7] Install Python packages ────────────────────────────────────────────
echo [2/7] Installing Python packages...
echo.

echo  anthropic ^(required - SAP AI SDK^)...
python -m pip install anthropic --quiet
if errorlevel 1 (
    echo  ERROR: pip install anthropic failed.
    echo  Check your network connection or corporate proxy settings.
    pause
    exit /b 1
)
echo  anthropic -- OK

echo  python-pptx ^(optional - PowerPoint export^)...
python -m pip install python-pptx --quiet 2>nul
if errorlevel 1 (
    echo  WARNING: python-pptx not installed. PowerPoint export will be unavailable.
) else (
    echo  python-pptx -- OK
)

echo  Pillow ^(optional - SAP logo display^)...
python -m pip install Pillow --quiet 2>nul
if errorlevel 1 (
    echo  WARNING: Pillow not installed. Logo in app header may not display.
) else (
    echo  Pillow -- OK
)
echo.

:: ── [3/7] Working directory ───────────────────────────────────────────────────
echo [3/7] Working directory
echo.
echo  This is where the app stores:
echo    - Input HANA Health Check .txt files
echo    - AI prompt template and release reference files
echo    - Generated HTML and PPTX reports
echo.
echo  Press Enter for default: %USERPROFILE%\Downloads\HANA_Analysis_App
echo.
set /p "WORK_DIR=  Working directory: "
if "!WORK_DIR!"=="" set "WORK_DIR=%USERPROFILE%\Downloads\HANA_Analysis_App"
if "!WORK_DIR:~-1!"=="\" set "WORK_DIR=!WORK_DIR:~0,-1!"
echo  Using: !WORK_DIR!
echo.

:: ── [4/7] SAP AI proxy configuration ─────────────────────────────────────────
echo [4/7] SAP AI proxy configuration
echo.
echo  The app connects to Claude AI via the SAP internal AI proxy.
echo  You need a SAP AI authentication token ^(UUID format^).
echo  Contact your team lead or the ECS AI team to obtain one.
echo  Leave blank to configure manually later in settings.json.
echo.
set /p "SAP_TOKEN=  SAP AI Token: "
if "!SAP_TOKEN!"=="" (
    set "SAP_TOKEN=ENTER-YOUR-SAP-AI-TOKEN-HERE"
    echo  WARNING: No token entered. Edit settings.json after install.
)
echo.
echo  SAP AI Proxy URL
echo  Press Enter for default: http://localhost:6655/anthropic/
set /p "PROXY_URL=  Proxy URL: "
if "!PROXY_URL!"=="" set "PROXY_URL=http://localhost:6655/anthropic/"
echo  Using: !PROXY_URL!
echo.
echo  Claude model
echo  Press Enter for default: claude-sonnet-latest
set /p "AI_MODEL=  Model: "
if "!AI_MODEL!"=="" set "AI_MODEL=claude-sonnet-latest"
echo  Using: !AI_MODEL!
echo.

:: ── [5/7] Create directory structure ─────────────────────────────────────────
echo [5/7] Creating directory structure...

mkdir "!WORK_DIR!" 2>nul
mkdir "!WORK_DIR!\HANA_Analysis_report_generator" 2>nul
mkdir "!WORK_DIR!\HANA_Analysis_report_generator\Previous versions" 2>nul
mkdir "!WORK_DIR!\HANA Health Check Reports" 2>nul
mkdir "!WORK_DIR!\Results" 2>nul

if not exist "!WORK_DIR!" (
    echo  ERROR: Cannot create directory: !WORK_DIR!
    echo  Try running as Administrator or choose a path inside your user profile.
    pause
    exit /b 1
)
echo  !WORK_DIR!
echo  !WORK_DIR!\HANA_Analysis_report_generator\
echo  !WORK_DIR!\HANA Health Check Reports\
echo  !WORK_DIR!\Results\
echo  Directories created OK.
echo.

:: ── [6/7] Copy files, patch paths, write settings.json ───────────────────────
echo [6/7] Copying files and configuring...
set "COPY_OK=1"
set "APP_DIR=!WORK_DIR!\HANA_Analysis_report_generator"

:: Main app
if exist "!SCRIPT_DIR!\hana_analysis_app_v6.02.py" (
    copy /y "!SCRIPT_DIR!\hana_analysis_app_v6.02.py" "!APP_DIR!\" >nul
    echo  hana_analysis_app_v6.02.py ... OK
) else (
    echo  ERROR: hana_analysis_app_v6.02.py not found.
    set "COPY_OK=0"
)

:: Prompt template
if exist "!SCRIPT_DIR!\HANA_HealthCheck_Prompt_Template.md" (
    copy /y "!SCRIPT_DIR!\HANA_HealthCheck_Prompt_Template.md" "!WORK_DIR!\" >nul
    echo  HANA_HealthCheck_Prompt_Template.md ... OK
) else (
    echo  ERROR: HANA_HealthCheck_Prompt_Template.md not found.
    set "COPY_OK=0"
)

:: Release reference
if exist "!SCRIPT_DIR!\HANA_latest_release.txt" (
    copy /y "!SCRIPT_DIR!\HANA_latest_release.txt" "!WORK_DIR!\" >nul
    echo  HANA_latest_release.txt ... OK
) else (
    echo  WARNING: HANA_latest_release.txt not found. Add it manually to !WORK_DIR!\
)

:: SAP logo
if exist "!SCRIPT_DIR!\SAP_LOGO.png" (
    copy /y "!SCRIPT_DIR!\SAP_LOGO.png" "!WORK_DIR!\" >nul
    echo  SAP_LOGO.png ... OK
) else (
    echo  ^(SAP_LOGO.png not found - optional, app works without it^)
)

:: App usage guide
if exist "!SCRIPT_DIR!\HANA_Analysis_App_v6.02_Guide.html" (
    copy /y "!SCRIPT_DIR!\HANA_Analysis_App_v6.02_Guide.html" "!APP_DIR!\" >nul
    echo  HANA_Analysis_App_v6.02_Guide.html ... OK
)

:: Installation guide
if exist "!SCRIPT_DIR!\HANA_Analysis_App_v6.02_Install_Guide.html" (
    copy /y "!SCRIPT_DIR!\HANA_Analysis_App_v6.02_Install_Guide.html" "!APP_DIR!\" >nul
    echo  HANA_Analysis_App_v6.02_Install_Guide.html ... OK
)

if "!COPY_OK!"=="0" (
    echo.
    echo  CRITICAL: Required files missing. Ensure all source files are in:
    echo    !SCRIPT_DIR!\
    echo  then retry.
    pause
    exit /b 1
)
echo.

:: Patch paths using helper script
echo  Patching paths in app...
set "SETTINGS_PATH=%USERPROFILE%\.claude\settings.json"

if exist "!SCRIPT_DIR!\_patch_paths.py" (
    python "!SCRIPT_DIR!\_patch_paths.py" "!APP_DIR!\hana_analysis_app_v6.02.py" "!WORK_DIR!" "!SETTINGS_PATH!"
    if errorlevel 1 (
        echo  WARNING: Path patching failed. Edit WORKING_DIR and SETTINGS_FILE manually in the .py file.
    )
) else (
    echo  WARNING: _patch_paths.py helper not found. Paths not patched.
    echo  Edit WORKING_DIR and SETTINGS_FILE manually in: !APP_DIR!\hana_analysis_app_v6.02.py
)
echo.

:: Write settings.json
if not exist "%USERPROFILE%\.claude" mkdir "%USERPROFILE%\.claude"
(
echo {
echo   "env": {
echo     "ANTHROPIC_BASE_URL": "!PROXY_URL!",
echo     "ANTHROPIC_AUTH_TOKEN": "!SAP_TOKEN!",
echo     "ANTHROPIC_MODEL": "!AI_MODEL!"
echo   }
echo }
) > "%USERPROFILE%\.claude\settings.json"
echo  settings.json written to: %USERPROFILE%\.claude\settings.json
echo.

:: ── [7/7] Launcher and desktop shortcut ──────────────────────────────────────
echo [7/7] Creating launcher and desktop shortcut...

(
echo @echo off
echo title SAP HANA Full Analysis Report Generator v6.02
echo cd /d "!APP_DIR!"
echo echo.
echo echo  Starting SAP HANA Full Analysis Report Generator v6.02...
echo echo  Close this window to stop the application.
echo echo.
echo python hana_analysis_app_v6.02.py
echo pause
) > "!WORK_DIR!\run_hana_analysis_app_v6.02.bat"
echo  Launcher: !WORK_DIR!\run_hana_analysis_app_v6.02.bat

set "SHORTCUT=%USERPROFILE%\Desktop\HANA Analysis App v6.02.lnk"
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath='!WORK_DIR!\run_hana_analysis_app_v6.02.bat'; $s.WorkingDirectory='!APP_DIR!'; $s.Description='SAP HANA Full Analysis Report Generator v6.02'; $s.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  Desktop shortcut: "HANA Analysis App v6.02" -- OK
) else (
    echo  ^(Desktop shortcut could not be created - use run_hana_analysis_app_v6.02.bat^)
)
echo.

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo  =================================================================
echo   Installation complete!
echo  =================================================================
echo.
echo   Working directory : !WORK_DIR!
echo   App               : !APP_DIR!\hana_analysis_app_v6.02.py
echo   Launcher          : !WORK_DIR!\run_hana_analysis_app_v6.02.bat
echo   Desktop shortcut  : %USERPROFILE%\Desktop\HANA Analysis App v6.02.lnk
echo   settings.json     : %USERPROFILE%\.claude\settings.json
echo   HC input folder   : !WORK_DIR!\HANA Health Check Reports\
echo   Reports output    : !WORK_DIR!\Results\
echo.
if "!SAP_TOKEN!"=="ENTER-YOUR-SAP-AI-TOKEN-HERE" (
    echo   *** ACTION REQUIRED: Edit settings.json and replace
    echo       ENTER-YOUR-SAP-AI-TOKEN-HERE with your real SAP AI token. ***
    echo.
)
echo   NEXT STEPS:
echo   1. Ensure the SAP AI proxy is running at: !PROXY_URL!
echo   2. Double-click "HANA Analysis App v6.02" on the Desktop.
echo   3. Place HANA Health Check .txt files in:
echo        !WORK_DIR!\HANA Health Check Reports\
echo   4. Click Browse, select a file, then click Generate.
echo.
echo   PACKAGES INSTALLED:
python -c "import anthropic; print('   anthropic:', anthropic.__version__)" 2>nul
python -c "import pptx; print('   python-pptx:', pptx.__version__)" 2>nul
python -c "import PIL; print('   Pillow:', PIL.__version__)" 2>nul
echo.
echo   DOCUMENTATION:
echo   !APP_DIR!\HANA_Analysis_App_v6.02_Install_Guide.html
echo   !APP_DIR!\HANA_Analysis_App_v6.02_Guide.html
echo.
pause
endlocal
