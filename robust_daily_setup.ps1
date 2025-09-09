# Robust Daily Collection Setup - Multiple Safeguards
# This creates several ways to ensure the daily collection runs

Write-Host "Setting up ROBUST daily collection with multiple safeguards..." -ForegroundColor Green
Write-Host ""

# 1. Create the main scheduled task (improved version)
Write-Host "1. Creating main scheduled task..." -ForegroundColor Yellow

# Delete existing task if it exists
try {
    Unregister-ScheduledTask -TaskName "RR_GU_Daily_Collection" -Confirm:$false -ErrorAction Stop
    Write-Host "   Deleted existing task"
} catch {
    Write-Host "   No existing task to delete"
}

# Create action
$action = New-ScheduledTaskAction -Execute "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat" -WorkingDirectory "C:\Users\rrose\gu-migration-tracker"

# Create multiple triggers
$trigger1 = New-ScheduledTaskTrigger -Daily -At 9:00AM
$trigger2 = New-ScheduledTaskTrigger -Daily -At 9:15AM  # Backup 15 minutes later
$trigger3 = New-ScheduledTaskTrigger -AtStartup         # Run at startup if missed

# Create robust settings
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartOnFailure `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

# Create principal with highest privileges
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

# Register the task with all triggers
Register-ScheduledTask `
    -TaskName "RR_GU_Daily_Collection" `
    -Action $action `
    -Trigger $trigger1,$trigger2,$trigger3 `
    -Settings $settings `
    -Principal $principal `
    -Force

Write-Host "   ✓ Task created with 3 triggers: 9:00 AM, 9:15 AM, and at startup" -ForegroundColor Green

# 2. Create desktop shortcut for manual runs
Write-Host ""
Write-Host "2. Creating desktop shortcut..." -ForegroundColor Yellow

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\RUN GU Daily Collection.lnk"

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat"
$Shortcut.WorkingDirectory = "C:\Users\rrose\gu-migration-tracker"
$Shortcut.Description = "Manually run the GU daily data collection"
$Shortcut.Save()

Write-Host "   ✓ Desktop shortcut created: 'RUN GU Daily Collection.lnk'" -ForegroundColor Green

# 3. Create startup folder shortcut
Write-Host ""
Write-Host "3. Creating startup folder entry..." -ForegroundColor Yellow

$startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$startupScript = "$startupPath\GU_Daily_Check.bat"

$startupContent = @"
@echo off
REM Wait 2 minutes after startup, then check if daily collection ran today
timeout /t 120 /nobreak >nul 2>&1
cd /d "C:\Users\rrose\gu-migration-tracker"
python check_and_run_daily.py
"@

$startupContent | Out-File -FilePath $startupScript -Encoding ASCII

Write-Host "   ✓ Startup script created (runs 2 minutes after boot)" -ForegroundColor Green

# 4. Create the check and run script
Write-Host ""
Write-Host "4. Creating smart check script..." -ForegroundColor Yellow

$checkScript = @"
#!/usr/bin/env python3
"""
Smart Daily Collection Checker
Runs at startup and checks if today's data collection has happened
If not, runs it automatically
"""
import sqlite3
import os
import sys
from datetime import date
import subprocess
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('startup_check.log'),
        logging.StreamHandler()
    ]
)

def check_if_ran_today():
    """Check if daily collection ran today"""
    try:
        db_path = 'data/gu_migration.db'
        if not os.path.exists(db_path):
            logging.info("Database doesn't exist, need to run collection")
            return False
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        cursor.execute("SELECT COUNT(*) FROM daily_analytics WHERE analytics_date = ?", (today,))
        count = cursor.fetchone()[0]
        
        conn.close()
        
        if count > 0:
            logging.info(f"✓ Today's data ({today}) already collected")
            return True
        else:
            logging.info(f"✗ Today's data ({today}) NOT found, need to run collection")
            return False
            
    except Exception as e:
        logging.error(f"Error checking database: {e}")
        return False

def run_daily_collection():
    """Run the daily collection"""
    try:
        logging.info("Starting daily collection...")
        result = subprocess.run([
            'python', 'src/services/daily_collection_runner.py'
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            logging.info("✓ Daily collection completed successfully")
            return True
        else:
            logging.error(f"✗ Daily collection failed: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"Error running daily collection: {e}")
        return False

if __name__ == "__main__":
    logging.info("=== GU Daily Collection Startup Check ===")
    
    # Change to the tracker directory
    os.chdir(r'C:\Users\rrose\gu-migration-tracker')
    
    # Check if today's collection has run
    if not check_if_ran_today():
        logging.info("Running daily collection now...")
        success = run_daily_collection()
        if success:
            logging.info("✓ Startup check completed successfully")
        else:
            logging.error("✗ Startup check failed")
    else:
        logging.info("✓ No action needed, today's data already collected")
"@

$checkScript | Out-File -FilePath "C:\Users\rrose\gu-migration-tracker\check_and_run_daily.py" -Encoding UTF8

Write-Host "   ✓ Smart check script created" -ForegroundColor Green

# 5. Create a simple status checker
Write-Host ""
Write-Host "5. Creating status checker..." -ForegroundColor Yellow

$statusScript = @"
@echo off
echo ========================================
echo GU Daily Collection Status Check
echo ========================================
echo.
cd /d "C:\Users\rrose\gu-migration-tracker"
python -c "
import sqlite3
from datetime import date, timedelta

try:
    conn = sqlite3.connect('data/gu_migration.db')
    cursor = conn.cursor()
    
    # Check last few days
    cursor.execute('''
        SELECT analytics_date, origins_floor_eth, undead_floor_eth 
        FROM daily_analytics 
        ORDER BY analytics_date DESC 
        LIMIT 3
    ''')
    
    rows = cursor.fetchall()
    print('Recent data in database:')
    for row in rows:
        print(f'  {row[0]}: Origins={row[1]:.4f} ETH, Undead={row[2]:.4f} ETH')
    
    # Check if today exists
    today = date.today().isoformat()
    cursor.execute('SELECT COUNT(*) FROM daily_analytics WHERE analytics_date = ?', (today,))
    count = cursor.fetchone()[0]
    
    print(f'\nToday ({today}): {\"✓ Data exists\" if count > 0 else \"✗ No data - need to run collection\"}')
    
    conn.close()
except Exception as e:
    print(f'Error: {e}')
"
echo.
pause
"@

$statusScript | Out-File -FilePath "C:\Users\rrose\gu-migration-tracker\check_status.bat" -Encoding ASCII

Write-Host "   ✓ Status checker created: check_status.bat" -ForegroundColor Green

# Show summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ROBUST DAILY COLLECTION SETUP COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Safeguards created:" -ForegroundColor White
Write-Host "1. ✓ Main task: Runs at 9:00 AM daily" -ForegroundColor Green
Write-Host "2. ✓ Backup task: Runs at 9:15 AM daily" -ForegroundColor Green  
Write-Host "3. ✓ Startup task: Runs when computer boots" -ForegroundColor Green
Write-Host "4. ✓ Desktop shortcut: For manual runs" -ForegroundColor Green
Write-Host "5. ✓ Smart checker: Auto-runs if data missing" -ForegroundColor Green
Write-Host "6. ✓ Status checker: Shows current data status" -ForegroundColor Green
Write-Host ""
Write-Host "Files created:" -ForegroundColor White
Write-Host "- Desktop: 'RUN GU Daily Collection.lnk'" -ForegroundColor Yellow
Write-Host "- Startup: Auto-check script runs 2 min after boot" -ForegroundColor Yellow  
Write-Host "- Scripts: check_status.bat, check_and_run_daily.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "The system now has MULTIPLE ways to ensure daily collection runs!" -ForegroundColor Green
Write-Host ""

# Verify the task
$task = Get-ScheduledTask -TaskName "RR_GU_Daily_Collection"
$info = Get-ScheduledTaskInfo -TaskName "RR_GU_Daily_Collection"
Write-Host "Task Status: $($task.State)" -ForegroundColor White
Write-Host "Next Run: $($info.NextRunTime)" -ForegroundColor White