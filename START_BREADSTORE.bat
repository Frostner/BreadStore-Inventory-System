@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BreadStore - Admin and Customer

echo ========================================================
echo       BREADSTORE - ADMIN + CUSTOMER WEBSITE
echo ========================================================
echo.
echo IMPORTANT: Stop any older BreadStore server with Ctrl+C.
echo.

REM A brand-new single-folder installation can reuse the old database.
REM Copy only on the first run, and never overwrite an existing new database.
if not exist "data\breadstore.db" (
    if exist "..\BreadStore-Inventory\data\breadstore.db" (
        if not exist "data" mkdir "data"
        copy /Y "..\BreadStore-Inventory\data\breadstore.db" "data\breadstore.db" >nul
        if errorlevel 1 (
            echo Warning: Could not copy your existing database.
        ) else (
            echo Copied your existing inventory data and admin account.
            echo Your original database remains untouched.
        )
    ) else if exist "D:\BreadStore-Inventory-System\BreadStore-Inventory\data\breadstore.db" (
        if not exist "data" mkdir "data"
        copy /Y "D:\BreadStore-Inventory-System\BreadStore-Inventory\data\breadstore.db" "data\breadstore.db" >nul
        if errorlevel 1 (
            echo Warning: Could not copy your existing database.
        ) else (
            echo Copied your existing inventory data and admin account.
            echo Your original database remains untouched.
        )
    )
)

REM Reuse the user's already-installed environment if it is next to this folder.
set "PY_EXE="
if exist "..\.venv\Scripts\python.exe" set "PY_EXE=..\.venv\Scripts\python.exe"
if not defined PY_EXE if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
if not defined PY_EXE (
    echo Creating a Python environment... Please wait.
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo ERROR: Python is not installed or is not on PATH.
            echo Install Python 3.11+ and reopen this file.
            goto :error
        )
        python -m venv .venv
    )
    if errorlevel 1 goto :error
    set "PY_EXE=.venv\Scripts\python.exe"
)

echo Installing or checking Python requirements...
"%PY_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo --------------------------------------------------------
echo Admin:     http://127.0.0.1:8000/
echo Customer:  http://127.0.0.1:8000/shop
echo --------------------------------------------------------
echo.
echo FIRST TIME: The admin email and a one-time password
 echo may appear below. Save them to log in.
echo If your old database was copied, use your old admin login.
echo Keep this window open while using the websites.
echo Press Ctrl+C here to stop both websites.
echo.
"%PY_EXE%" -m uvicorn app:app --reload
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Something prevented BreadStore from starting.
echo Take a screenshot of the error to ask for help.
pause
exit /b 1
