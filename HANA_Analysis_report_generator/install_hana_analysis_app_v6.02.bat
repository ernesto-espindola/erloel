@echo off
setlocal EnableDelayedExpansion
title SAP HANA Full Analysis Report Generator v6.02 -- Installer

:: ============================================================
:: SAP HANA Full Analysis Report Generator v6.02 - Windows Installer
:: RDE LAC / SAP ECS
:: Run as Administrator for best results
:: ============================================================

echo.
echo  =================================================================
echo   SAP HANA Full Analysis Report Generator -- Installer v6.02
echo   RDE LAC / SAP ECS
echo  =================================================================
echo.

:: Source directory = folder containing this .bat
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

:: Parent directory (working directory root, one level up)
for %%I in ("!SCRIPT_DIR!\..") do set "PARENT_DIR=%%~fI"

:: ── [1/8] Check Python ────────────────────────────────────────────────────────
echo [1/8] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download from: https://www.python.org/downloads/
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
    echo  The anthropic SDK requires 64-bit Python.
    echo  Install the 64-bit distribution and retry.
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
echo  Found: %PY_VER% (64-bit) -- OK
echo.

:: Check tkinter (must be in stdlib)
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo  ERROR: tkinter is not available in this Python installation.
    echo  Reinstall Python with the "tcl/tk and IDLE" option checked.
    pause
    exit /b 1
)
echo  tkinter -- OK
echo.

:: ── [2/8] Working directory ────────────────────────────────────────────────────
echo [2/8] Working directory setup
echo.
echo  Enter the full path for the HANA Analysis App working directory.
echo  This is where input files (Health Checks), templates, and output
echo  reports will be stored.
echo  Example: C:\HANA_Analysis_App
echo  (Press Enter to use default: C:\HANA_Analysis_App)
echo.
set /p "WORK_DIR=  Working directory: "
if "!WORK_DIR!"=="" set "WORK_DIR=C:\HANA_Analysis_App"
if "!WORK_DIR:~-1!"=="\" set "WORK_DIR=!WORK_DIR:~0,-1!"
echo  Using: !WORK_DIR!
echo.

:: ── [3/8] SAP AI proxy token ──────────────────────────────────────────────────
echo [3/8] SAP AI Proxy configuration
echo.
echo  Enter your SAP AI proxy auth token (UUID format).
echo  Contact your team lead or the ECS AI team to obtain one.
echo  Leave blank to configure manually later in settings.json.
echo.
set /p "SAP_TOKEN=  SAP AI Token: "
if "!SAP_TOKEN!"=="" (
    echo  WARNING: No token entered. Edit settings.json manually after install.
    set "SAP_TOKEN=ENTER-YOUR-SAP-AI-TOKEN-HERE"
)
echo.

