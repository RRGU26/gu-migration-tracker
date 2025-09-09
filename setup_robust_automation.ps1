# Robust Daily Collection Setup - Multiple Safeguards
Write-Host "Setting up ROBUST daily collection with multiple safeguards..." -ForegroundColor Green

# 1. Delete existing task and create improved one
try {
    Unregister-ScheduledTask -TaskName "RR_GU_Daily_Collection" -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Create action
$action = New-ScheduledTaskAction -Execute "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat" -WorkingDirectory "C:\Users\rrose\gu-migration-tracker"

# Create multiple triggers
$trigger1 = New-ScheduledTaskTrigger -Daily -At 9:00AM
$trigger2 = New-ScheduledTaskTrigger -Daily -At 9:15AM
$trigger3 = New-ScheduledTaskTrigger -AtStartup

# Create robust settings  
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Register the task
Register-ScheduledTask -TaskName "RR_GU_Daily_Collection" -Action $action -Trigger $trigger1,$trigger2,$trigger3 -Settings $settings -Force

Write-Host "✓ Task created with 3 triggers: 9:00 AM, 9:15 AM, and at startup" -ForegroundColor Green

# 2. Create desktop shortcut
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\RUN GU Daily Collection.lnk"

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat"
$Shortcut.WorkingDirectory = "C:\Users\rrose\gu-migration-tracker"
$Shortcut.Description = "Manually run the GU daily data collection"
$Shortcut.Save()

Write-Host "✓ Desktop shortcut created" -ForegroundColor Green

# 3. Create startup folder entry
$startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$startupScript = "$startupPath\GU_Daily_Check.bat"

$startupContent = @"
@echo off
timeout /t 120 /nobreak >nul 2>&1
cd /d "C:\Users\rrose\gu-migration-tracker"
python check_and_run_daily.py >startup_check.log 2>&1
"@

$startupContent | Out-File -FilePath $startupScript -Encoding ASCII

Write-Host "✓ Startup script created" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ROBUST SETUP COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Safeguards:" -ForegroundColor White
Write-Host "1. ✓ Daily at 9:00 AM" -ForegroundColor Green
Write-Host "2. ✓ Daily at 9:15 AM (backup)" -ForegroundColor Green
Write-Host "3. ✓ At computer startup" -ForegroundColor Green
Write-Host "4. ✓ Desktop shortcut for manual runs" -ForegroundColor Green
Write-Host "5. ✓ Smart startup checker (runs 2 min after boot)" -ForegroundColor Green
Write-Host ""

# Verify
$task = Get-ScheduledTask -TaskName "RR_GU_Daily_Collection"
$info = Get-ScheduledTaskInfo -TaskName "RR_GU_Daily_Collection"
Write-Host "Task Status: $($task.State)" -ForegroundColor White
Write-Host "Next Run: $($info.NextRunTime)" -ForegroundColor White