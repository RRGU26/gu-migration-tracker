@echo off
cd /d "C:\Users\rrose\gu-migration-tracker"
python "src\services\daily_collection_runner.py" > daily_collection.log 2>&1