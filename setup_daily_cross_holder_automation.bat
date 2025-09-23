@echo off
REM Setup daily automation for cross-holder analysis

echo Setting up daily cross-holder analysis automation...

REM Create task to run cross-holder analysis daily at 9:15 AM EST
schtasks /create /tn "GU Cross-Holder Analysis" /tr "\"C:\Users\rrose\gu-migration-tracker\run_daily_cross_holder.bat\"" /sc daily /st 09:15 /f

if %errorlevel% equ 0 (
    echo ✓ Daily cross-holder analysis scheduled for 9:15 AM EST
) else (
    echo ✗ Failed to schedule cross-holder analysis
)

echo.
echo Daily automation setup complete:
echo - Seller analysis: 9:00 AM EST
echo - Cross-holder analysis: 9:15 AM EST
echo.
pause