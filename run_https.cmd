@echo off
REM HTTPS mode so a phone on the same Wi-Fi can use its camera
cd /d "%~dp0"
if exist backend\.venv\Scriptsctivate call backend\.venv\Scriptsctivate
if not exist backend\certs\cert.pem python scripts\make_cert.py
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile certs\key.pem --ssl-certfile certs\cert.pem
