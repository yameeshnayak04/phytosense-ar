@echo off
REM Start PhytoSense AR on http://localhost:8000
cd /d "%~dp0backend"
if exist .venv\Scriptsctivate call .venv\Scriptsctivate
start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
