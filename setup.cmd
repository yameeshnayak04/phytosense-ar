@echo off
REM One-time setup: virtual environment + dependencies (no PyTorch needed)
cd /d "%~dp0backend"
if not exist .venv python -m venv .venv
call .venv\Scriptsctivate
python -m pip install --upgrade pip
pip install -r requirements.txt cryptography pytest httpx
if not exist .env copy .env.example .env
echo.
echo Setup done. Now run run.cmd
pause
