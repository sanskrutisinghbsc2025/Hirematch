@echo off
title HireMatch Platform
cd /d "%~dp0"
python run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while launching HireMatch.
    pause
)
