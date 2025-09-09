@echo off
echo Creating Task Scheduler entry...
echo.

REM Delete any existing task first
schtasks /delete /tn "RR_GU_Daily_Collection" /f >nul 2>&1

REM Create the daily task at 9 AM
schtasks /create /tn "RR_GU_Daily_Collection" /tr "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat" /sc daily /st 09:00 /f

echo.
if %errorlevel% == 0 (
    echo SUCCESS: Task created!
    echo Task will run daily at 9:00 AM
    echo.
    echo Verifying task...
    schtasks /query /tn "RR_GU_Daily_Collection" /fo list
) else (
    echo ERROR: Failed to create task
    echo Error level: %errorlevel%
)

echo.
pause