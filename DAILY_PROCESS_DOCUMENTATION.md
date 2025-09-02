# RR GU ANALYTIC TRACKER - DAILY PROCESS DOCUMENTATION

## Overview
This system tracks NFT migrations from GU Origins to Genuine Undead collections, calculating market metrics and generating reports.

## 9-STEP DAILY PROCESS

### STEP 1: Get Latest Ethereum Price
- **Source**: CoinGecko API (`src/api/price_client.py`)
- **Data**: Current ETH price in USD
- **Storage**: `daily_eth_prices` table
- **Example**: $4,266.24

### STEP 2: Get GU Origins Floor Price
- **Source**: OpenSea API
- **Collection**: `gu-origins`
- **Data**: Floor price in ETH
- **Current**: 0.0575 ETH

### STEP 3: Get Genuine Undead Floor Price
- **Source**: OpenSea API
- **Collection**: `genuine-undead`
- **Data**: Floor price in ETH
- **Current**: 0.0383 ETH

### STEP 4: Get Genuine Undead NFT Count
- **Source**: OpenSea API
- **Data**: Total supply (number of NFTs)
- **Current**: 5,037 NFTs
- **Note**: This represents migrations from Origins

### STEP 5: Log All Data Points
- **Storage**: SQLite database (`data/gu_migration.db`)
- **Tables Updated**:
  - `daily_eth_prices`: ETH price
  - `daily_snapshots`: Collection data
  - `daily_analytics`: Calculated metrics

### STEP 6: Calculate Market Caps
**Formula**: floor_price × eth_price × total_supply

- **Origins Market Cap**: 0.0575 ETH × $4,266.24 × 9,993 NFTs = $2,451,371
- **Undead Market Cap**: 0.0383 ETH × $4,266.24 × 5,037 NFTs = $823,031
- **Combined Market Cap**: $3,274,401

### STEP 7: Calculate Day-over-Day Migration Changes
- **Formula**: today_undead_supply - yesterday_undead_supply
- **Example**: 5,037 - 6,000 = -963 NFTs
- **Storage**: `undead_supply_change_24h` field

### STEP 8: Calculate Day-over-Day Floor Price Changes
- **Formula**: ((today_floor - yesterday_floor) / yesterday_floor) × 100
- **Origins Change**: -13.9%
- **Undead Change**: -31.0%
- **Storage**: `origins_floor_change_24h`, `undead_floor_change_24h`

### STEP 9: Calculate Price Ratio & Migration Percentage
- **Price Ratio**: undead_floor ÷ origins_floor = 0.0383 ÷ 0.0575 = 0.666x
- **Migration %**: (undead_supply ÷ origins_supply) × 100 = (5,037 ÷ 9,993) × 100 = 50.4%
- **Total Migrations**: undead_supply + 26 burned = 5,063

## OUTPUTS

### Dashboard (http://127.0.0.1:5000)
- Real-time display of all metrics
- Market cap charts
- Migration tracking charts
- PDF export functionality

### PDF Report
- Twitter-optimized format (600x600px)
- Professional charts with crisp fonts
- Key metrics summary
- Generated as `daily_report.pdf`

## DATABASE SCHEMA

### daily_analytics table
```sql
- analytics_date: Date of record
- eth_price_usd: Current ETH price
- origins_floor_eth: Origins floor price
- origins_supply: Fixed at 9,993
- origins_market_cap_usd: Calculated market cap
- origins_floor_change_24h: % change
- undead_floor_eth: Undead floor price  
- undead_supply: Current NFT count
- undead_market_cap_usd: Calculated market cap
- undead_floor_change_24h: % change
- undead_supply_change_24h: New migrations
- total_migrations: Supply + 26 burned
- migration_percent: (undead/origins) × 100
- price_ratio: undead_floor/origins_floor
- combined_market_cap_usd: Total ecosystem value
```

## KEY CONSTANTS
- **Origins Supply**: 9,993 NFTs (fixed)
- **Burned GU**: 26 (always added to migration count)
- **Collection IDs**: Origins = 1, Undead = 2

## AUTOMATED EXECUTION
Run daily at specified time:
```bash
cd gu-migration-tracker
python src/services/daily_collection_runner.py
```

## ERROR HANDLING
- OpenSea API rate limiting: Uses cached values if API unavailable
- Missing data: Logs errors and continues with available data
- Database failures: Retries with exponential backoff

## VERIFICATION
After each run, the system:
1. Reads back saved data from database
2. Verifies all calculations
3. Logs confirmation of successful storage
4. Updates dashboard with new data
5. Generates PDF report

## CRITICAL FORMULAS
- **Market Cap** = floor_price_eth × eth_price_usd × total_supply
- **Migration %** = (undead_supply ÷ origins_supply) × 100
- **Price Ratio** = undead_floor ÷ origins_floor
- **Total Migrations** = undead_supply + 26 burned
- **Daily Change** = today_value - yesterday_value
- **% Change** = ((today - yesterday) ÷ yesterday) × 100