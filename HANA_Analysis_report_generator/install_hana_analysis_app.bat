@echo off
setlocal EnableDelayedExpansion
title HANA Analysis Report Generator -- Installer

:: ============================================================
:: HANA Analysis Report Generator v6.01 - Windows Installer
:: Run as Administrator for best results
:: ============================================================

echo.
echo  =================================================================
echo   HANA Analysis Report Generator -- Installer v6.01
echo   RDE LAC / SAP ECS
echo  =================================================================
echo.

:: ── Source directory (same folder as this .bat) ──────────────────────────────
set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: ── Check Python ─────────────────────────────────────────────────────────────
echo [1/7] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Found: %PY_VER%
echo.

:: ── Ask for working directory ─────────────────────────────────────────────────
echo [2/7] Working directory setup
echo.
echo  Enter the full path for the HANA Analysis App working directory.
echo  Example: C:\HANA_Analysis_App
echo  (Press Enter to use default: C:\HANA_Analysis_App)
echo.
set /p "WORK_DIR=  Working directory: "
if "!WORK_DIR!"=="" set "WORK_DIR=C:\HANA_Analysis_App"
:: Normalize: remove trailing backslash
if "!WORK_DIR:~-1!"=="\" set "WORK_DIR=!WORK_DIR:~0,-1!"
echo  Using: !WORK_DIR!
echo.

:: ── Ask for SAP AI token ──────────────────────────────────────────────────────
echo [3/7] SAP AI Proxy token
echo.
echo  Enter your SAP AI proxy auth token (UUID format).
echo  Contact your team lead or the ECS AI team to obtain one.
echo.
set /p "SAP_TOKEN=  SAP AI Token: "
if "!SAP_TOKEN!"=="" (
    echo  WARNING: No token entered. You must add it manually to:
    echo    %%USERPROFILE%%\.claude\settings.json
    set "SAP_TOKEN=ENTER-YOUR-SAP-AI-TOKEN-HERE"
)
echo.

:: ── Ask for proxy URL ─────────────────────────────────────────────────────────
echo  SAP AI Proxy URL (Press Enter for default: http://localhost:6655/anthropic/)
set /p "PROXY_URL=  Proxy URL: "
if "!PROXY_URL!"=="" set "PROXY_URL=http://localhost:6655/anthropic/"
echo  Using: !PROXY_URL!
echo.

:: ── Install Python packages ───────────────────────────────────────────────────
echo [4/7] Installing Python packages...
echo.
echo  Installing anthropic...
pip install anthropic --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install anthropic. Check your network / pip configuration.
    pause
    exit /b 1
)
echo  anthropic installed OK.

echo  Installing python-pptx (optional - for PowerPoint export)...
pip install python-pptx --quiet
if errorlevel 1 (
    echo  WARNING: python-pptx installation failed. PowerPoint export will be unavailable.
) else (
    echo  python-pptx installed OK.
)
echo.

:: ── Create directory structure ────────────────────────────────────────────────
echo [5/7] Creating directory structure...
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

:: ── Copy files ────────────────────────────────────────────────────────────────
echo [6/7] Copying files...

:: Required files
set "COPY_OK=1"

if exist "%SCRIPT_DIR%\hana_analysis_app_v6.01.py" (
    copy /y "%SCRIPT_DIR%\hana_analysis_app_v6.01.py" "!WORK_DIR!\HANA_Analysis_report_generator\" >nul
    echo  hana_analysis_app_v6.01.py ... OK
) else if exist "%SCRIPT_DIR%\hana_analysis_app_v6.py" (
    copy /y "%SCRIPT_DIR%\hana_analysis_app_v6.py" "!WORK_DIR!\HANA_Analysis_report_generator\" >nul
    echo  hana_analysis_app_v6.py ... OK (v6.01 not found, used v6)
) else (
    echo  ERROR: App .py file not found in installer directory.
    set "COPY_OK=0"
)

if exist "%SCRIPT_DIR%\..\HANA_HealthCheck_Prompt_Template.md" (
    copy /y "%SCRIPT_DIR%\..\HANA_HealthCheck_Prompt_Template.md" "!WORK_DIR!\" >nul
    echo  HANA_HealthCheck_Prompt_Template.md ... OK
) else if exist "%SCRIPT_DIR%\HANA_HealthCheck_Prompt_Template.md" (
    copy /y "%SCRIPT_DIR%\HANA_HealthCheck_Prompt_Template.md" "!WORK_DIR!\" >nul
    echo  HANA_HealthCheck_Prompt_Template.md ... OK
) else (
    echo  ERROR: HANA_HealthCheck_Prompt_Template.md not found.
    set "COPY_OK=0"
)

