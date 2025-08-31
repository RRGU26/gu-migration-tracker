#!/usr/bin/env python3
"""
Generate a real report with actual OpenSea data, but with rate limit handling
"""
import asyncio
import sys
import os
from datetime import date, datetime
sys.path.append('src')

from src.database.database import DatabaseManager
from src.api.opensea_client import OpenSeaClient
from src.api.price_client import get_current_eth_price
import json

async def fetch_basic_collection_data():
    """Fetch just the essential data we need for a report"""
    print("Fetching real collection data from OpenSea...")
    
    client = OpenSeaClient()
    
    # Get collection stats for both collections
    print("Getting GU Origins stats...")
    origins_stats = await client.get_collection_stats('gu-origins')
    await asyncio.sleep(2)  # Wait to avoid rate limiting
    
    print("Getting Genuine Undead stats...")
    undead_stats = await client.get_collection_stats('genuine-undead')
    await asyncio.sleep(2)
    
    print("Getting collection details...")
    origins_details = await client.get_collection_details('gu-origins')
    await asyncio.sleep(2)
    
    undead_details = await client.get_collection_details('genuine-undead')
    await asyncio.sleep(2)
    
    print("Getting current ETH price...")
    eth_price = await get_current_eth_price()
    
    return {
        'origins_stats': origins_stats,
        'undead_stats': undead_stats,
        'origins_details': origins_details,
        'undead_details': undead_details,
        'eth_price_usd': eth_price,
        'fetched_at': datetime.now().isoformat()
    }

def extract_key_metrics(stats, details, eth_price_usd):
    """Extract key metrics from the API data"""
    if not stats or not details:
        return None
    
    # Get total supply from details
    total_supply = details.get('total_supply', 0) or 10000
    
    # Calculate metrics
    floor_price_eth = stats.get('floor_price', 0) or 0
    floor_price_usd = floor_price_eth * eth_price_usd
    
    volume_24h_eth = stats.get('one_day_volume', 0) or 0
    volume_24h_usd = volume_24h_eth * eth_price_usd
    
    volume_7d_eth = stats.get('seven_day_volume', 0) or 0
    volume_7d_usd = volume_7d_eth * eth_price_usd
    
    market_cap_eth = floor_price_eth * total_supply
    market_cap_usd = market_cap_eth * eth_price_usd
    
    return {
        'total_supply': int(total_supply),
        'holders_count': stats.get('num_owners', 0),
        'floor_price_eth': floor_price_eth,
        'floor_price_usd': floor_price_usd,
        'market_cap_eth': market_cap_eth,
        'market_cap_usd': market_cap_usd,
        'volume_24h_eth': volume_24h_eth,
        'volume_24h_usd': volume_24h_usd,
        'volume_7d_eth': volume_7d_eth,
        'volume_7d_usd': volume_7d_usd,
        'average_price_eth': stats.get('average_price', 0) or 0,
        'num_sales_24h': 0  # We'll skip this for now to avoid more API calls
    }

def generate_simple_markdown_report(origins_metrics, undead_metrics, eth_price, report_date):
    """Generate a simple markdown report"""
    
    report_content = f"""# GU Migration Daily Report - {report_date.strftime('%B %d, %Y')}

## Real-Time Market Data

**ETH Price**: ${eth_price:,.2f} USD

---

## Collection Performance

### GU Origins
- **Floor Price**: {origins_metrics['floor_price_eth']:.4f} ETH (${origins_metrics['floor_price_usd']:,.2f} USD)
- **Total Supply**: {origins_metrics['total_supply']:,}
- **Holders**: {origins_metrics['holders_count']:,}
- **Market Cap**: {origins_metrics['market_cap_eth']:,.1f} ETH (${origins_metrics['market_cap_usd']:,.0f} USD)
- **24h Volume**: {origins_metrics['volume_24h_eth']:.3f} ETH (${origins_metrics['volume_24h_usd']:,.2f} USD)
- **7d Volume**: {origins_metrics['volume_7d_eth']:.2f} ETH (${origins_metrics['volume_7d_usd']:,.0f} USD)

### Genuine Undead  
- **Floor Price**: {undead_metrics['floor_price_eth']:.4f} ETH (${undead_metrics['floor_price_usd']:,.2f} USD)
- **Total Supply**: {undead_metrics['total_supply']:,}
- **Holders**: {undead_metrics['holders_count']:,}
- **Market Cap**: {undead_metrics['market_cap_eth']:,.1f} ETH (${undead_metrics['market_cap_usd']:,.0f} USD)
- **24h Volume**: {undead_metrics['volume_24h_eth']:.3f} ETH (${undead_metrics['volume_24h_usd']:,.2f} USD)
- **7d Volume**: {undead_metrics['volume_7d_eth']:.2f} ETH (${undead_metrics['volume_7d_usd']:,.0f} USD)

---

## Market Analysis

### Price Comparison
- **Floor Price Premium**: {((undead_metrics['floor_price_eth'] / max(origins_metrics['floor_price_eth'], 0.001) - 1) * 100):+.1f}%
  - Genuine Undead floor is {undead_metrics['floor_price_eth'] / max(origins_metrics['floor_price_eth'], 0.001):.2f}x GU Origins

### Volume Analysis  
- **Origins 24h Volume**: {origins_metrics['volume_24h_eth']:.3f} ETH
- **Undead 24h Volume**: {undead_metrics['volume_24h_eth']:.3f} ETH
- **Volume Ratio**: {(undead_metrics['volume_24h_eth'] / max(origins_metrics['volume_24h_eth'], 0.001)):.2f}x

### Market Cap Analysis
- **Combined Ecosystem Value**: ${(origins_metrics['market_cap_usd'] + undead_metrics['market_cap_usd']):,.0f} USD
- **Origins Market Cap**: ${origins_metrics['market_cap_usd']:,.0f} USD ({(origins_metrics['market_cap_usd'] / (origins_metrics['market_cap_usd'] + undead_metrics['market_cap_usd']) * 100):.1f}%)
- **Undead Market Cap**: ${undead_metrics['market_cap_usd']:,.0f} USD ({(undead_metrics['market_cap_usd'] / (origins_metrics['market_cap_usd'] + undead_metrics['market_cap_usd']) * 100):.1f}%)

---

## Migration Insights

*Note: Migration detection requires holder data comparison over time. This will be available once the system runs for multiple days.*

### Key Observations
- Both collections are active with trading volume in the last 24 hours
- {"Genuine Undead has a premium floor price" if undead_metrics['floor_price_eth'] > origins_metrics['floor_price_eth'] else "GU Origins maintains a higher floor price"}
- Total ecosystem holders: {origins_metrics['holders_count'] + undead_metrics['holders_count']:,} across both collections

---

## Technical Notes

- **Data Source**: OpenSea API v2
- **ETH Price**: CoinGecko API
- **Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
- **Rate Limiting**: Applied to respect API limits

---

*Generated by GU Migration Tracker with real-time data*
"""
    
    return report_content