:: Proxy URL
echo  SAP AI Proxy URL
echo  (Press Enter for default: http://localhost:6655/anthropic/)
set /p "PROXY_URL=  Proxy URL: "
if "!PROXY_URL!"=="" set "PROXY_URL=http://localhost:6655/anthropic/"
echo  Using: !PROXY_URL!
echo.

:: ── [4/8] Install Python packages ─────────────────────────────────────────────
echo [4/8] Installing Python packages...
echo.

:: Try offline first (packages folder in hana_tool sibling directory)
set "PKG_DIR=!SCRIPT_DIR!\..\HANA Tool AI\hana_tool\packages"
if not exist "!PKG_DIR!" set "PKG_DIR=!SCRIPT_DIR!\packages"

:: anthropic (required)
echo  Installing anthropic (required)...
if exist "!PKG_DIR!" (
    pip install anthropic --find-links "!PKG_DIR!" --no-index --quiet 2>nul
    if errorlevel 1 pip install anthropic --quiet
) else (
    pip install anthropic --quiet
)
if errorlevel 1 (
    echo  ERROR: Failed to install anthropic.
    echo  Check your network connection or pip configuration.
    pause
    exit /b 1
)
echo  anthropic -- OK

:: python-pptx (optional)
echo  Installing python-pptx (optional - for PowerPoint export)...
pip install python-pptx --quiet 2>nul
if errorlevel 1 (
    echo  WARNING: python-pptx not installed. PowerPoint export unavailable.
) else (
    echo  python-pptx -- OK
)

:: Pillow (optional - for SAP logo display in UI header)
echo  Installing Pillow (optional - for logo display in app header)...
pip install Pillow --quiet 2>nul
if errorlevel 1 (
    echo  WARNING: Pillow not installed. Logo in app header may not display.
) else (
    echo  Pillow -- OK
)
echo.

:: ── [5/8] Create directory structure ──────────────────────────────────────────
echo [5/8] Creating directory structure...

mkdir "!WORK_DIR!" 2>nul
mkdir "!WORK_DIR!\HANA_Analysis_report_generator" 2>nul
mkdir "!WORK_DIR!\HANA_Analysis_report_generator\Previous versions" 2>nul
mkdir "!WORK_DIR!\HANA Health Check Reports" 2>nul
mkdir "!WORK_DIR!\Results" 2>nul

if not exist "!WORK_DIR!" (
    echo  ERROR: Could not create working directory: !WORK_DIR!
    echo  Try running as Administrator or choose a different path.
    pause
    exit /b 1
)
echo  Directories created OK.
echo.

:: ── [6/8] Copy files ──────────────────────────────────────────────────────────
echo [6/8] Copying files...
set "COPY_OK=1"

:: Main application file
if exist "!SCRIPT_DIR!\hana_analysis_app_v6.02.py" (
    copy /y "!SCRIPT_DIR!\hana_analysis_app_v6.02.py" "!WORK_DIR!\HANA_Analysis_report_generator\" >nul
    echo  hana_analysis_app_v6.02.py ... OK
) else (
    echo  ERROR: hana_analysis_app_v6.02.py not found in installer folder.
    set "COPY_OK=0"
)

:: Prompt template (check sibling parent dir first, then installer dir)
if exist "!PARENT_DIR!\HANA_HealthCheck_Prompt_Template.md" (
    copy /y "!PARENT_DIR!\HANA_HealthCheck_Prompt_Template.md" "!WORK_DIR!\" >nul
    echo  HANA_HealthCheck_Prompt_Template.md ... OK
) else if exist "!SCRIPT_DIR!\HANA_HealthCheck_Prompt_Template.md" (
    copy /y "!SCRIPT_DIR!\HANA_HealthCheck_Prompt_Template.md" "!WORK_DIR!\" >nul
    echo  HANA_HealthCheck_Prompt_Template.md ... OK
) else (
    echo  ERROR: HANA_HealthCheck_Prompt_Template.md not found.
    echo  Expected in: !PARENT_DIR!\ or !SCRIPT_DIR!\
    set "COPY_OK=0"
)

:: HANA latest release file
if exist "!PARENT_DIR!\HANA_latest_release.txt" (
    copy /y "!PARENT_DIR!\HANA_latest_release.txt" "!WORK_DIR!\" >nul
    echo  HANA_latest_release.txt ... OK
) else if exist "!SCRIPT_DIR!\HANA_latest_release.txt" (
    copy /y "!SCRIPT_DIR!\HANA_latest_release.txt" "!WORK_DIR!\" >nul
    echo  HANA_latest_release.txt ... OK
) else (
    echo  WARNING: HANA_latest_release.txt not found. Add it manually to !WORK_DIR!\
)

:: SAP logo (optional)
if exist "!PARENT_DIR!\SAP_LOGO.png" (
    copy /y "!PARENT_DIR!\SAP_LOGO.png" "!WORK_DIR!\" >nul
    echo  SAP_LOGO.png ... OK
) else if exist "!SCRIPT_DIR!\SAP_LOGO.png" (
    copy /y "!SCRIPT_DIR!\SAP_LOGO.png" "!WORK_DIR!\" >nul
    echo  SAP_LOGO.png ... OK
) else (
    echo  (SAP_LOGO.png not found - optional, app works without it)
)

:: Documentation guide
if exist "!SCRIPT_DIR!\HANA_Analysis_App_v6.02_Guide.html" (
    copy /y "!SCRIPT_DIR!\HANA_Analysis_App_v6.02_Guide.html" "!WORK_DIR!\HANA_Analysis_report_generator\" >nul
    echo  HANA_Analysis_App_v6.02_Guide.html ... OK
) else if exist "!SCRIPT_DIR!\HANA_Analysis_App_Deployment_Guide.html" (
    copy /y "!SCRIPT_DIR!\HANA_Analysis_App_Deployment_Guide.html" "!WORK_DIR!\HANA_Analysis_report_generator\" >nul
    echo  HANA_Analysis_App_Deployment_Guide.html ... OK
)

if "!COPY_OK!"=="0" (
    echo.
    echo  CRITICAL: Required files are missing. Place all source files in the
    echo  same folder as this installer and retry.
    pause
    exit /b 1
)
echo.

:: ── [7/8] Patch paths and write settings.json ─────────────────────────────────
echo [7/8] Patching paths in app and writing settings.json...

set "APP_PY=!WORK_DIR!\HANA_Analysis_report_generator\hana_analysis_app_v6.02.py"
set "USER_PROFILE=%USERPROFILE%"

python -c "
import sys, re
app_py      = sys.argv[1]
work_dir    = sys.argv[2]
user_profile= sys.argv[3]

with open(app_py, 'r', encoding='utf-8') as f:
    src = f.read()

# Patch WORKING_DIR
src = re.sub(
    r'(WORKING_DIR\s*=\s*Path\s*\()r\"[^\"]+\"(\))',
    r'\1r\"' + work_dir.replace('\\\\', '\\\\\\\\') + r'\"' + r'\2',
    src
)
# Patch SETTINGS_FILE
src = re.sub(
    r'(SETTINGS_FILE\s*=\s*Path\s*\()r\"[^\"]+\"(\))',
    r'\1r\"' + user_profile.replace('\\\\', '\\\\\\\\') + r'\\\\.claude\\\\settings.json\"' + r'\2',
    src
)

with open(app_py, 'w', encoding='utf-8') as f:
    f.write(src)
print('Paths patched OK')
" "!APP_PY!" "!WORK_DIR!" "!USER_PROFILE!"

if errorlevel 1 (
    echo  WARNING: Automatic path patching failed.
    echo  Edit WORKING_DIR and SETTINGS_FILE manually in the .py file.
) else (
    echo  Paths patched OK.
)

:: Write settings.json
if not exist "%USERPROFILE%\.claude" mkdir "%USERPROFILE%\.claude"
(
echo {
echo   "env": {
echo     "ANTHROPIC_BASE_URL": "!PROXY_URL!",
echo     "ANTHROPIC_AUTH_TOKEN": "!SAP_TOKEN!",
echo     "ANTHROPIC_MODEL": "claude-sonnet-latest"
echo   }
echo }
) > "%USERPROFILE%\.claude\settings.json"
echo  settings.json written to: %USERPROFILE%\.claude\settings.json
echo.

:: ── [8/8] Launcher and shortcut ───────────────────────────────────────────────
echo [8/8] Creating launcher and desktop shortcut...

(
echo @echo off
echo title SAP HANA Full Analysis Report Generator v6.02
echo cd /d "!WORK_DIR!\HANA_Analysis_report_generator"
echo echo.
echo echo  Starting SAP HANA Full Analysis Report Generator v6.02...
echo echo  Close this window to stop the app.
echo echo.
echo python hana_analysis_app_v6.02.py
echo pause
) > "!WORK_DIR!\run_hana_analysis_app_v6.02.bat"
echo  Launcher created: !WORK_DIR!\run_hana_analysis_app_v6.02.bat

:: Desktop shortcut
set "SHORTCUT=%USERPROFILE%\Desktop\HANA Analysis App v6.02.lnk"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '!WORK_DIR!\run_hana_analysis_app_v6.02.bat'; $s.WorkingDirectory = '!WORK_DIR!\HANA_Analysis_report_generator'; $s.Description = 'SAP HANA Full Analysis Report Generator v6.02'; $s.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  Desktop shortcut created: "HANA Analysis App v6.02"
) else (
    echo  (Desktop shortcut could not be created - use run_hana_analysis_app_v6.02.bat)
)
echo.

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo  =================================================================
echo   Installation complete!
echo  =================================================================
echo.
echo   Working directory : !WORK_DIR!
echo   App location      : !WORK_DIR!\HANA_Analysis_report_generator\
echo   Launcher          : !WORK_DIR!\run_hana_analysis_app_v6.02.bat
echo   Desktop shortcut  : %USERPROFILE%\Desktop\HANA Analysis App v6.02.lnk
echo   settings.json     : %USERPROFILE%\.claude\settings.json
echo   HC input folder   : !WORK_DIR!\HANA Health Check Reports\
echo   Reports output    : !WORK_DIR!\Results\
echo.
echo   NEXT STEPS:
echo   1. If a token placeholder was used, edit settings.json and
echo      replace ENTER-YOUR-SAP-AI-TOKEN-HERE with your real SAP AI token.
echo   2. Verify the SAP AI proxy is running at: !PROXY_URL!
echo   3. Double-click "HANA Analysis App v6.02" on the Desktop to launch.
echo   4. Place HANA Health Check .txt files in:
echo        !WORK_DIR!\HANA Health Check Reports\
echo   5. Browse, select a health check file, and click Generate.
echo.
echo   PACKAGE VERSIONS INSTALLED:
python -c "import anthropic; print('   anthropic:', anthropic.__version__)" 2>nul
python -c "import pptx; print('   python-pptx:', pptx.__version__)" 2>nul
python -c "import PIL; print('   Pillow:', PIL.__version__)" 2>nul
echo.
echo   See the full documentation guide:
echo   !WORK_DIR!\HANA_Analysis_report_generator\HANA_Analysis_App_v6.02_Guide.html
echo.
pause
endlocal
