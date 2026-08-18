@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  HANA TUI SQL Console - Offline Setup
echo ============================================
echo.

:: ── Python check ────────────────────────────────────────────────────────────
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

:: ── Paths ────────────────────────────────────────────────────────────────────
set SCRIPT_DIR=%~dp0
set PKG_DIR=%SCRIPT_DIR%packages
set LIB_DIR=%SCRIPT_DIR%lib

if not exist "%PKG_DIR%" (
    echo [ERROR] packages\ folder not found next to this script.
    echo         Expected: %PKG_DIR%
    pause
    exit /b 1
)

:: ── Install all packages into lib\ ──────────────────────────────────────────
echo [INFO] Installing packages into: %LIB_DIR%
echo.

%PYTHON% -m pip install --no-index --find-links="%PKG_DIR%" --target="%LIB_DIR%" ^
    textual hdbcli anthropic

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. Check the output above for details.
    pause
    exit /b 1
)

:: ── Verify imports ───────────────────────────────────────────────────────────
echo.
echo [INFO] Verifying installation...

:: Write a small helper script to avoid backslash escape issues in -c strings
set VERIFY_PY=%TEMP%\hana_verify.py
(
    echo import sys
    echo sys.path.insert^(0, r'%LIB_DIR%'^)
    echo try:
    echo     import textual
    echo     print^('  textual', textual.__version__, '- OK'^)
    echo except Exception as e:
    echo     print^('  textual FAILED:', e^); sys.exit^(1^)
    echo try:
    echo     import hdbcli
    echo     print^('  hdbcli  - OK'^)
    echo except Exception as e:
    echo     print^('  hdbcli  FAILED:', e^); sys.exit^(1^)
    echo try:
    echo     import anthropic
    echo     print^('  anthropic', anthropic.__version__, '- OK'^)
    echo except Exception as e:
    echo     print^('  anthropic FAILED:', e^); sys.exit^(1^)
) > "%VERIFY_PY%"

%PYTHON% "%VERIFY_PY%"
if errorlevel 1 (
    del /q "%VERIFY_PY%" 2>nul
    echo.
    echo [ERROR] One or more packages failed to import. Check output above.
    pause
    exit /b 1
)
del /q "%VERIFY_PY%" 2>nul

:: ── Anthropic API key setup ──────────────────────────────────────────────────
echo.
echo ============================================
echo  AI Analysis Setup (optional)
echo ============================================
echo.
echo  The web console includes an "AI Analysis" feature that sends query
echo  results to Claude (claude-opus-4-8) for interpretation.
echo.
echo  To enable it you need an Anthropic API key from:
echo    https://console.anthropic.com/
echo.

:: Check if already set in the current session or system
if defined ANTHROPIC_API_KEY (
    echo [INFO] ANTHROPIC_API_KEY is already set in this session.
    goto :key_done
)

:: Check if set as a persistent user env variable
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v ANTHROPIC_API_KEY 2^>nul') do (
    set _REG_KEY=%%B
)
if defined _REG_KEY (
    echo [INFO] ANTHROPIC_API_KEY is already saved as a user environment variable.
    goto :key_done
)

set /p USER_KEY="  Enter your Anthropic API key (or press Enter to skip): "
if "!USER_KEY!"=="" (
    echo [INFO] Skipped. You can set ANTHROPIC_API_KEY later before starting the app.
    goto :key_done
)

:: Persist as a user environment variable (no admin required)
setx ANTHROPIC_API_KEY "!USER_KEY!" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Could not save key via setx. Set it manually:
    echo        set ANTHROPIC_API_KEY=^<your-key^>
) else (
    echo [INFO] API key saved as user environment variable ANTHROPIC_API_KEY.
    echo [INFO] It will be available in new terminal/cmd windows automatically.
)

:key_done

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo ============================================
echo  Setup complete.
echo.
echo  Start the TUI console with:
echo    py hana_tui.py
echo.
echo  Start the Web console with:
echo    py hana_tui_web.py
echo    then open http://127.0.0.1:5000
echo ============================================
echo.
pause
