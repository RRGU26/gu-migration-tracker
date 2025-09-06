@echo off
echo Setting up Daily Automation for RR GU Analytic Tracker
echo ========================================================

REM Create a scheduled task to run daily at 9:00 AM
schtasks /create /tn "RR_GU_Daily_Collection" /tr "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat" /sc daily /st 09:00 /f

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