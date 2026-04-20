# Running the Configurator on Windows

> All instructions below are untested on Windows but should work.

## Prerequisites

Install **Python 3.12** from [python.org](https://www.python.org/downloads/windows/).
During installation, check **"Add Python to PATH"**.

## Option A — Run from source

Open a terminal (Command Prompt or PowerShell) in the `src/configurator/` directory.

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python configurator.py
```

The configurator resolves all paths relative to `configurator.py`, so it can be run from any working directory.

## Option B — Build a standalone .exe

Run `build.bat` from the `src/configurator/` directory. Python and the venv must already be set up (see Option A).

```bat
build.bat
```

The executable is written to `dist\RobotConfigurator.exe`. It can be copied anywhere and run without Python installed.

## Features

All features work natively on Windows — **Read Device**, **Write Config**, **Write Firmware**, and the **Flash** tab (Download, Flash MicroPython, Deploy Skeleton).
