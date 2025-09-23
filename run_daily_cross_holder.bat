@echo off
REM Daily cross-holder analysis runner

echo ================================================
echo GU MIGRATION TRACKER - DAILY CROSS-HOLDER ANALYSIS
echo %date% %time%
echo ================================================

cd /d "C:\Users\rrose\gu-migration-tracker"

REM Run the cross-holder analysis and email
echo Running cross-holder analysis...
python "send_cross_holder_email.py"

if %errorlevel% equ 0 (
    echo [SUCCESS] Cross-holder analysis completed and sent
) else (
    echo [ERROR] Cross-holder analysis failed
)

echo.
echo Cross-holder analysis complete: %date% %time%
echo ================================================