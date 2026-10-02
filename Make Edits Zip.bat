@echo off
rem Make Edits Zip - double-click to pack what was added in the editor into a dated zip beside this file.
rem   Makes QuestEdits_<date>_<time>.zip in this folder: every new or changed file of packs/TheQuest (new pictures,
rem   items, creatures, spells, tiles, maps ...) and every pack made new in the editor. Send that zip on.
rem   Needs only Python 3.10+ (the same Python the game uses). Nothing in the game folders is changed.
setlocal EnableExtensions
cd /d "%~dp0"
title Make Edits Zip

set "PY="
rem The py launcher first, then python on PATH (skipping the Microsoft Store stub), then the default install folders.
py -3 -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1 && set "PY=python"
if not defined PY for %%V in (314 313 312 311 310) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe""
)
if not defined PY for %%V in (314 313 312 311 310) do (
    if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" set "PY="%ProgramFiles%\Python%%V\python.exe""
)
if not defined PY (
    echo Python isn't installed. It is the same Python that runs the game: run "Play The Quest Deluxe.bat" once
    echo in the TheQuestDeluxe folder, which offers to install it, then run this again.
    echo.
    pause
    exit /b 1
)

echo Packing what was added in the editor...
echo.
%PY% "%~dp0tools\pack_edits_zip.py"
set "RESULT=%errorlevel%"
echo.
if "%RESULT%"=="0" (
    for /f "delims=" %%Z in ('dir /b /o-d "%~dp0QuestEdits_*.zip" 2^>nul') do (
        explorer /select,"%~dp0%%Z"
        goto shown
    )
)
:shown
pause
exit /b %RESULT%
