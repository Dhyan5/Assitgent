@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
if not exist ".venv\Scripts\pythonw.exe" goto missing
if not exist "main.py" goto missing
if not exist "config.yaml" goto missing
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set DO_NOT_TRACK=1
set PYTHONNOUSERSITE=1
set PYTHONDONTWRITEBYTECODE=1
if /I "%~1"=="debug" goto debug
start "" /LOW ".venv\Scripts\pythonw.exe" main.py
exit /b 0
:debug
".venv\Scripts\python.exe" main.py --debug
pause
exit /b
:missing
echo JARVIS cannot start: .venv, main.py or config.yaml is missing.
echo Follow README.md to provision the verified environment. Nothing was installed.
pause
exit /b 1
