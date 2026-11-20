@echo off
rem Tobi desktop chat window (no console)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" run_desktop.py
