@echo off
rem HapticImproveManager launcher (pythonw, no console window)
rem 要求 pythonw 在 PATH 中(Python 官方安装包默认即是)
cd /d "%~dp0"
start "" pythonw app.py
