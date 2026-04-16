@echo off
chcp 65001 >nul
cd /d %~dp0
echo ???? AI ????...
python main.py
pause
