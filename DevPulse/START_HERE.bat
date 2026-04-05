@echo off
setlocal EnableDelayedExpansion
title DevPulse Installer
color 0A
chcp 65001 > nul 2>&1

echo.
echo  ============================================================
echo   DevPulse - One-Click Installer
echo   Everything will be installed automatically
echo  ============================================================
echo.

:: ── Save current folder ──────────────────────────────────────
set "DEVPULSE_DIR=%~dp0"
cd /d "%DEVPULSE_DIR%"

:: ════════════════════════════════════════════════════════════
:: STEP 1 — Check Python
:: ════════════════════════════════════════════════════════════
echo  [1/5] Checking Python...
python --version > nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo       OK: %%v
    goto :check_git
)

:: Python not found — try py launcher
py --version > nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=*" %%v in ('py --version 2^>^&1') do echo       OK: %%v
    set "PYTHON_CMD=py"
    goto :check_git
)

echo       Python not found. Installing automatically...
echo.

:: Try winget first (Windows 10/11)
winget --version > nul 2>&1
if %errorlevel% == 0 (
    echo       Using Windows Package Manager (winget)...
    winget install -e --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if !errorlevel! == 0 (
        echo       Python installed via winget
        :: Refresh PATH
        call refreshenv.cmd > nul 2>&1
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
        goto :check_git
    )
)

:: Fallback: download Python installer
echo       Downloading Python 3.11 installer from python.org...
set "PY_INSTALLER=%TEMP%\python_installer.exe"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%PY_INSTALLER%') }" 2>nul
if %errorlevel% == 0 (
    echo       Running Python installer (this may take a minute)...
    "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
    del "%PY_INSTALLER%" > nul 2>&1
    :: Refresh PATH for this session
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
    echo       Python installed successfully
) else (
    echo.
    echo  [ERROR] Could not download Python automatically.
    echo  Please install manually: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:check_git
:: ════════════════════════════════════════════════════════════
:: STEP 2 — Check Git
:: ════════════════════════════════════════════════════════════
echo.
echo  [2/5] Checking Git...
git --version > nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=*" %%v in ('git --version 2^>^&1') do echo       OK: %%v
    goto :install_deps
)

echo       Git not found. Installing automatically...

winget --version > nul 2>&1
if %errorlevel% == 0 (
    winget install -e --id Git.Git --silent --accept-source-agreements --accept-package-agreements
    set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin"
    echo       Git installed via winget
    goto :install_deps
)

:: Fallback: download Git
set "GIT_INSTALLER=%TEMP%\git_installer.exe"
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"
echo       Downloading Git...
powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%GIT_URL%', '%GIT_INSTALLER%') }" 2>nul
if %errorlevel% == 0 (
    "%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"
    del "%GIT_INSTALLER%" > nul 2>&1
    set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin"
    echo       Git installed successfully
) else (
    echo  [WARN] Could not install Git automatically.
    echo  Download from: https://git-scm.com/download/win
    echo  Then re-run this installer.
    pause
)

:install_deps
:: ════════════════════════════════════════════════════════════
:: STEP 3 — Install Python packages
:: ════════════════════════════════════════════════════════════
echo.
echo  [3/5] Installing Python packages...

:: Upgrade pip silently
python -m pip install --upgrade pip --quiet > nul 2>&1
py -m pip install --upgrade pip --quiet > nul 2>&1

:: Install from requirements.txt
if exist "%DEVPULSE_DIR%requirements.txt" (
    python -m pip install -r "%DEVPULSE_DIR%requirements.txt" --quiet 2>nul
    if !errorlevel! neq 0 (
        python -m pip install -r "%DEVPULSE_DIR%requirements.txt" --quiet --break-system-packages 2>nul
    )
    if !errorlevel! neq 0 (
        py -m pip install -r "%DEVPULSE_DIR%requirements.txt" --quiet 2>nul
    )
    echo       Packages installed
) else (
    python -m pip install psutil --quiet 2>nul
    echo       psutil installed
)

:: ════════════════════════════════════════════════════════════
:: STEP 4 — Git identity
:: ════════════════════════════════════════════════════════════
echo.
echo  [4/5] Checking git identity...
for /f "tokens=*" %%n in ('git config --global user.name 2^>nul') do set "GIT_NAME=%%n"
for /f "tokens=*" %%e in ('git config --global user.email 2^>nul') do set "GIT_EMAIL=%%e"

if "!GIT_NAME!" == "" (
    set /p GIT_NAME="       Enter your name for git commits: "
    git config --global user.name "!GIT_NAME!"
)
if "!GIT_EMAIL!" == "" (
    set /p GIT_EMAIL="       Enter your email for git commits: "
    git config --global user.email "!GIT_EMAIL!"
)
echo       Identity: !GIT_NAME! ^<!GIT_EMAIL!^>

:: ════════════════════════════════════════════════════════════
:: STEP 5 — Launch DevPulse Setup
:: ════════════════════════════════════════════════════════════
echo.
echo  [5/5] Launching DevPulse...
echo  ============================================================
echo.

:: Try python, then py
python "%DEVPULSE_DIR%cli.py" > nul 2>&1
if %errorlevel% == 0 (
    python "%DEVPULSE_DIR%cli.py"
) else (
    py "%DEVPULSE_DIR%cli.py"
)

echo.
echo  ============================================================
echo   DevPulse is set up! 
echo   Next time just run:  python cli.py
echo   Or double-click:     START_HERE.bat
echo  ============================================================
echo.
pause
