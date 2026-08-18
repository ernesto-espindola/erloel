@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  HANA TUI SQL Console - Offline Setup
echo ============================================
echo.

:: Check Python is available
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Install Python 3.9+ from https://python.org
        echo         Make sure to check "Add Python to PATH" during install.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

echo [INFO] Using Python:
%PYTHON% --version
echo.

:: Resolve script directory so paths work from any location
set SCRIPT_DIR=%~dp0
set PKG_DIR=%SCRIPT_DIR%packages

if not exist "%PKG_DIR%" (
    echo [ERROR] packages\ folder not found next to this script.
    echo         Expected: %PKG_DIR%
    pause
    exit /b 1
)

echo [INFO] Installing packages into: %SCRIPT_DIR%lib
echo.

%PYTHON% -m pip install --no-index --find-links="%PKG_DIR%" --target="%SCRIPT_DIR%lib" textual hdbcli
if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. Check the output above for details.
    pause
    exit /b 1
)

echo.
echo [INFO] Verifying installation...
%PYTHON% -c "import textual; print('  textual', textual.__version__, '- OK')"
if errorlevel 1 ( echo [ERROR] textual import failed. & pause & exit /b 1 )

%PYTHON% -c "import hdbcli; print('  hdbcli  - OK')"
if errorlevel 1 ( echo [ERROR] hdbcli import failed. & pause & exit /b 1 )

echo.
echo ============================================
echo  Setup complete.
echo  Run the app with:
echo    py hana_tui.py
echo ============================================
echo.
pause
