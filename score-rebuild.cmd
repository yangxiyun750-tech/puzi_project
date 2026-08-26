@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
  "%PROJECT_ROOT%.venv\Scripts\python.exe" -m score_rebuild %*
) else (
  py -3.12 -m score_rebuild %*
)
exit /b %ERRORLEVEL%
