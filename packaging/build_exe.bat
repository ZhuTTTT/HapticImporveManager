@echo off
rem Build HapticImproveManager as onedir exe. Run from repo root.
python -m pip install "pyinstaller>=6.0"
python -m PyInstaller --noconfirm --clean --windowed --name HapticImproveManager --collect-all qfluentwidgets app.py
echo.
echo Output: dist\HapticImproveManager\HapticImproveManager.exe
