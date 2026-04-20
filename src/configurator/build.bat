@echo off
setlocal

echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (echo pip install failed & exit /b 1)

echo Building executable...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "RobotConfigurator" ^
  --hidden-import serial.tools.list_ports ^
  --hidden-import mpremote ^
  configurator.py
if errorlevel 1 (echo PyInstaller failed & exit /b 1)

echo.
echo Done. Executable: dist\RobotConfigurator.exe
