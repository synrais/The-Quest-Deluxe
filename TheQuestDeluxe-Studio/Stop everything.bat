@echo off
rem Stops everything started from this game folder, so that the folders can be deleted. Double-click it.
rem (The programs it stops: the Studio, the game, the compare program and DOSBox, and anything an earlier run left behind.)
title Stop everything from this folder
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop everything.ps1"
echo.
pause
