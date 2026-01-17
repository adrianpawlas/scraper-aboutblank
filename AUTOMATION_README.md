# About Blank Scraper - Automation Setup

This guide explains how to set up automated daily scraping while maintaining the ability to run the scraper manually.

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)
Run the PowerShell setup script as Administrator:
```powershell
.\setup_environment.ps1
.\setup_scheduler.ps1
```

### Option 2: Manual Setup
Follow the step-by-step instructions below.

## 📋 Prerequisites

- Windows 10/11
- Python 3.8+ installed
- Administrator privileges for scheduler setup
- Git (for cloning/updating)

## 🛠️ Setup Instructions

### Step 1: Environment Setup

Run the environment setup script:
```powershell
.\setup_environment.ps1
```

This will:
- ✅ Create a Python virtual environment
- ✅ Install all dependencies
- ✅ Create desktop shortcuts for manual execution

**Or manually:**
```powershell
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Deactivate
deactivate
```

### Step 2: Test Manual Execution

Test that everything works:
```powershell
# Test mode (5 products)
.\run_scraper.ps1 -TestMode

# Full mode
.\run_scraper.ps1
```

### Step 3: Set Up Daily Automation

Run the scheduler setup script **as Administrator**:
```powershell
.\setup_scheduler.ps1
```

This creates a Windows Task Scheduler task that runs daily at midnight.

**Or manually create the task:**

1. Open **Task Scheduler** (`taskschd.msc`)
2. Click **Create Task...**
3. Configure:
   - **Name**: `About Blank Fashion Scraper`
   - **Description**: `Automatically scrape About Blank fashion products daily`
   - **Security options**: Run whether user is logged on or not
   - **Run with highest privileges**: ✅
4. **Triggers** tab:
   - **New...** → Daily → At 12:00:00 AM every 1 days
5. **Actions** tab:
   - **New...** → Start a program
   - **Program/script**: `powershell.exe`
   - **Add arguments**: `-ExecutionPolicy Bypass -File "C:\path\to\scraper-aboutblank\run_scraper.ps1"`
6. **Conditions** tab:
   - ✅ Start only if the following network connection is available
   - ✅ Start the task only if the computer is on AC power
7. **Settings** tab:
   - ✅ Allow task to be run on demand
   - ✅ Run task as soon as possible after a scheduled start is missed
   - ✅ If the running task does not end when requested, force it to stop

## 🎯 How to Use

### Manual Execution

**Option 1: Desktop Shortcuts**
- Double-click `Run About Blank Scraper.lnk` on your desktop

**Option 2: Command Line**
```powershell
# Full scrape
.\run_scraper.ps1

# Test mode (5 products)
.\run_scraper.ps1 -TestMode

# Verbose output
.\run_scraper.ps1 -Verbose

# Custom log file
.\run_scraper.ps1 -LogFile "my_custom_log.txt"
```

**Option 3: Batch File**
```cmd
run_scraper.bat
```

### Automated Execution

The scraper will automatically run every day at midnight. Logs are saved with timestamps:
- `scheduled_run_2024-01-17_00-00-00.log`
- Check Task Scheduler for task status
- View logs in the scraper directory

## 📊 Monitoring & Logs

### Log Files
- `scraper.log` - Main application logs
- `scheduled_run_YYYY-MM-DD_HH-mm-ss.log` - Scheduled run logs
- All logs are automatically rotated

### Task Scheduler Monitoring
1. Open **Task Scheduler** (`taskschd.msc`)
2. Navigate to **Task Scheduler Library**
3. Find **"About Blank Fashion Scraper"**
4. Check **History** tab for execution details
5. **Last Run Result** shows success/failure

### Manual Task Execution
```powershell
# Run task immediately
schtasks /run /tn "About Blank Fashion Scraper"

# Check task status
schtasks /query /tn "About Blank Fashion Scraper"
```

## 🔧 Troubleshooting

### Common Issues

**1. "Python not found"**
```powershell
# Add Python to PATH or use full path
python --version
```

**2. "Virtual environment not activated"**
```powershell
# Activate manually
venv\Scripts\activate
```

**3. Task Scheduler fails**
- Ensure script paths are correct
- Check execution policy: `Get-ExecutionPolicy`
- Try: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`

**4. Network errors**
- Check internet connection
- Verify About Blank website is accessible
- The scraper has built-in retry logic

**5. Permission errors**
- Run PowerShell/Command Prompt as Administrator
- Check file permissions on the scraper directory

### Debug Commands

```powershell
# Test Python environment
python -c "import sys; print(sys.version)"

# Test imports
python -c "from scraper import AboutBlankScraper; print('OK')"

# Test database connection
python check_db.py

# Test full pipeline
python main_test.py
```

## ⚙️ Configuration

### Modify Schedule
1. Open Task Scheduler
2. Find the task
3. Right-click → Properties
4. **Triggers** tab → Edit the daily trigger

### Change Execution Time
Edit the trigger to run at different times:
- Daily at 2 AM: Change to `02:00`
- Weekly on Mondays: Change trigger type
- Multiple times per day: Add multiple triggers

### Disable/Enable Automation
```powershell
# Disable task
schtasks /change /tn "About Blank Fashion Scraper" /disable

# Enable task
schtasks /change /tn "About Blank Fashion Scraper" /enable

# Or use Task Scheduler GUI
```

## 📁 File Structure

```
scraper-aboutblank/
├── 📄 run_scraper.bat          # Batch file for manual execution
├── 📄 run_scraper.ps1          # PowerShell script with advanced options
├── 📄 setup_environment.ps1    # Environment setup script
├── 📄 setup_scheduler.ps1      # Scheduler setup script
├── 📄 AUTOMATION_README.md     # This file
├── 📄 README.md               # Main documentation
└── [other scraper files...]
```

## 🔄 Updates

To update the scraper:
```powershell
# Pull latest changes
git pull origin master

# Update dependencies
venv\Scripts\activate
pip install -r requirements.txt
deactivate
```

## 🆘 Support

If you encounter issues:

1. Check the log files in the scraper directory
2. Run in test mode: `.\run_scraper.ps1 -TestMode -Verbose`
3. Check Task Scheduler history
4. Verify all prerequisites are installed
5. Ensure network connectivity to about---blank.com

## 📈 Performance Notes

- **Full scrape**: ~45-60 minutes (422 products)
- **Test scrape**: ~30 seconds (5 products)
- **Memory usage**: ~500MB during execution
- **CPU usage**: High during embedding generation
- **Network**: ~10-15 requests per minute (rate limited)

The scraper is designed to be resource-efficient and respectful to the target website.