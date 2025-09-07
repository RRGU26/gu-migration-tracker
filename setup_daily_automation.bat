@echo off
echo Setting up Daily Automation for RR GU Analytic Tracker
echo ========================================================

REM Delete existing task if it exists
schtasks /delete /tn "RR_GU_Daily_Collection" /f 2>nul

REM Create a scheduled task to run daily at 9:00 AM with better settings
REM /RL HIGHEST - Run with highest privileges
REM /RU %USERNAME% - Run as current user
schtasks /create /tn "RR_GU_Daily_Collection" /tr "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat" /sc daily /st 09:00 /RL HIGHEST /RU %USERNAME% /f

REM Configure task to run missed tasks when computer starts
powershell -Command "Set-ScheduledTask -TaskName 'RR_GU_Daily_Collection' -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)"

echo.
echo Daily automation task created!
echo Task Name: RR_GU_Daily_Collection
echo Schedule: Daily at 9:00 AM
echo.
echo To view or modify: Open Task Scheduler and look for "RR_GU_Daily_Collection"
echo To run manually now: schtasks /run /tn "RR_GU_Daily_Collection"
echo To delete: schtasks /delete /tn "RR_GU_Daily_Collection" /f
echo.
pause