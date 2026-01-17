# About Blank Scraper - Environment Setup Script
# Run this once to set up the development environment

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

# Check if Python is available
Write-ColorOutput "Checking Python installation..." "Yellow"
try {
    $pythonVersion = python --version 2>&1
    Write-ColorOutput "✓ Python found: $pythonVersion" "Green"
} catch {
    Write-ColorOutput "✗ Python not found. Please install Python 3.8+ from https://python.org" "Red"
    exit 1
}

# Check if pip is available
Write-ColorOutput "Checking pip installation..." "Yellow"
try {
    $pipVersion = pip --version 2>&1
    Write-ColorOutput "✓ Pip found: $pipVersion" "Green"
} catch {
    Write-ColorOutput "✗ Pip not found. Please install pip." "Red"
    exit 1
}

# Create virtual environment
Write-ColorOutput "Creating virtual environment..." "Yellow"
if (Test-Path "venv") {
    Write-ColorOutput "Virtual environment already exists. Removing..." "Yellow"
    Remove-Item -Recurse -Force "venv"
}

python -m venv venv
Write-ColorOutput "✓ Virtual environment created" "Green"

# Activate virtual environment
Write-ColorOutput "Activating virtual environment..." "Yellow"
& "venv\Scripts\activate.ps1"

# Upgrade pip
Write-ColorOutput "Upgrading pip..." "Yellow"
python -m pip install --upgrade pip

# Install requirements
Write-ColorOutput "Installing dependencies from requirements.txt..." "Yellow"
pip install -r requirements.txt

Write-ColorOutput "✓ All dependencies installed" "Green"

# Deactivate virtual environment
Write-ColorOutput "Deactivating virtual environment..." "Yellow"
deactivate

# Create desktop shortcut for manual execution
Write-ColorOutput "Creating desktop shortcuts..." "Yellow"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$batchShortcut = Join-Path $desktopPath "Run About Blank Scraper.lnk"
$ps1Shortcut = Join-Path $desktopPath "Run About Blank Scraper (PS).lnk"

# Create batch file shortcut
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($batchShortcut)
$Shortcut.TargetPath = Join-Path $PSScriptRoot "run_scraper.bat"
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Run About Blank Fashion Scraper"
$Shortcut.Save()

# Create PowerShell shortcut
$Shortcut = $WshShell.CreateShortcut($ps1Shortcut)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot "run_scraper.ps1")`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Run About Blank Fashion Scraper (PowerShell)"
$Shortcut.Save()

Write-ColorOutput "✓ Desktop shortcuts created" "Green"

Write-ColorOutput "" "Gray"
Write-ColorOutput "=== Setup Complete ===" "Green"
Write-ColorOutput "✓ Virtual environment created" "Green"
Write-ColorOutput "✓ Dependencies installed" "Green"
Write-ColorOutput "✓ Desktop shortcuts created" "Green"
Write-ColorOutput "" "Gray"
Write-ColorOutput "To run the scraper:" "Cyan"
Write-ColorOutput "  1. Double-click 'Run About Blank Scraper.lnk' on your desktop" "White"
Write-ColorOutput "  2. Or run: .\run_scraper.ps1" "White"
Write-ColorOutput "  3. Or run: .\run_scraper.bat" "White"
Write-ColorOutput "" "Gray"
Write-ColorOutput "To run in test mode (5 products only):" "Cyan"
Write-ColorOutput "  .\run_scraper.ps1 -TestMode" "White"
Write-ColorOutput "" "Gray"
Write-ColorOutput "Press any key to continue..." "Yellow"
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")