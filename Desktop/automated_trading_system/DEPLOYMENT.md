# Deployment Guide - Trade Pulse

This guide covers deploying your automated trading system with dashboard + backend services.

## Option 1: Railway (Recommended) ⭐

Railway is perfect for trading systems - it supports persistent background services and databases.

### Step 1: Prepare for Deployment

1. **Create Procfile** at project root:
```
web: streamlit run dashboard/app.py --server.port=$PORT --logger.level=error
worker: python auto_trader_daemon.py
```

2. **Create runtime.txt** (optional but recommended):
```
python-3.11.0
```

3. **Update requirements.txt** - ensure all dependencies are listed (already done ✓)

4. **Environment Variables** - Create `.env.production` with:
```
DATABASE_URL=postgresql://user:password@host/dbname
FLASK_ENV=production
PYTHONUNBUFFERED=1
```

### Step 2: Deploy to Railway

1. **Sign up at** https://railway.app
2. **Connect GitHub**: Click "New Project" → Select your repo
3. **Add PostgreSQL Plugin**:
   - Click "+ Add"
   - Select "PostgreSQL"
   - Railway auto-generates DATABASE_URL
4. **Configure Environment**:
   - Railway Dashboard → Variables
   - Add any trading API keys (Angel, Zerodha, etc.) from your `.env`
5. **Deploy**:
   - Push to GitHub → Railway auto-deploys
   - Your app runs at: `https://yourdomain.railway.app`

### Step 3: Connect PostgreSQL

Update `config.py`:
```python
import os
from urllib.parse import urlparse

if os.getenv('DATABASE_URL'):
    # Production PostgreSQL
    db_url = os.getenv('DATABASE_URL')
    # Railway format: postgresql://user:pass@host/db
    engine_url = db_url.replace('postgres://', 'postgresql://')
else:
    # Local SQLite
    engine_url = 'sqlite:///./trading.db'

DATABASE_URL = engine_url
```

**Cost**: ~$5-10/month for web + PostgreSQL

---

## Option 2: Render

Similar to Railway, with generous free tier.

### Step 1: Create `render.yaml` at project root:

```yaml
services:
  - type: web
    name: trade-pulse-dashboard
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run dashboard/app.py --server.port=$PORT
    envVars:
      - key: PYTHONUNBUFFERED
        value: true
  
  - type: background_worker
    name: trade-pulse-worker
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python auto_trader_daemon.py
    envVars:
      - key: PYTHONUNBUFFERED
        value: true

databases:
  - name: tradepulse-db
    databaseName: tradepulse
    region: oregon
```

### Step 2: Deploy
1. Go to https://render.com
2. "New+" → "Web Service"
3. Connect GitHub repo
4. Select `render.yaml`
5. Deploy

**Cost**: Free tier available, paid ~$7/month

---

## Option 3: Heroku (Legacy but works)

### Step 1: Install Heroku CLI
```bash
# Windows
choco install heroku-cli

# macOS
brew install heroku/brew/heroku

# Linux
curl https://cli-assets.heroku.com/install.sh | sh
```

### Step 2: Create Procfile
```
web: streamlit run dashboard/app.py --server.port=$PORT --logger.level=error
worker: python auto_trader_daemon.py
```

### Step 3: Deploy
```bash
heroku login
heroku create your-app-name
git push heroku main
heroku addons:create heroku-postgresql:hobby-dev
heroku config:set FLASK_ENV=production
```

**Cost**: Free tier deprecated; ~$7/month minimum

---

## Before Deployment - Checklist

- [ ] All sensitive data in `.env` (not in code)
- [ ] `requirements.txt` updated with all dependencies
- [ ] Database migrations configured
- [ ] Trading API keys secured (Angel, Zerodha, etc.)
- [ ] `.gitignore` includes `.env`, `*.db`, `__pycache__/`
- [ ] Code tested locally: `python main.py run`
- [ ] Dashboard tested: `streamlit run dashboard/app.py`

---

## After Deployment

### View Logs
**Railway:**
```bash
railway logs
```

**Render:**
```bash
# Via dashboard: Logs → Merged Output
```

**Heroku:**
```bash
heroku logs --tail
```

### Database Backups
- **Railway**: Auto-backups included
- **Render**: Configure backups in dashboard
- **Heroku**: Manual backups recommended

### Scaling Background Worker
If trading system gets heavy:
- **Railway**: Increase dyno size
- **Render**: Upgrade instance type
- **Heroku**: Scale worker processes

---

## Troubleshooting

### App crashes on startup
```bash
# Check logs
heroku logs --tail  # or railway logs

# Common issue: DATABASE_URL not set
# Add to environment variables
```

### Database connection error
```
Verify DATABASE_URL in platform dashboard
Test locally: python -c "from config import DATABASE_URL; print(DATABASE_URL)"
```

### Background worker not running trades
```
Check logs for errors
Verify trading API credentials in environment
Test locally: python auto_trader_daemon.py
```

---

## Recommendation

**Use Railway or Render** - They're built for apps like yours:
- ✅ Persistent background workers
- ✅ Integrated PostgreSQL
- ✅ Auto-deploys from GitHub
- ✅ Affordable ($5-10/month)
- ✅ Easy scaling

**Avoid Streamlit Cloud** - It's great for dashboards but stops background jobs after 30 mins.
