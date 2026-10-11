@echo off
setlocal
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

title jev-chat

if not exist ".venv\Scripts\python.exe" (
    echo [jev-chat] First run: checking for Python 3.12...
    py -3.12 --version > nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3.12 not found. Please install Python 3.12.x from https://www.python.org/downloads/
        echo          and make sure "py launcher" is checked during installation.
        echo          Then run this script again.
        pause
        exit /b 1
    )
    echo [jev-chat] Creating venv with Python 3.12 and installing dependencies...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [ERROR] Dependency install failed. See output above.
        pause
        exit /b 1
    )
    echo [jev-chat] Install done.
)

call ".venv\Scripts\activate.bat"

.venv\Scripts\python.exe -c "import sys; print('VENV_OK')" > nul 2>&1
if not "%errorlevel%"=="0" (
    echo [jev-chat] Venv python broken, rebuilding...
    rmdir /s /q .venv
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Rebuild venv failed.
        pause
        exit /b 1
    )
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [ERROR] Reinstall failed.
        pause
        exit /b 1
    )
)

echo [jev-chat] Preflight check...
.venv\Scripts\python.exe -u -c "import main; print('PREFLIGHT_OK')" > preflight.log 2>&1
if not "%errorlevel%"=="0" (
    echo [jev-chat] Preflight FAILED. See preflight.log:
    powershell -NoProfile -Command "Get-Content preflight.log -Tail 30"
    pause
    exit /b 1
)
echo [jev-chat] Preflight OK.

echo [jev-chat] Starting jev-chat (log -> jev-chat.log)...
.venv\Scripts\python.exe -u main.py > jev-chat.log 2>&1
set RC=%errorlevel%

echo.
echo [jev-chat] Exited with code %RC%.
if not "%RC%"=="0" (
    echo --- Last 30 lines of jev-chat.log ---
    powershell -NoProfile -Command "Get-Content jev-chat.log -Tail 30"
    echo --------------------------------------
    echo Send the red text above (or jev-chat.log) to me for diagnosis.
)
echo.
echo Press any key to close this window.
pause
