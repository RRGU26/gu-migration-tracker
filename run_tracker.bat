@echo off
REM GU Migration Tracker - Windows Batch Script
REM This script provides easy commands to run the migration tracker

echo GU Migration Tracker - Control Script
echo =====================================

if "%1"=="" (
    echo Usage: run_tracker.bat [command]
    echo.
    echo Commands:
    echo   setup      - Initialize database and directories
    echo   daily      - Generate daily report
    echo   test       - Run with mock data for testing
    echo   health     - Check system health
    echo   schedule   - Start automated daily scheduler
    echo   help       - Show detailed help
    echo.
    goto :end
)

if "%1"=="setup" (
    echo Setting up GU Migration Tracker...
    python main.py --mode setup
    goto :end
)

if "%1"=="daily" (
    echo Generating daily migration report...
    python main.py --mode daily
    goto :end
)

if "%1"=="test" (
    echo Running in test mode with mock data...
    python main.py --mode test
    goto :end
)

if "%1"=="health" (
    echo Checking system health...
    python main.py --mode health
    goto :end
)

if "%1"=="schedule" (
    echo Starting automated scheduler...
    echo Press Ctrl+C to stop
    python main.py --mode scheduler
    goto :end
)

if "%1"=="help" (
    echo GU Migration Tracker - Detailed Help
    echo ====================================
    echo.
    echo This tool tracks NFT migrations from GU Origins to Genuine Undead
    echo and generates comprehensive daily reports with market analytics.
    echo.
    echo Quick Start:
    echo 1. run_tracker.bat setup    - First time setup
    echo 2. Edit .env file with your OpenSea API key
    echo 3. run_tracker.bat test     - Test with mock data
    echo 4. run_tracker.bat daily    - Generate real report
    echo 5. run_tracker.bat schedule - Start automated mode
    echo.
    echo Report Files:
    echo   reports/daily/daily_report_YYYY-MM-DD.md  - Markdown report
    echo   reports/daily/daily_report_YYYY-MM-DD.pdf - PDF report  
    echo   reports/charts/                          - Generated charts
    echo.
    echo For more details, see README.md
    goto :end
)

echo Unknown command: %1
echo Run 'run_tracker.bat' with no arguments to see available commands.

:end
pause