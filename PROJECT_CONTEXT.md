# Genuine Undead Project Context

## Overview
Analytics dashboard for the Genuine Undead NFT collection and GUSTR token ecosystem.

## Dashboard Features

### Genuine Undead - Live Metrics
- Floor Price (ETH and USD)
- 24h Volume
- Market Cap
- Total Supply (5,744 NFTs)
- Unique Holders
- Listed count (% of supply)

### Genuine Undead - 30-Day Trends
- Floor Price change
- Migrations count
- Average daily volume
- Diamond Hands % (holders with no sales in 30d)

### GUSTR Token Metrics
- Market Cap
- Token Price (USD and ETH)
- Holder count with 24h % change
- 24h Volume and trade count
- NFTs held by strategy contract
- GUSTR burned percentage

### GUSTR Trading Activity (from DexScreener)
- Price changes: 5m, 1h, 6h, 24h
- Transaction counts: buys/sells with visual bar
- Volume: 24h total with 6h/1h breakdown
- Liquidity and FDV

## Data Sources
- **OpenSea API**: NFT collection data (floor, volume, supply, holders)
- **DexScreener API**: GUSTR token price, volume, transactions, liquidity
- **Etherscan Web Scraping**: GUSTR holder count
- **SQLite Database**: Historical snapshots for trend calculations

## Technical Stack
- **Backend**: Python Flask
- **Frontend**: HTML + Tailwind CSS
- **Database**: SQLite
- **Hosting**: GitHub auto-deployment

## Key Contracts
- **GUSTR Token**: `0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00`
- **Genuine Undead NFT**: OpenSea collection

## Related Projects

### Undead Land
Mobile/casual game featuring the Genuine Undead universe. Candy-themed zombie aesthetic with graveyard environments.

## API Limitations Discovered
- DexScreener API provides buy/sell transaction **counts** but NOT buy/sell **volume** breakdown
- Etherscan API v1 is deprecated; holder count requires web scraping
- Volume per transaction varies significantly (can't estimate buy/sell volume from tx counts)

## Recent Updates (Dec 2024)
1. Added GUSTR holder count via Etherscan scraping
2. Added GUSTR Trading Activity section with DexScreener data
3. Fixed Volume section to show real 6h/1h data instead of fake buy/sell estimates
4. Replaced Makers section with Liquidity/FDV (accurate data)
5. Standardized UI tiles across all sections
6. Fixed timezone display to show user's local time
