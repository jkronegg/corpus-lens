@echo off
setlocal

REM Dispatcher pour les skills fetch-*
REM Usage: fetch <source> <requête> [options]
REM
REM Exemples:
REM   fetch dhs "affaire des colonels"
REM   fetch wikipedia "affaire des colonels"
REM   fetch dodis-person "Jean Pascal Delamuraz"
REM   fetch elitesuisse "Thierry Pun"
REM   fetch enewspaper "affaire des colonels" --start-year 1900
REM   fetch url "https://example.com/document.pdf"
REM   fetch swissvote 639

set "ROOT=%~dp0"
python -u "%ROOT%fetch.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%

