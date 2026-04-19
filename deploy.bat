@echo off
:: Deploy robot or controller firmware to a connected ESP32.
::
:: Usage:
::   deploy.bat robot      Deploy the robot firmware
::   deploy.bat controller Deploy the controller firmware
::
:: Dependencies:
::   mpremote   pip install mpremote
::
:: Before running:
::   - Edit src\<board>\config.json (copied from config.json.example)
::   - For the robot, also create mecanum.json on the device

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "SHARED_DIR=%SCRIPT_DIR%\src\shared"

set "BOARD=%~1"
if "%BOARD%"=="" goto usage
if "%BOARD%"=="robot" goto board_ok
if "%BOARD%"=="controller" goto board_ok
:usage
echo USAGE: %~nx0 ^<robot^|controller^>
exit /b 1
:board_ok

set "BOARD_DIR=%SCRIPT_DIR%\src\%BOARD%"

where mpremote >nul 2>&1
if errorlevel 1 (
    echo ERROR: mpremote not found. Install with: pip install mpremote
    exit /b 1
)

if not exist "%BOARD_DIR%\config.json" (
    echo ERROR: %BOARD_DIR%\config.json not found.
    echo   Copy config.json.example to config.json and fill in your values.
    exit /b 1
)

echo Deploying %BOARD% firmware...

cd /d "%SHARED_DIR%"
mpremote resume cp boot.py config.py :/ + cp -r lib :/
if errorlevel 1 exit /b 1

cd /d "%BOARD_DIR%"
if "%BOARD%"=="robot" (
    mpremote resume cp main.py config.json : + cp -r lib/ :lib/
) else (
    mpremote resume cp main.py config.json :
)
if errorlevel 1 exit /b 1

echo Done. Reset the device to apply: mpremote reset
