# 🧟‍♂️ GU Migration Tracker

**Real-time NFT migration analytics dashboard tracking the movement from GU Origins to Genuine Undead collections.**

[![Live Dashboard](https://img.shields.io/badge/Live-Dashboard-blue?style=for-the-badge)](https://gu-migration-tracker.herokuapp.com)
[![OpenSea](https://img.shields.io/badge/OpenSea-API-orange?style=for-the-badge)](https://opensea.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

## 🎯 What This Tracks

**Collections Monitored:**
- **GU Origins** (Source): `0x209e639a0EC166Ac7a1A4bA41968fa967dB30221`
- **Genuine Undead** (Destination): `0x39509d8e1dd96cc8bad301ea65c75c7deb52374c`

**Key Metrics:**
- 📈 Real-time floor prices and market caps
- 📊 24h/7d trading volumes
- 🔄 Migration detection and velocity
- 👥 Holder distribution analysis
- 📉 Price trends and market comparisons
- 💎 Diamond hands vs seller behavior analysis
- 📧 Automated daily seller analysis emails
- 🎯 Interactive bubble charts for holder visualization

## 🌐 Live Dashboard

Visit the live dashboard: **[GU Migration Tracker](https://gu-migration-tracker.herokuapp.com)**

### Dashboard Features:
- **Real-time Market Data**: Live floor prices, volumes, market caps
- **Migration Analytics**: Track NFT movements between collections
- **Interactive Charts**: Floor price trends, volume comparisons, supply growth
- **Market Comparison**: GU ecosystem vs industry averages
- **Mobile Responsive**: Works perfectly on all devices

## 📊 Dashboard Screenshots

*Real-time market data and migration analytics*

### Charts Available:
1. **Floor Price Trends** - Compare both collections over time
2. **Volume Analysis** - 24h trading volume comparison
3. **Collection Growth** - Genuine Undead supply increase over time
4. **Market Cap Comparison** - GU ecosystem vs NFT industry average
5. **Migration Activity** - Daily migration tracking with cumulative totals
6. **Holder Behavior Analysis** - Diamond hands vs seller distribution
7. **Interactive Bubble Charts** - Holder visualization with NFT counts
8. **Seller Analysis Reports** - Daily email reports on market activity

## 🚀 Quick Start

### For Users:
Simply visit the [live dashboard](https://gu-migration-tracker.herokuapp.com) - no setup required!

### For Developers:

```bash
# Clone the repository
git clone https://github.com/RRGU26/gu-migration-tracker.git
cd gu-migration-tracker

# Install dependencies
pip install -r requirements.txt
pip install -r dashboard/requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your OpenSea API key

# Initialize database
python main.py --mode setup

# Run the dashboard locally
cd dashboard
python app.py
```

Visit `http://localhost:5000` to see your local dashboard.

## 🔧 System Components

### 1. Data Collection Engine
- **OpenSea API Integration**: Real-time collection stats
- **Migration Detection**: Holder comparison algorithms  
- **Price Feeds**: ETH/USD conversion via CoinGecko
- **Rate Limiting**: Respects API limits with smart caching

### 2. Web Dashboard
- **Flask Backend**: RESTful API with real-time data
- **Interactive Frontend**: Modern UI with Plotly charts
- **Responsive Design**: Mobile-first approach
- **Auto-refresh**: Updates every 5 minutes

### 3. Database & Storage
- **SQLite Database**: Stores historical data and migrations
- **Daily Snapshots**: Collection metrics over time
- **Migration Tracking**: NFT movement detection
- **Report Generation**: Automated daily/weekly summaries

## 📈 Migration Detection Algorithm

The system tracks migrations by:

1. **Daily Snapshots**: Captures holder data for both collections
2. **Comparison Logic**: Identifies tokens that moved between collections
3. **Migration Velocity**: Calculates migration trends and rates
4. **Validation**: Cross-references with on-chain events

```python
# Simplified migration detection
if token_id in previous_origins and token_id not in current_origins:
    if token_id in current_undead:
        # Migration detected!
        save_migration(token_id, origins → undead, date)
```

## 🎨 API Endpoints

The dashboard provides these API endpoints:

- `GET /api/current` - Current market data
- `GET /api/refresh` - Force data refresh  
- `GET /api/charts` - Chart data for visualizations
- `GET /health` - System health check

## 📊 Market Insights

**Recent Observations:**
- GU ecosystem total value: **$3.9M+**
- Active trading in both collections
- Migration patterns emerging over time
- Floor price arbitrage opportunities

## 💎 Holder Behavior Analysis

**New Features:**

### 📈 Diamond Hands Analysis
- **92% of GU holders** are diamond hands (never listed)
- **89% of all NFTs** held by diamond hands
- Only **2.9% are heavy sellers** (3+ listings)
- Real-time holder categorization and tracking

### 📧 Daily Email Reports
- Automated seller analysis sent daily at 9:00 AM
- Complete breakdown of all active sellers
- Floor price monitoring and near-floor listings
- Seller concentration and risk assessment

### 🎯 Interactive Visualizations
- Bubble charts showing holder distribution
- Clean charts optimized for social media sharing
- Real-time data validation and accuracy checking
- Publication-ready graphics with verified statistics

## 🛠️ Advanced Usage

### Command Line Interface:
```bash
# Generate daily report
python main.py --mode daily

# Run system health check
python main.py --mode health

# Start automated scheduler
python main.py --mode scheduler

# Test with mock data
python main.py --mode test
```

### Holder Analysis Tools:
```bash
# Generate bubble chart visualization
python generate_genuine_undead_bubble.py

# Send daily seller analysis email
python complete_seller_analysis_email.py

# Create holder behavior analysis
python corrected_holder_analysis.py

# Generate clean chart for social media
python clean_chart.py

# Validate data accuracy before posting
python simple_validation.py
```

### Custom Reports:
```bash
# Generate custom report with real data
python generate_real_report.py
```

## 🔐 Environment Variables

```bash
# Required
OPENSEA_API_KEY=your_opensea_api_key_here

# Optional
ETHERSCAN_API_KEY=your_etherscan_api_key
EMAIL_FROM=your_email@domain.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@domain.com
```

## 📱 Mobile Support

The dashboard is fully responsive and optimized for:
- 📱 iPhone/Android phones
- 📱 Tablets 
- 💻 Desktop browsers
- 🖥️ Large displays

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenSea** for providing comprehensive NFT market data
- **GU Community** for the migration from Origins to Genuine Undead
- **CoinGecko** for cryptocurrency price feeds
- **Plotly** for interactive data visualizations

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/RRGU26/gu-migration-tracker/issues)
- **Community**: Join the GU Discord
- **Updates**: Watch this repository for updates

---

**Built with ❤️ for the GU community** 🧟‍♂️

*Real-time NFT analytics • Migration tracking • Market intelligence*# Trigger rebuild Tue, Sep  2, 2025 12:43:05 PM
# Force data refresh 1756906949
