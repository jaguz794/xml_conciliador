@echo off
setlocal
cd /d "%~dp0\frontend"

if not exist "node_modules" (
  echo [ERROR] No existe frontend\node_modules
  echo Ejecuta primero: npm install
  pause
  exit /b 1
)

echo Iniciando frontend en http://127.0.0.1:5173
call npm run dev

endlocal

