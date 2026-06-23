@echo off
title Image Prompts Local Server
cd /d "%~dp0"

echo ==================================================
echo   Image Prompts Local Server
echo ==================================================
echo.
echo   Starting server...
echo   Visit: http://localhost:8000
echo   Press Ctrl+C to stop
echo.

start "" http://localhost:8000

python -X utf8 server.py

pause
