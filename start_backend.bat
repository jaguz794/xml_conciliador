@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] No existe el entorno virtual en .venv
  echo Ejecuta primero la instalacion inicial.
  pause
  exit /b 1
)

echo Iniciando backend en http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

endlocal