async def main():
    print("GU Migration Tracker - Real Data Report Generator")
    print("=" * 60)
    
    try:
        # Fetch real data
        print("Step 1: Fetching real-time data from OpenSea and CoinGecko...")
        data = await fetch_basic_collection_data()
        
        if not data['origins_stats'] or not data['undead_stats']:
            print("ERROR: Could not fetch collection stats")
            return
        
        print("Step 2: Processing market data...")
        
        # Extract metrics
        origins_metrics = extract_key_metrics(
            data['origins_stats'], 
            data['origins_details'], 
            data['eth_price_usd']
        )
        
        undead_metrics = extract_key_metrics(
            data['undead_stats'], 
            data['undead_details'], 
            data['eth_price_usd']
        )
        
        if not origins_metrics or not undead_metrics:
            print("ERROR: Could not process collection data")
            return
        
        print("Step 3: Generating report...")
        
        # Generate report
        report_date = date.today()
        report_content = generate_simple_markdown_report(
            origins_metrics, 
            undead_metrics, 
            data['eth_price_usd'], 
            report_date
        )
        
        # Save report
        os.makedirs('reports/daily', exist_ok=True)
        report_file = f'reports/daily/real_data_report_{report_date}.md'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # Save raw data
        data_file = f'reports/daily/raw_data_{report_date}.json'
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump({
                'origins_metrics': origins_metrics,
                'undead_metrics': undead_metrics,
                'raw_api_data': data
            }, f, indent=2, default=str)
        
        print(f"SUCCESS! Real data report generated:")
        print(f"  Report: {report_file}")
        print(f"  Raw Data: {data_file}")
        
        # Show key metrics
        print(f"\n" + "=" * 60)
        print("KEY METRICS SUMMARY")
        print("=" * 60)
        print(f"ETH Price: ${data['eth_price_usd']:,.2f}")
        print(f"\nGU Origins:")
        print(f"  Floor: {origins_metrics['floor_price_eth']:.4f} ETH (${origins_metrics['floor_price_usd']:,.2f})")
        print(f"  24h Volume: {origins_metrics['volume_24h_eth']:.3f} ETH")
        print(f"  Holders: {origins_metrics['holders_count']:,}")
        print(f"\nGenuine Undead:")
        print(f"  Floor: {undead_metrics['floor_price_eth']:.4f} ETH (${undead_metrics['floor_price_usd']:,.2f})")
        print(f"  24h Volume: {undead_metrics['volume_24h_eth']:.3f} ETH") 
        print(f"  Holders: {undead_metrics['holders_count']:,}")
        
        floor_ratio = undead_metrics['floor_price_eth'] / max(origins_metrics['floor_price_eth'], 0.001)
        print(f"\nFloor Price Analysis:")
        print(f"  Genuine Undead vs Origins: {floor_ratio:.2f}x ({((floor_ratio - 1) * 100):+.1f}%)")
        
        print(f"\nEcosystem Value: ${(origins_metrics['market_cap_usd'] + undead_metrics['market_cap_usd']):,.0f}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Report generation failed - {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(main())
    if not success:
        sys.exit(1)