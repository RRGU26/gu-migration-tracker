@echo off
echo Setting up Automated Daily Process for RR GU Analytic Tracker
echo ===========================================================

REM Delete old task if exists
schtasks /delete /tn "RR_GU_Daily_Collection" /f 2>nul

REM Create new automated task
schtasks /create /tn "RR_GU_Automated_Daily_Process" ^
  /tr "python C:\Users\rrose\gu-migration-tracker\src\services\automated_daily_process.py" ^
  /sc daily /st 09:00 /f

echo.
echo ✅ Automation configured successfully!
echo.
echo The system will automatically run every day at 9:00 AM and:
echo   1. Get latest Ethereum price
echo   2. Get GU Origins floor price
echo   3. Get Genuine Undead floor price  
echo   4. Get Genuine Undead NFT count
echo   5. Log all data
echo   6. Calculate market caps
echo   7. Calculate migration changes
echo   8. Calculate floor price changes
echo   9. Update dashboard and reports
echo.
echo To run manually now: python src\services\automated_daily_process.py
pause