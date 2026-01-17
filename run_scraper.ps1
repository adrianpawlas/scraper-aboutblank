# About Blank Scraper - PowerShell Automation Script
# This script can be used for both manual execution and scheduled tasks

param(
    [switch]$TestMode,
    [switch]$Verbose,
    [string]$LogFile = "scraper_run_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
)

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

# Function to check Python availability
function Test-Python {
    try {
        $pythonVersion = python --version 2>&1
        Write-ColorOutput "✓ Python found: $pythonVersion" "Green"
        return $true
    }
    catch {
        Write-ColorOutput "✗ Python not found in PATH" "Red"
        return $false
    }
}

# Function to activate virtual environment
function Activate-VirtualEnv {
    $venvPath = Join-Path $PSScriptRoot "venv\Scripts\activate.ps1"
    if (Test-Path $venvPath) {
        Write-ColorOutput "Activating virtual environment..." "Yellow"
        & $venvPath
        return $true
    } else {
        Write-ColorOutput "No virtual environment found, using system Python..." "Yellow"
        return $false
    }
}

# Function to run the scraper
function Run-Scraper {
    param([bool]$TestMode)

    $script = if ($TestMode) { "main_test.py" } else { "main.py" }
    $scriptPath = Join-Path $PSScriptRoot $script

    if (-not (Test-Path $scriptPath)) {
        Write-ColorOutput "✗ Scraper script not found: $scriptPath" "Red"
        return $false
    }

    Write-ColorOutput "Running scraper: $script" "Cyan"

    try {
        if ($Verbose) {
            & python $scriptPath
        } else {
            & python $scriptPath 2>&1 | Tee-Object -FilePath $LogFile
        }

        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ Scraper completed successfully" "Green"
            return $true
        } else {
            Write-ColorOutput "✗ Scraper failed with exit code: $LASTEXITCODE" "Red"
            return $false
        }
    }
    catch {
        Write-ColorOutput "✗ Error running scraper: $($_.Exception.Message)" "Red"
        return $false
    }
}

# Main execution
Write-ColorOutput "=== About Blank Scraper Automation ===" "Cyan"
Write-ColorOutput "Started at: $(Get-Date)" "Gray"
Write-ColorOutput "" "Gray"

# Change to script directory
Set-Location $PSScriptRoot
Write-ColorOutput "Working directory: $PSScriptRoot" "Gray"

# Check Python
if (-not (Test-Python)) {
    exit 1
}

# Activate virtual environment
$venvActivated = Activate-VirtualEnv

# Run the scraper
$success = Run-Scraper -TestMode $TestMode

# Deactivate virtual environment if it was activated
if ($venvActivated) {
    Write-ColorOutput "Deactivating virtual environment..." "Yellow"
    deactivate
}

# Final status
Write-ColorOutput "" "Gray"
Write-ColorOutput "Completed at: $(Get-Date)" "Gray"

if ($success) {
    Write-ColorOutput "✓ Scraper execution completed successfully" "Green"
    if (-not $Verbose) {
        Write-ColorOutput "Log saved to: $LogFile" "Gray"
    }
    exit 0
} else {
    Write-ColorOutput "✗ Scraper execution failed" "Red"
    if (-not $Verbose) {
        Write-ColorOutput "Check log file: $LogFile" "Gray"
    }
    exit 1
}