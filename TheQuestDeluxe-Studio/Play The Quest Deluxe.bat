@echo off
rem The Quest Deluxe - Windows launcher. Double-click to play.
rem   1. finds Python 3.10+ (or offers to install Python 3.12 with winget)
rem   2. the first time, installs pygame-ce into the .deps folder here (from the bundled wheels)
rem   3. starts the game
setlocal EnableExtensions
cd /d "%~dp0"
title The Quest Deluxe

set "PY="
rem The py launcher first, then python on PATH (skipping the Microsoft Store stub), then the default install folders.
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=python"
if not defined PY for %%V in (314 313 312 311 310) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe""
)
if not defined PY for %%V in (314 313 312 311 310) do (
    if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" set "PY="%ProgramFiles%\Python%%V\python.exe""
)
if defined PY goto have_python

echo The Quest Deluxe needs Python 3.10 or newer, and it isn't installed.
echo.
where winget >nul 2>&1
if errorlevel 1 goto manual_python
choice /c YN /m "Install Python 3.12 now (for this Windows user, with winget)"
if errorlevel 2 goto manual_python
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
    goto have_python
)
echo.
echo Python didn't install. Please install it yourself, then run this again.
:manual_python
echo Download Python from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
start "" https://www.python.org/downloads/
pause
exit /b 1

:have_python
set "PYTHONPATH=%~dp0.deps"
%PY% -c "import pygame" >nul 2>&1
if not errorlevel 1 goto run
echo Setting up pygame-ce (first run only)...
%PY% -m pip install --disable-pip-version-check --no-index --find-links "%~dp0windows\wheels" --target "%~dp0.deps" pygame-ce >nul 2>&1
%PY% -c "import pygame" >nul 2>&1
if not errorlevel 1 goto run
echo No bundled package fits this Python, downloading pygame-ce...
%PY% -m pip install --disable-pip-version-check --target "%~dp0.deps" pygame-ce
%PY% -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Couldn't install pygame-ce. Check the internet connection and try again.
    pause
    exit /b 1
)

:run
rem Started with no terminal window of its own (pythonw), so there is nothing to close by mistake; an error is shown in a box and kept in your user folder.
set "PYW=%PY%"
set "PYW=%PYW:python.exe=pythonw.exe%"
if /i "%PYW%"=="py -3" set "PYW=pyw -3"
if /i "%PYW%"=="python" set "PYW=pythonw"
start "" %PYW% run_deluxe.py %*
exit /b 0
