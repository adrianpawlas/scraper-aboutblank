# About Blank Scraper - Windows Task Scheduler Setup
# This script creates a scheduled task to run the scraper daily at midnight

# Requires administrator privileges
#Requires -RunAsAdministrator

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to write colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Main execution
Write-ColorOutput "=== About Blank Scraper - Scheduler Setup ===" "Cyan"

# Check administrator privileges
if (-not (Test-Administrator)) {
    Write-ColorOutput "✗ This script requires administrator privileges." "Red"
    Write-ColorOutput "Please run PowerShell as Administrator and try again." "Yellow"
    exit 1
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$scraperScript = Join-Path $scriptDir "run_scraper.ps1"

# Check if scraper script exists
if (-not (Test-Path $scraperScript)) {
    Write-ColorOutput "✗ Scraper script not found: $scraperScript" "Red"
    exit 1
}

# Task parameters
$taskName = "About Blank Fashion Scraper"
$taskDescription = "Automatically scrape About Blank fashion products daily at midnight"
$taskAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scraperScript`" -LogFile `"$scriptDir\scheduled_run_`$((Get-Date).ToString('yyyy-MM-dd_HH-mm-ss')).log`""
$taskTrigger = New-ScheduledTaskTrigger -Daily -At "00:00"
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken
$taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

Write-ColorOutput "Creating scheduled task..." "Yellow"
Write-ColorOutput "Task Name: $taskName" "Gray"
Write-ColorOutput "Schedule: Daily at 12:00 AM (midnight)" "Gray"
Write-ColorOutput "Action: $scraperScript" "Gray"

try {
    # Remove existing task if it exists
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-ColorOutput "Removing existing task..." "Yellow"
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    # Create new task
    $task = New-ScheduledTask -Action $taskAction -Principal $taskPrincipal -Trigger $taskTrigger -Settings $taskSettings -Description $taskDescription
    Register-ScheduledTask -TaskName $taskName -InputObject $task

    Write-ColorOutput "✓ Scheduled task created successfully!" "Green"

    # Verify task was created
    $createdTask = Get-ScheduledTask -TaskName $taskName
    if ($createdTask) {
        Write-ColorOutput "" "Gray"
        Write-ColorOutput "Task Details:" "Cyan"
        Write-ColorOutput "  Name: $($createdTask.TaskName)" "White"
        Write-ColorOutput "  Status: $($createdTask.State)" "White"
        Write-ColorOutput "  Next Run: $($createdTask.NextRunTime)" "White"
        Write-ColorOutput "  Author: $($createdTask.Author)" "White"
    }

} catch {
    Write-ColorOutput "✗ Failed to create scheduled task: $($_.Exception.Message)" "Red"
    exit 1
}

Write-ColorOutput "" "Gray"
Write-ColorOutput "=== Setup Complete ===" "Green"
Write-ColorOutput "✓ Daily scraper scheduled for midnight" "Green"
Write-ColorOutput "" "Gray"
Write-ColorOutput "To manage the task:" "Cyan"
Write-ColorOutput "  1. Open Task Scheduler (taskschd.msc)" "White"
Write-ColorOutput "  2. Go to Task Scheduler Library" "White"
Write-ColorOutput "  3. Find '$taskName'" "White"
Write-ColorOutput "  4. Right-click to modify, run, or disable" "White"
Write-ColorOutput "" "Gray"
Write-ColorOutput "To run manually:" "Cyan"
Write-ColorOutput "  .\run_scraper.ps1" "White"
Write-ColorOutput "  # or use the desktop shortcuts" "Gray"
Write-ColorOutput "" "Gray"
Write-ColorOutput "Press any key to continue..." "Yellow"
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")