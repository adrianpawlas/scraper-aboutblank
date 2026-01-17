# GitHub Actions Setup Guide

## 🚀 Setting Up GitHub Actions for Your Scraper

Follow these steps to enable automated scraping via GitHub Actions.

## Step 1: Enable Actions in Your Repository

1. Go to your repository: https://github.com/adrianpawlas/scraper-aboutblank
2. Click on the **"Actions"** tab
3. If prompted, click **"I understand my workflows, go ahead and enable them"**

## Step 2: Configure Repository Secrets

GitHub Actions needs your Supabase credentials to run the scraper. You must add them as repository secrets:

1. In your repository, click **"Settings"** tab
2. In the left sidebar, click **"Secrets and variables"**
3. Click **"Actions"**
4. Click **"New repository secret"**

### Add These Secrets:

#### Secret 1: SUPABASE_URL
- **Name**: `SUPABASE_URL`
- **Value**: `https://yqawmzggcgpeyaaynrjk.supabase.co`
- Click **"Add secret"**

#### Secret 2: SUPABASE_ANON_KEY
- **Name**: `SUPABASE_ANON_KEY`
- **Value**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4`
- Click **"Add secret"**

## Step 3: Verify Workflows Are Available

1. Go back to the **"Actions"** tab
2. You should now see two workflows:
   - **"About Blank Scraper"** - Main automated scraper
   - **"Test Scraper"** - Test workflow for validation

## Step 4: Test the Setup

### Run Test Workflow First
1. Click on **"Test Scraper"** workflow
2. Click **"Run workflow"** (green button)
3. Click **"Run workflow"** again in the popup
4. Watch the workflow run (should take ~2-3 minutes)
5. Check the results - it should complete successfully

### Then Test Main Scraper
1. Click on **"About Blank Scraper"** workflow
2. Click **"Run workflow"**
3. Select **"test"** mode (not "full" for first test)
4. Click **"Run workflow"**
5. Monitor the execution

## Step 5: Set Up Automatic Scheduling

The main scraper is configured to run automatically every day at midnight UTC. To customize:

1. In your repository, go to **`.github/workflows/scraper.yml`**
2. Edit the cron schedule:
   ```yaml
   schedule:
     - cron: '0 0 * * *'  # Change this
   ```

### Common Schedules:
- `'0 0 * * *'` - Daily at midnight UTC
- `'0 6 * * *'` - Daily at 6 AM UTC
- `'0 */12 * * *'` - Every 12 hours
- `'0 0 * * 1'` - Weekly on Mondays

## 📊 Monitoring Your Workflows

### View Workflow Runs
1. Go to **"Actions"** tab
2. Click on any workflow run
3. View logs, timing, and results
4. Download artifacts (logs) if needed

### Workflow Status
- 🟢 **Green checkmark**: Success
- 🔴 **Red X**: Failed
- 🟡 **Yellow dot**: Running
- ⚪ **Gray circle**: Queued

### Troubleshooting Failed Runs
1. Click on the failed run
2. Check the logs for error messages
3. Common issues:
   - Missing secrets (check Step 2)
   - Network timeouts (temporary issue)
   - Supabase connection problems
   - Rate limiting from the website

## 🎯 Available Workflows

### 1. About Blank Scraper (Main)
- **Purpose**: Full automated scraping
- **Schedule**: Daily at midnight UTC
- **Manual trigger**: Yes, with mode selection
- **Duration**: ~45-60 minutes for full scrape
- **Products**: All available products (~400+)

### 2. Test Scraper
- **Purpose**: Quick validation and testing
- **Schedule**: On every push/PR
- **Manual trigger**: Yes
- **Duration**: ~2-3 minutes
- **Products**: 5 test products only

## 🔧 Advanced Configuration

### Change Python Version
Edit `.github/workflows/scraper.yml`:
```yaml
- name: Set up Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'  # Change version here
```

### Modify Scraper Behavior
The workflows run your existing `main.py` and `main_test.py` scripts, so any changes you make to those files will apply to GitHub Actions automatically.

### Add Notifications
You can add Slack, Discord, or email notifications by adding steps to the workflow files.

## 🔒 Security Notes

- Secrets are encrypted and only accessible to this repository
- GitHub Actions runs on Microsoft/Azure infrastructure
- No sensitive data is logged or exposed
- Virtual environments are destroyed after each run

## 📞 Support

If workflows don't appear or fail:

1. **Check repository settings**: Ensure Actions are enabled
2. **Verify secrets**: Make sure both secrets are added correctly
3. **Check workflow syntax**: GitHub will show syntax errors
4. **Review logs**: Detailed error messages in workflow logs
5. **Test locally**: Ensure scraper works on your machine first

## 🎉 You're Done!

Once set up, your scraper will:
- ✅ Run automatically every day at midnight UTC
- ✅ Allow manual execution anytime
- ✅ Keep your Supabase database updated
- ✅ Generate fresh embeddings for new products
- ✅ Provide complete logging and monitoring

**Repository**: https://github.com/adrianpawlas/scraper-aboutblank

**Actions URL**: https://github.com/adrianpawlas/scraper-aboutblank/actions