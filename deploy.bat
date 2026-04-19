@echo off
:: Deploy robot or controller firmware to a connected ESP32.
::
:: Usage:
::   deploy.bat robot               Deploy the robot firmware
::   deploy.bat controller          Deploy the controller firmware
::   deploy.bat robot -u COM3       Specify port when multiple devices connected
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
set "USB_PORT="

set "BOARD=%~1"
if "%BOARD%"=="" goto usage
if "%BOARD%"=="robot" goto board_ok
if "%BOARD%"=="controller" goto board_ok
:usage
echo USAGE: %~nx0 ^<robot^|controller^> [-u PORT]
echo   -u PORT   Serial port (e.g. COM3, COM4)
exit /b 1
:board_ok
shift

:parse_args
if "%~1"=="" goto args_done
if "%~1"=="-u" (
    if "%~2"=="" (
        echo ERROR: -u requires a port argument ^(e.g. -u COM3^)
        exit /b 1
    )
    set "USB_PORT=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--usb" (
    if "%~2"=="" (
        echo ERROR: --usb requires a port argument ^(e.g. --usb COM3^)
        exit /b 1
    )
    set "USB_PORT=%~2"
    shift
    shift
    goto parse_args
)
echo USAGE: %~nx0 ^<robot^|controller^> [-u PORT]
exit /b 1
:args_done

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

set "MPREMOTE=mpremote"
if not "%USB_PORT%"=="" set "MPREMOTE=mpremote connect %USB_PORT%"

echo Deploying %BOARD% firmware...
if not "%USB_PORT%"=="" echo   Port: %USB_PORT%

cd /d "%SHARED_DIR%"
%MPREMOTE% resume cp boot.py config.py :/ + cp -r lib :/
if errorlevel 1 exit /b 1

cd /d "%BOARD_DIR%"
if "%BOARD%"=="robot" (
    %MPREMOTE% resume cp main.py config.json : + cp -r lib/ :lib/
) else (
    %MPREMOTE% resume cp main.py config.json :
)
if errorlevel 1 exit /b 1

echo Done. Reset the device to apply: %MPREMOTE% reset
