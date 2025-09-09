@echo off
cd /d "C:\Users\rrose\gu-migration-tracker"
REM Run without logging to file to avoid permission issues with Task Scheduler
python "src\services\daily_collection_runner.py" --no-file-log