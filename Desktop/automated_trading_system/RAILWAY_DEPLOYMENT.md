# Railway Deployment - Quick Start

Trade Pulse on Railway in 5 minutes! 🚀

## Prerequisites

- GitHub account (your code is already here ✓)
- Railway account (free): https://railway.app

## Step 1: Connect to Railway (2 min)

1. Go to https://railway.app and sign up
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Search for and select: `akshrajput542/Trade-Pulse`
4. Authorize Railway to access your GitHub
5. Click **Deploy**

Railway automatically detects your `Procfile` and starts deploying!

## Step 2: Add PostgreSQL Database (1 min)

1. In Railway dashboard, click **"+ Add"**
2. Click **"PostgreSQL"**
3. Railway auto-creates the database and sets `DATABASE_URL` env var ✓

Your app now has production-grade PostgreSQL!

## Step 3: Add Your Secrets (1 min)

1. Click **"Variables"** in your Railway project
2. Add your trading API credentials:
   ```
   ANGEL_API_KEY = your_key_here
   ZERODHA_API_KEY = your_key_here
   MARKET_PRESET = both
   ENVIRONMENT = production
   STREAMLIT_SERVER_HEADLESS = true
   ```
3. **Never commit these to GitHub** - Railway handles them securely

## Step 4: Deploy! (1 min)

1. Push any changes to GitHub:
   ```bash
   git add .
   git commit -m "Add deployment config"
   git push origin main
   ```

2. Railway auto-deploys from GitHub!

3. Your app is live at: `https://your-project-name-prod.up.railway.app`

## Access Your App

- **Dashboard**: https://your-project-name-prod.up.railway.app
- **Logs**: Railway Dashboard → Logs tab
- **Metrics**: Railway Dashboard → Metrics tab

## Troubleshooting

### App not starting?
```bash
# Check logs
Railway Dashboard → Logs tab
```

### Database connection failed?
```bash
# Verify DATABASE_URL exists
Railway → Variables
# Should show: postgresql://...
```

### Broker credentials not working?
```
Check if ANGEL_API_KEY and ZERODHA_API_KEY are set in Variables
Restart deployment if you added new vars
```

## Monitoring

Railway provides:
- ✅ Real-time logs
- ✅ Memory/CPU usage
- ✅ Automatic restarts
- ✅ PostgreSQL backups
- ✅ Custom domain support

## Scaling

Need more power? In Railway:
1. Click your web service
2. **Plan** → Choose paid tier
3. **Replicas** → Add more instances

## Cost

- **Free tier**: Good for testing
- **Starter**: ~$5/month (web + database)
- **Production**: $20+/month with scaling

---

**Pro Tips:**
- Use Railway's "Canary Deployments" to test updates safely
- Enable "Auto Deploy" to deploy on every push
- Set up email alerts for failed deployments

Need help? Railway docs: https://docs.railway.app
