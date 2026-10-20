@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Missing backend virtual environment. Create it before opening the demo tool.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app.tools.demo_accounts
