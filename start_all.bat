@echo off
setlocal
cd /d "%~dp0"

start "Conciliador Backend" cmd /k ""%~dp0\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000"
start "Conciliador Frontend" cmd /k "cd /d "%~dp0\frontend" && npm run dev"

echo Backend y frontend lanzados en ventanas separadas.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173
pause

endlocal

