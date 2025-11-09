@echo off
REM Camera S3 Monitor Startup Script
REM Auto-start on Windows boot
REM Uses venv Python with all required libraries

cd /d "C:\camera-uploader\src"
"C:\camera-uploader\venv\Scripts\python.exe" main.py

REM Keep window open if there's an error
if %ERRORLEVEL% NEQ 0 pause