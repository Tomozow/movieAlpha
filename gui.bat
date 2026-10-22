@echo off
setlocal
cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\pythonw.exe" set "PY=.venv\Scripts\pythonw.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY set "PY=pythonw"

"%PY%" -m moviealpha --gui
if errorlevel 1 (
  echo.
  echo GUI の起動に失敗しました。venv を作っている場合は:
  echo   python -m venv .venv
  echo   .venv\Scripts\Activate.ps1
  echo   pip install -e .
  echo FFmpeg が PATH にあることも確認してください。
  pause
)
