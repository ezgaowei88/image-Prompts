@echo off
chcp 65001 >nul
title Image Prompts 本地服务器
cd /d "%~dp0"

echo ════════════════════════════════════════════════
echo   Image Prompts 本地服务器
echo ════════════════════════════════════════════════
echo.
echo   正在启动服务器...
echo   浏览器访问: http://localhost:8000
echo   按 Ctrl+C 停止服务器
echo.

start "" http://localhost:8000

python server.py

pause