if exist "%SCRIPT_DIR%\..\HANA_latest_release.txt" (
    copy /y "%SCRIPT_DIR%\..\HANA_latest_release.txt" "!WORK_DIR!\" >nul
    echo  HANA_latest_release.txt ... OK
) else if exist "%SCRIPT_DIR%\HANA_latest_release.txt" (
    copy /y "%SCRIPT_DIR%\HANA_latest_release.txt" "!WORK_DIR!\" >nul
    echo  HANA_latest_release.txt ... OK
) else (
    echo  WARNING: HANA_latest_release.txt not found. Add it manually to !WORK_DIR!\
)

if exist "%SCRIPT_DIR%\..\SAP_LOGO.png" (
    copy /y "%SCRIPT_DIR%\..\SAP_LOGO.png" "!WORK_DIR!\" >nul
    echo  SAP_LOGO.png ... OK
) else if exist "%SCRIPT_DIR%\SAP_LOGO.png" (
    copy /y "%SCRIPT_DIR%\SAP_LOGO.png" "!WORK_DIR!\" >nul
    echo  SAP_LOGO.png ... OK
) else (
    echo  (SAP_LOGO.png not found - optional, reports will work without it)
)

:: Copy deployment guide
if exist "%SCRIPT_DIR%\HANA_Analysis_App_Deployment_Guide.html" (
    copy /y "%SCRIPT_DIR%\HANA_Analysis_App_Deployment_Guide.html" "!WORK_DIR!\HANA_Analysis_report_generator\" >nul
    echo  HANA_Analysis_App_Deployment_Guide.html ... OK
)

if "!COPY_OK!"=="0" (
    echo.
    echo  CRITICAL: Required files are missing. Ensure all source files are in the
    echo  same folder as this installer before running it.
    pause
    exit /b 1
)
echo.

:: ── Patch paths in the .py file ───────────────────────────────────────────────
echo [7/7] Patching paths in the app...

:: Determine which .py file was copied
set "APP_PY=!WORK_DIR!\HANA_Analysis_report_generator\hana_analysis_app_v6.01.py"
if not exist "!APP_PY!" set "APP_PY=!WORK_DIR!\HANA_Analysis_report_generator\hana_analysis_app_v6.py"

:: Get current user profile path
set "USER_PROFILE=%USERPROFILE%"

:: Use Python to do the path patching (safer than batch string replace)
python -c "
import sys, re
app_py = sys.argv[1]
work_dir = sys.argv[2]
user_profile = sys.argv[3]

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
    echo  WARNING: Automatic path patching failed. Edit the .py file manually.
    echo  See the Deployment Guide for details.
) else (
    echo  Paths patched OK.
)
echo.

:: ── Write settings.json ───────────────────────────────────────────────────────
echo  Writing settings.json...
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

:: ── Create run.bat launcher ───────────────────────────────────────────────────
(
echo @echo off
echo cd /d "!WORK_DIR!\HANA_Analysis_report_generator"
echo python hana_analysis_app_v6.01.py
echo pause
) > "!WORK_DIR!\run_hana_analysis_app.bat"

:: Create run.bat for v6 fallback name
if not exist "!WORK_DIR!\HANA_Analysis_report_generator\hana_analysis_app_v6.01.py" (
    (
    echo @echo off
    echo cd /d "!WORK_DIR!\HANA_Analysis_report_generator"
    echo python hana_analysis_app_v6.py
    echo pause
    ) > "!WORK_DIR!\run_hana_analysis_app.bat"
)

echo  Launcher created: !WORK_DIR!\run_hana_analysis_app.bat
echo.

:: ── Create desktop shortcut ───────────────────────────────────────────────────
echo  Creating desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\HANA Analysis App.lnk"
set "LAUNCHER=!WORK_DIR!\run_hana_analysis_app.bat"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '!LAUNCHER!'; $s.WorkingDirectory = '!WORK_DIR!\HANA_Analysis_report_generator'; $s.Description = 'HANA Analysis Report Generator'; $s.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  Desktop shortcut created OK.
) else (
    echo  (Desktop shortcut could not be created - use run_hana_analysis_app.bat instead)
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
echo   Launcher          : !WORK_DIR!\run_hana_analysis_app.bat
echo   Desktop shortcut  : %USERPROFILE%\Desktop\HANA Analysis App.lnk
echo   settings.json     : %USERPROFILE%\.claude\settings.json
echo.
echo   NEXT STEPS:
echo   1. Verify the SAP AI proxy is running on !PROXY_URL!
echo   2. If the token placeholder was used, edit settings.json
echo      and replace ENTER-YOUR-SAP-AI-TOKEN-HERE with your real token.
echo   3. Double-click "HANA Analysis App" on the Desktop to launch.
echo   4. Place HANA Health Check .txt files in:
echo      "!WORK_DIR!\HANA Health Check Reports\"
echo.
echo   See the Deployment Guide for full documentation:
echo   !WORK_DIR!\HANA_Analysis_report_generator\HANA_Analysis_App_Deployment_Guide.html
echo.
pause
endlocal
