@echo off
python "%~dp0recover.py" %*
exit /b %errorlevel%
