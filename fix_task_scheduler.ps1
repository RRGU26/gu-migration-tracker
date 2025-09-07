# Fix Task Scheduler for RR GU Daily Collection
# This script creates a task that will run missed tasks when computer starts

# Delete existing task if it exists
try {
    Unregister-ScheduledTask -TaskName "RR_GU_Daily_Collection" -Confirm:$false -ErrorAction Stop
    Write-Host "Deleted existing task"
} catch {
    Write-Host "No existing task to delete"
}

# Create action (what to run)
$action = New-ScheduledTaskAction -Execute "C:\Users\rrose\gu-migration-tracker\run_daily_collection.bat"

# Create trigger (when to run - daily at 9 AM)
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

# Create settings (run missed tasks, allow on battery, etc)
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Register the task
Register-ScheduledTask `
    -TaskName "RR_GU_Daily_Collection" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force

Write-Host ""
Write-Host "Task 'RR_GU_Daily_Collection' created successfully!"
Write-Host ""
Write-Host "Settings:"
Write-Host "- Runs daily at 9:00 AM"
Write-Host "- Will run missed tasks when computer starts (StartWhenAvailable)"
Write-Host "- Can run on battery power"
Write-Host "- 10 minute timeout"
Write-Host ""

# Verify the task
$task = Get-ScheduledTask -TaskName "RR_GU_Daily_Collection"
$info = Get-ScheduledTaskInfo -TaskName "RR_GU_Daily_Collection"
Write-Host "Task Status: $($task.State)"
Write-Host "Next Run: $($info.NextRunTime)"