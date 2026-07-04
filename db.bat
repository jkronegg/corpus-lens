@echo off
setlocal

REM Exécute la commande stats du skill manage-named-entities-db
set "ROOT=%~dp0"
python -u "%ROOT%.agents\skills\manage-named-entities-db\scripts\manage_named_entities_db.py" %1 %2 %3 %4 %5 %6 %7 %8 %9
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%

