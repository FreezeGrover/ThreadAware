@echo off
setlocal
where threadaware >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  threadaware
) else (
  echo ThreadAware is not installed in this environment.
  echo Run: pip install -e .
  exit /b 1
)
