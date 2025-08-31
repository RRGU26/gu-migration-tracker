# 🚀 Deployment Instructions

## GitHub Setup

### 1. Create GitHub Repository

Go to https://github.com/RRGU26 and create a new repository:
- Repository name: `gu-migration-tracker`
- Description: `Real-time NFT migration analytics dashboard`
- Set to Public
- Don't initialize with README (we have our own)

### 2. Initialize Git and Push

```bash
cd C:\Users\rrose\gu-migration-tracker

# Initialize git repository
git init

# Add all files
git add .

# First commit
git commit -m "Initial commit: GU Migration Tracker with live dashboard

- Real-time OpenSea API integration
- Interactive web dashboard with 5 chart types
- Migration detection algorithm
- SQLite database for historical data
- Flask web server with RESTful API
- Mobile-responsive design
- Automated report generation
- Market cap vs industry comparison
- Supply growth tracking"

# Add GitHub remote
git remote add origin https://github.com/RRGU26/gu-migration-tracker.git

# Push to GitHub
git push -u origin main
```

## 🌐 Deploy to Heroku (Free Hosting)

### 1. Create Heroku Account
- Sign up at https://heroku.com
- Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli

### 2. Create Heroku App
```bash
# Login to Heroku
heroku login

# Create new Heroku app
heroku create gu-migration-tracker

# Or with custom name:
heroku create your-custom-name-here
```

### 3. Set Environment Variables
```bash
# Set your OpenSea API key
heroku config:set OPENSEA_API_KEY=518c0d7ea6ad4116823f41c5245b1098

# Optional: Set other variables
heroku config:set ETHERSCAN_API_KEY=your_etherscan_key_here
```

### 4. Deploy to Heroku
```bash
# Push to Heroku
git push heroku main

# Open your live dashboard
heroku open
```

Your dashboard will be live at: `https://gu-migration-tracker.herokuapp.com`

## 🔄 Alternative: Deploy to Railway (Recommended)

Railway offers better free tier limits:

### 1. Sign up at https://railway.app with GitHub
### 2. Connect your GitHub repository
### 3. Add environment variables in Railway dashboard:
   - `OPENSEA_API_KEY` = `518c0d7ea6ad4116823f41c5245b1098`
### 4. Deploy automatically!

## 🌊 Alternative: Deploy to Vercel

### 1. Sign up at https://vercel.com with GitHub
### 2. Import your repository
### 3. Add environment variables
### 4. Deploy with one click

## 📱 Alternative: Deploy to Render

### 1. Sign up at https://render.com
### 2. Connect GitHub repository
### 3. Configure as Web Service:
   - Build Command: `pip install -r requirements.txt && pip install -r dashboard/requirements.txt`
   - Start Command: `cd dashboard && python app.py`
### 4. Add environment variables
### 5. Deploy!

## ⚙️ Environment Variables Needed

```bash
# Required for live data
OPENSEA_API_KEY=your_opensea_api_key_here

# Optional
ETHERSCAN_API_KEY=your_etherscan_key
DATABASE_URL=sqlite:///data/gu_migration.db
PORT=5000
```

## 🔄 Automatic Updates

Once deployed, you can update your dashboard:

```bash
# Make changes to code
git add .
git commit -m "Update: Added new feature"
git push origin main

# For Heroku:
git push heroku main

# For Railway/Vercel: Automatic deployment on git push
```

## 📊 Dashboard URLs

After deployment, your dashboard will have these endpoints:

- **Main Dashboard**: `https://your-app.herokuapp.com/`
- **API Current Data**: `https://your-app.herokuapp.com/api/current`
- **API Charts**: `https://your-app.herokuapp.com/api/charts`
- **Health Check**: `https://your-app.herokuapp.com/health`

## 🎯 Next Steps After Deployment

1. **Share your dashboard** with the GU community
2. **Monitor usage** and API limits
3. **Set up alerts** for when migrations spike
4. **Add custom domain** (optional)
5. **Enable GitHub Actions** for CI/CD (optional)

## 🚨 Troubleshooting

**Common Issues:**

1. **App won't start**: Check logs with `heroku logs --tail`
2. **API errors**: Verify OpenSea API key is set correctly
3. **Charts not loading**: Check browser console for JavaScript errors
4. **Database issues**: SQLite works on Heroku but resets on restart

**Solutions:**
- Use PostgreSQL for persistent data on production
- Add error handling for API rate limits
- Cache data to reduce API calls

## 🎉 Success!

Your GU Migration Tracker dashboard is now live and accessible worldwide! 

The dashboard will:
- ✅ Update every 5 minutes with fresh data
- ✅ Track migrations automatically
- ✅ Show beautiful charts and analytics
- ✅ Work on all devices (mobile/desktop)
- ✅ Handle API rate limits gracefully