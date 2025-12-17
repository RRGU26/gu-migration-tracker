#!/usr/bin/env python3
"""
Simplified GU Migration Tracker Dashboard
Direct database connection, no complex caching
"""
import os
import sys
from datetime import datetime, date
from flask import Flask, render_template, jsonify, send_file

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.database.database import DatabaseManager
from src.api.price_client import get_current_eth_price
import requests
import subprocess
import threading

app = Flask(__name__)

# Single database connection
db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gu_migration.db')
db = DatabaseManager(db_path)

def get_gustr_token_data():
    """Get GUSTR token data from DexScreener API"""
    try:
        response = requests.get(
            'https://api.dexscreener.com/latest/dex/tokens/0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00',
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs') and len(data['pairs']) > 0:
                pair = data['pairs'][0]
                return {
                    'price_usd': float(pair.get('priceUsd', 0)),
                    'price_eth': float(pair.get('priceNative', 0)),
                    'market_cap': float(pair.get('marketCap', 0) or pair.get('fdv', 0)),
                    'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                    'price_change_6h': float(pair.get('priceChange', {}).get('h6', 0)),
                    'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0)),
                    'buys_24h': int(pair.get('txns', {}).get('h24', {}).get('buys', 0)),
                    'sells_24h': int(pair.get('txns', {}).get('h24', {}).get('sells', 0))
                }
        return None
    except Exception as e:
        print(f"Error fetching GUSTR data: {e}")
        return None


def get_strategy_nft_holdings():
    """Get NFT holdings count for the GUSTR strategy contract"""
    try:
        # Strategy contract address
        strategy_address = '0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00'
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}

        # Query OpenSea for NFTs owned by the strategy
        response = requests.get(
            f'https://api.opensea.io/api/v2/chain/ethereum/account/{strategy_address}/nfts',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            nfts = data.get('nfts', [])
            # Count NFTs from Genuine Undead collection
            gu_nfts = [nft for nft in nfts if 'genuine' in nft.get('collection', '').lower() or 'undead' in nft.get('collection', '').lower()]
            return len(gu_nfts) if gu_nfts else len(nfts)
        return 0
    except Exception as e:
        print(f"Error fetching strategy NFT holdings: {e}")
        return 0


def get_gustr_burn_amount():
    """Get GUSTR tokens burned from TokenStrategy API"""
    try:
        response = requests.get(
            'https://www.tokenstrategy.com/api/strategies/0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00',
            timeout=10
        )
        if response.status_code == 200:
            json_data = response.json()
            # Response is wrapped in a "data" object
            data = json_data.get('data', {})
            # Burned amount is in raw token units (18 decimals) - field is "burnedAmount"
            burned_raw = int(data.get('burnedAmount', 0) or 0)
            # Convert to human readable (divide by 10^18)
            burned_tokens = burned_raw / (10 ** 18)
            # Total supply is 1 billion
            total_supply = 1_000_000_000
            burn_percent = (burned_tokens / total_supply) * 100
            return {
                'burned_tokens': burned_tokens,
                'burn_percent': burn_percent
            }
        return {'burned_tokens': 0, 'burn_percent': 0}
    except Exception as e:
        print(f"Error fetching GUSTR burn amount: {e}")
        return {'burned_tokens': 0, 'burn_percent': 0}


def get_gustr_holder_count():
    """Get GUSTR token holder count by scraping Etherscan token page"""
    try:
        import re
        # GUSTR token contract address
        gustr_address = '0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00'

        # Scrape Etherscan token page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        url = f'https://etherscan.io/token/{gustr_address}'
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            html = response.text
            # Look for holder count in meta description: "Holders: 80 |"
            match = re.search(r'Holders:\s*([\d,]+)', html)
            if match:
                holder_count = int(match.group(1).replace(',', ''))
                return {'holder_count': holder_count, 'source': 'etherscan_web'}

        return {'holder_count': None, 'source': None}
    except Exception as e:
        print(f"Error fetching GUSTR holder count: {e}")
        return {'holder_count': None, 'source': None}


def get_gustr_holder_change():
    """Get GUSTR holder count change from database"""
    try:
        with db.get_connection() as conn:
            # Get yesterday's holder count
            cursor = conn.execute("""
                SELECT holder_count FROM gustr_daily_snapshots
                WHERE snapshot_date = date('now', '-1 day')
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row and row['holder_count']:
                return row['holder_count']
        return None
    except Exception as e:
        print(f"Error getting GUSTR holder change: {e}")
        return None


def save_gustr_snapshot(holder_count, market_cap, price_usd, volume_24h):
    """Save daily GUSTR snapshot to database"""
    try:
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO gustr_daily_snapshots
                (snapshot_date, holder_count, market_cap_usd, price_usd, volume_24h_usd)
                VALUES (date('now'), ?, ?, ?, ?)
            """, (holder_count, market_cap, price_usd, volume_24h))
            conn.commit()
    except Exception as e:
        print(f"Error saving GUSTR snapshot: {e}")


def get_quick_volume_data():
    """Get volume data directly from OpenSea API"""
    try:
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        
        # Get Origins volume
        origins_response = requests.get('https://api.opensea.io/api/v2/collections/gu-origins/stats', 
                                       headers=headers, timeout=5)
        origins_vol = 0.0127  # fallback
        if origins_response.status_code == 200:
            origins_data = origins_response.json()
            if 'intervals' in origins_data:
                for interval in origins_data['intervals']:
                    if interval.get('interval') == 'one_day':
                        origins_vol = float(interval.get('volume', 0.0127))
                        break
        
        # Get Undead volume
        undead_response = requests.get('https://api.opensea.io/api/v2/collections/genuine-undead/stats', 
                                      headers=headers, timeout=5)
        undead_vol = 0.033  # fallback
        if undead_response.status_code == 200:
            undead_data = undead_response.json()
            if 'intervals' in undead_data:
                for interval in undead_data['intervals']:
                    if interval.get('interval') == 'one_day':
                        undead_vol = float(interval.get('volume', 0.033))
                        break
                        
        return origins_vol, undead_vol
    except:
        return 0.0127, 0.033  # fallback values

def get_live_floor_prices_and_supply():
    """Get live floor prices, supplies, and holder count from OpenSea API"""
    try:
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}

        # Get Origins floor price
        origins_response = requests.get('https://api.opensea.io/api/v2/collections/gu-origins/stats',
                                       headers=headers, timeout=5)
        origins_floor = 0.0330
        origins_supply = 9993
        if origins_response.status_code == 200:
            origins_data = origins_response.json()
            origins_floor = float(origins_data.get('total', {}).get('floor_price', 0.0330))

        # Get Undead stats (floor, num_owners)
        undead_response = requests.get('https://api.opensea.io/api/v2/collections/genuine-undead/stats',
                                      headers=headers, timeout=5)
        undead_floor = 0.0460
        undead_holders = 718
        if undead_response.status_code == 200:
            undead_data = undead_response.json()
            undead_floor = float(undead_data.get('total', {}).get('floor_price', 0.0460))
            undead_holders = int(undead_data.get('total', {}).get('num_owners', 718))

        # Get Undead supply
        undead_supply = 5566
        undead_collection_response = requests.get('https://api.opensea.io/api/v2/collections/genuine-undead',
                                                headers=headers, timeout=5)
        if undead_collection_response.status_code == 200:
            undead_collection = undead_collection_response.json()
            undead_supply = int(undead_collection.get('total_supply', 5566))

        return origins_floor, undead_floor, origins_supply, undead_supply, undead_holders

    except Exception as e:
        print(f"Floor price/supply fetch error: {e}")
        return 0.0330, 0.0460, 9993, 5566, 718


def get_listings_count():
    """Get total number of active listings"""
    try:
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        total = 0
        next_cursor = None
        for _ in range(3):
            params = {'limit': 200}
            if next_cursor:
                params['next'] = next_cursor
            response = requests.get('https://api.opensea.io/api/v2/listings/collection/genuine-undead/all',
                                   headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                total += len(data.get('listings', []))
                next_cursor = data.get('next')
                if not next_cursor:
                    break
            else:
                break
        return total
    except:
        return 0


def get_diamond_hands_percent(total_holders):
    """Calculate % of holders who haven't sold in last 30 days"""
    try:
        import time
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        thirty_days_ago = int(time.time()) - (30 * 24 * 60 * 60)
        sellers = set()
        next_cursor = None
        total_sales_30d = 0

        for _ in range(5):
            url = 'https://api.opensea.io/api/v2/events/collection/genuine-undead'
            params = {'event_type': 'sale', 'limit': 50}
            if next_cursor:
                params['next'] = next_cursor

            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code != 200:
                break

            data = response.json()
            events = data.get('asset_events', [])
            if not events:
                break

            for event in events:
                timestamp = event.get('event_timestamp', 0)
                if timestamp >= thirty_days_ago:
                    total_sales_30d += 1
                    if event.get('seller'):
                        sellers.add(event['seller'].lower())

            next_cursor = data.get('next')
            if not next_cursor:
                break

        if total_holders > 0:
            diamond_hands = total_holders - len(sellers)
            diamond_pct = round((diamond_hands / total_holders) * 100, 1)
            return diamond_pct, len(sellers), total_sales_30d
        return 0.0, 0, 0

    except Exception as e:
        print(f'Diamond hands calc error: {e}')
        return 0.0, 0, 0


@app.route('/')
def index():
    """Serve the dashboard"""
    return render_template('dashboard.html')

@app.route('/api/current')
def get_current_data():
    """Get current data directly from database - no caching, always fresh"""
    try:
        # Get fresh ETH price from API
        import asyncio
        try:
            eth_price = asyncio.run(get_current_eth_price())
            if not eth_price or eth_price <= 0:
                eth_price = 2600.0  # Fallback
        except:
            eth_price = 2600.0  # Fallback

        with db.get_connection() as conn:
            # Get the latest analytics data
            cursor = conn.execute("""
                SELECT
                    analytics_date,
                    eth_price_usd,
                    origins_floor_eth,
                    origins_supply,
                    origins_market_cap_usd,
                    origins_floor_change_24h,
                    undead_floor_eth,
                    undead_supply,
                    undead_market_cap_usd,
                    undead_floor_change_24h,
                    total_migrations,
                    migration_percent,
                    price_ratio,
                    combined_market_cap_usd
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 1
            """)

            row = cursor.fetchone()

            if not row:
                # Return default values if no data
                return jsonify({
                    'error': 'No data available',
                    'timestamp': datetime.now().isoformat()
                })

            # Get real volume data
            try:
                origins_vol, undead_vol = get_quick_volume_data()
            except:
                origins_vol, undead_vol = 0.0127, 0.033
            
            # Get 30-day historical data for trends
            cursor_30d = conn.execute("""
                SELECT
                    undead_floor_eth,
                    undead_supply,
                    undead_market_cap_usd,
                    analytics_date
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 30
            """)

            historical_data = cursor_30d.fetchall()

            # Calculate 30-day trends
            trends = {
                'floor_price_change_30d': 0.0,
                'supply_growth_30d': 0,
                'market_cap_change_30d': 0.0,
                'avg_daily_volume_30d': undead_vol,  # Simplified for now
                'holder_count': row['undead_supply']  # Using supply as proxy
            }

            if len(historical_data) >= 2:
                # Floor price change (current vs 30 days ago)
                oldest = historical_data[-1]
                current_floor = row['undead_floor_eth']
                old_floor = oldest['undead_floor_eth']
                if old_floor > 0:
                    trends['floor_price_change_30d'] = ((current_floor - old_floor) / old_floor) * 100

                # Supply growth (current vs 30 days ago)
                current_supply = row['undead_supply']
                old_supply = oldest['undead_supply']
                trends['supply_growth_30d'] = current_supply - old_supply

                # Market cap change (current vs 30 days ago)
                current_mc = row['undead_floor_eth'] * eth_price * row['undead_supply']
                old_mc = oldest['undead_market_cap_usd']
                if old_mc > 0:
                    trends['market_cap_change_30d'] = ((current_mc - old_mc) / old_mc) * 100

            # Build response using fresh ETH price - focused on Genuine Undead
            data = {
                'timestamp': datetime.now().isoformat(),
                'analytics_date': row['analytics_date'],
                'eth_price_usd': eth_price,
                'undead': {
                    'floor_price_eth': row['undead_floor_eth'],
                    'floor_price_usd': row['undead_floor_eth'] * eth_price,
                    'total_supply': row['undead_supply'],
                    'market_cap_usd': row['undead_floor_eth'] * eth_price * row['undead_supply'],
                    'floor_change_24h': 0.0,  # Removed for reliability
                    'volume_24h_eth': undead_vol,
                    'holders_count': row['undead_supply']  # Will be actual holders when available
                },
                'trends': trends
            }

            return jsonify(data)
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/refresh')
def refresh_data():
    """Get live ETH price and fresh volume data immediately - Updated Sept 13"""
    try:
        # Get live ETH price directly
        import asyncio
        live_eth_price = None
        try:
            live_eth_price = asyncio.run(get_current_eth_price())
            if not live_eth_price or live_eth_price <= 0:
                raise ValueError("Invalid ETH price")
        except Exception as e:
            print(f"Error fetching ETH price: {e}")
            # Use existing database price as fallback
            with db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT eth_price_usd FROM daily_analytics 
                    WHERE analytics_date = ? 
                    LIMIT 1
                """, (date.today().isoformat(),))
                row = cursor.fetchone()
                if row and row['eth_price_usd']:
                    live_eth_price = row['eth_price_usd']
                else:
                    live_eth_price = 4418  # Updated fallback to current price
        
        # Get live floor prices, supplies, holders, and listings
        try:
            origins_floor, undead_floor, origins_supply, undead_supply, undead_holders = get_live_floor_prices_and_supply()
        except:
            origins_floor, undead_floor, origins_supply, undead_supply, undead_holders = 0.0330, 0.0460, 9993, 5566, 718
        
        # Get listings count
        try:
            num_listed = get_listings_count()
        except:
            num_listed = 0

        # Calculate diamond hands % (recalculates on every refresh)
        try:
            diamond_hands_pct, num_sellers_30d, total_sales_30d = get_diamond_hands_percent(undead_holders)
        except:
            diamond_hands_pct, num_sellers_30d, total_sales_30d = 0.0, 0, 0

        with db.get_connection() as conn:
            # Update ETH price and floor prices in database
            today = date.today().isoformat()
            # Calculate metrics for INSERT
            origins_mc = origins_floor * origins_supply * live_eth_price
            undead_mc_calc = undead_floor * undead_supply * live_eth_price
            total_mig = undead_supply + 26
            mig_pct = (undead_supply / 9993) * 100
            p_ratio = undead_floor / origins_floor if origins_floor > 0 else 0

            # INSERT OR REPLACE - creates today data if missing
            conn.execute("""
                INSERT OR REPLACE INTO daily_analytics (
                    analytics_date, eth_price_usd,
                    origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                    undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                    total_migrations, migration_percent, price_ratio, combined_market_cap_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (today, live_eth_price, origins_floor, origins_supply, origins_mc, 0.0,
                  undead_floor, undead_supply, undead_mc_calc, 0.0, total_mig, mig_pct, p_ratio, origins_mc + undead_mc_calc))
            
            conn.execute("""
                INSERT OR REPLACE INTO daily_eth_prices (price_date, eth_price_usd)
                VALUES (?, ?)
            """, (today, live_eth_price))
            conn.commit()
            
            # Get today's data for other fields
            cursor = conn.execute("""
                SELECT 
                    analytics_date, eth_price_usd, origins_floor_eth, origins_supply,
                    origins_market_cap_usd, origins_floor_change_24h, undead_floor_eth, 
                    undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                    total_migrations, migration_percent, price_ratio, combined_market_cap_usd
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'No data available'}), 404
                
            # Note: 24h change calculations removed for simplicity and reliability

            # Get fresh volume data
            try:
                origins_vol, undead_vol = get_quick_volume_data()
            except:
                origins_vol, undead_vol = 0.09, 0.49

            # Recalculate market cap with live floor price, ETH price, and supply
            undead_mc = undead_floor * live_eth_price * undead_supply

            # Get 30-day historical data for trends
            cursor_30d = conn.execute("""
                SELECT
                    undead_floor_eth,
                    undead_supply,
                    undead_market_cap_usd,
                    analytics_date
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 30
            """)

            historical_data = cursor_30d.fetchall()

            # Calculate trends from historical data
            trends = {
                'floor_price_change_30d': 0.0,
                'floor_price_change_7d': 0.0,
                'floor_price_change_1d': 0.0,
                'supply_growth_30d': 0,
                'market_cap_change_30d': 0.0,
                'avg_daily_volume_30d': undead_vol,
                'holder_count': undead_holders,
                'num_listed': num_listed
            }

            if len(historical_data) >= 2:
                # 30-day changes
                oldest = historical_data[-1]
                if oldest['undead_floor_eth'] > 0:
                    trends['floor_price_change_30d'] = ((undead_floor - oldest['undead_floor_eth']) / oldest['undead_floor_eth']) * 100
                trends['supply_growth_30d'] = undead_supply - oldest['undead_supply']
                if oldest['undead_market_cap_usd'] > 0:
                    trends['market_cap_change_30d'] = ((undead_mc - oldest['undead_market_cap_usd']) / oldest['undead_market_cap_usd']) * 100
                
                # 7-day change (if we have at least 7 days of data)
                if len(historical_data) >= 7:
                    day7 = historical_data[6]
                    if day7['undead_floor_eth'] > 0:
                        trends['floor_price_change_7d'] = ((undead_floor - day7['undead_floor_eth']) / day7['undead_floor_eth']) * 100
                
                # 1-day change (yesterday vs today)
                if len(historical_data) >= 1:
                    yesterday = historical_data[0]  # Most recent is index 0 after today is inserted
                    if yesterday['undead_floor_eth'] > 0 and yesterday['analytics_date'] != today:
                        trends['floor_price_change_1d'] = ((undead_floor - yesterday['undead_floor_eth']) / yesterday['undead_floor_eth']) * 100

            # Build response with live data
            data = {
                'timestamp': datetime.now().isoformat(),
                'analytics_date': today,
                'eth_price_usd': live_eth_price,
                'undead': {
                    'floor_price_eth': undead_floor,
                    'floor_price_usd': undead_floor * live_eth_price,
                    'total_supply': undead_supply,
                    'market_cap_usd': undead_mc,
                    'floor_change_24h': trends['floor_price_change_1d'],
                    'volume_24h_eth': undead_vol,
                    'holders_count': undead_holders,
                    'num_listed': num_listed,
                    'listing_percent': (num_listed / undead_supply * 100) if undead_supply > 0 else 0,
                    'diamond_hands_pct': diamond_hands_pct,
                    'num_sellers_30d': num_sellers_30d,
                    'total_sales_30d': total_sales_30d
                },
                'trends': trends
            }

            return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts')
def get_chart_data():
    """Get historical data for charts"""
    try:
        with db.get_connection() as conn:
            # Get last 30 days of data (last 3 days + next 27 for projection)
            cursor = conn.execute("""
                SELECT 
                    analytics_date,
                    origins_floor_eth,
                    undead_floor_eth,
                    origins_market_cap_usd,
                    undead_market_cap_usd,
                    total_migrations,
                    undead_supply
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 30
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                return jsonify({'charts': []})
            
            # Build chart data - focus on Genuine Undead trends
            dates = []
            floor_prices = []
            undead_mc = []
            undead_supply = []

            for row in reversed(rows):  # Reverse to get chronological order
                dates.append(row['analytics_date'])
                floor_prices.append(row['undead_floor_eth'])
                undead_mc.append(row['undead_market_cap_usd'])
                undead_supply.append(row['undead_supply'])

            # Create clean, professional charts focused on GU trends
            charts_data = {
                'floor_price_chart': {
                    'data': [{
                        'x': dates,
                        'y': floor_prices,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': 'Floor Price',
                        'line': {'color': '#8b5cf6', 'width': 3},
                        'marker': {'size': 8, 'color': '#8b5cf6', 'line': {'color': 'white', 'width': 1}},
                        'hovertemplate': '<b>%{y:.4f}</b> ETH<br>%{x}<extra></extra>',
                        'fill': 'tozeroy',
                        'fillcolor': 'rgba(139, 92, 246, 0.1)'
                    }],
                    'layout': {
                        'title': {
                            'text': 'Floor Price Trend (30 Days)',
                            'x': 0.5,
                            'font': {'size': 18, 'family': 'Arial, sans-serif', 'color': '#1f2937'}
                        },
                        'xaxis': {
                            'title': '',
                            'showgrid': False,
                            'showline': True,
                            'linecolor': '#e5e7eb',
                            'tickfont': {'size': 12, 'color': '#6b7280'}
                        },
                        'yaxis': {
                            'title': 'Floor Price (ETH)',
                            'titlefont': {'size': 14, 'color': '#6b7280'},
                            'showgrid': True,
                            'gridcolor': '#f3f4f6',
                            'showline': True,
                            'linecolor': '#e5e7eb',
                            'tickfont': {'size': 12, 'color': '#6b7280'},
                            'tickformat': '.4f'
                        },
                        'plot_bgcolor': 'rgba(0,0,0,0)',
                        'paper_bgcolor': 'rgba(0,0,0,0)',
                        'margin': {'t': 50, 'l': 60, 'r': 20, 'b': 40},
                        'showlegend': False,
                        'height': 350
                    }
                },
                'market_cap_chart': {
                    'data': [{
                        'x': dates,
                        'y': undead_mc,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': 'Market Cap',
                        'line': {'color': '#10b981', 'width': 3},
                        'marker': {'size': 8, 'color': '#10b981', 'line': {'color': 'white', 'width': 1}},
                        'hovertemplate': '<b>$%{y:,.0f}</b><br>%{x}<extra></extra>',
                        'fill': 'tozeroy',
                        'fillcolor': 'rgba(16, 185, 129, 0.1)'
                    }],
                    'layout': {
                        'title': {
                            'text': 'Market Cap Trend (30 Days)',
                            'x': 0.5,
                            'font': {'size': 18, 'family': 'Arial, sans-serif', 'color': '#1f2937'}
                        },
                        'xaxis': {
                            'title': '',
                            'showgrid': False,
                            'showline': True,
                            'linecolor': '#e5e7eb',
                            'tickfont': {'size': 12, 'color': '#6b7280'}
                        },
                        'yaxis': {
                            'title': 'Market Cap (USD)',
                            'titlefont': {'size': 14, 'color': '#6b7280'},
                            'showgrid': True,
                            'gridcolor': '#f3f4f6',
                            'showline': True,
                            'linecolor': '#e5e7eb',
                            'tickfont': {'size': 12, 'color': '#6b7280'},
                            'tickformat': '$,.0f'
                        },
                        'plot_bgcolor': 'rgba(0,0,0,0)',
                        'paper_bgcolor': 'rgba(0,0,0,0)',
                        'margin': {'t': 50, 'l': 80, 'r': 20, 'b': 60},
                        'showlegend': False,
                        'height': 350
                    }
                },
                'supply_chart': {
                    'data': [{
                        'x': dates,
                        'y': undead_supply,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': 'Supply',
                        'line': {'color': '#3b82f6', 'width': 3},
                        'marker': {'size': 8, 'color': '#3b82f6', 'line': {'color': 'white', 'width': 1}},
                        'hovertemplate': '<b>%{y:,}</b> NFTs<br>%{x}<extra></extra>',
                        'fill': 'tozeroy',
                        'fillcolor': 'rgba(59, 130, 246, 0.1)'
                    }],
                    'layout': {
                        'title': {
                            'text': 'Supply Growth (30 Days)',
                            'x': 0.5,
                            'font': {'size': 18, 'family': 'Arial, sans-serif', 'color': '#1f2937'}
                        },
                        'xaxis': {
                            'title': '',
                            'showgrid': False,
                            'showline': True,
                            'linecolor': '#e5e7eb',
                            'tickfont': {'size': 12, 'color': '#6b7280'}
                        },
                        'yaxis': {
                            'title': 'NFT Count',
                            'titlefont': {'size': 14, 'color': '#6b7280'},
                            'showgrid': True,
                            'gridcolor': '#f3f4f6',
                            'showline': True,
                            'linecolor': '#e5e7eb',
                            'tickfont': {'size': 12, 'color': '#6b7280'},
                            'tickformat': ',.0f'
                        },
                        'plot_bgcolor': 'rgba(0,0,0,0)',
                        'paper_bgcolor': 'rgba(0,0,0,0)',
                        'margin': {'t': 50, 'l': 60, 'r': 20, 'b': 40},
                        'showlegend': False,
                        'height': 350
                    }
                }
            }
            
            return jsonify(charts_data)
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'charts': []
        }), 500

@app.route('/api/gustr')
def get_gustr_data():
    """Get GUSTR token metrics"""
    try:
        # Get token data from DexScreener
        token_data = get_gustr_token_data()

        # Get NFT holdings count
        nft_holdings = get_strategy_nft_holdings()

        # Get burn data from TokenStrategy
        burn_data = get_gustr_burn_amount()

        # Get holder count from Etherscan
        holder_data = get_gustr_holder_count()
        holder_count = holder_data.get('holder_count')

        # Get yesterday's holder count for % change
        yesterday_holders = get_gustr_holder_change()
        holder_change_pct = None
        if holder_count and yesterday_holders and yesterday_holders > 0:
            holder_change_pct = ((holder_count - yesterday_holders) / yesterday_holders) * 100

        # Save today's snapshot if we have holder data
        if token_data and holder_count:
            save_gustr_snapshot(
                holder_count,
                token_data.get('market_cap', 0),
                token_data.get('price_usd', 0),
                token_data.get('volume_24h', 0)
            )

        if token_data:
            response_data = {
                'timestamp': datetime.now().isoformat(),
                'token': {
                    'name': 'GenuineUndeadStrategy',
                    'symbol': 'GUSTR',
                    'address': '0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00',
                    'price_usd': token_data['price_usd'],
                    'price_eth': token_data['price_eth'],
                    'market_cap': token_data['market_cap'],
                    'liquidity_usd': token_data['liquidity_usd'],
                    'volume_24h': token_data['volume_24h'],
                    'price_change_24h': token_data['price_change_24h'],
                    'price_change_6h': token_data['price_change_6h'],
                    'price_change_1h': token_data['price_change_1h'],
                    'buys_24h': token_data['buys_24h'],
                    'sells_24h': token_data['sells_24h'],
                    'holder_count': holder_count,
                    'holder_change_24h': holder_change_pct
                },
                'strategy': {
                    'nft_holdings': nft_holdings,
                    'burned_tokens': burn_data['burned_tokens'],
                    'burn_percent': burn_data['burn_percent']
                }
            }
            return jsonify(response_data)
        else:
            return jsonify({
                'error': 'Unable to fetch GUSTR data',
                'timestamp': datetime.now().isoformat()
            }), 500

    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected'
    })

@app.route('/api/export-pdf')
def export_pdf():
    """Export current dashboard data as PDF"""
    try:
        # Get current data
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    analytics_date, eth_price_usd, origins_floor_eth, origins_supply,
                    origins_market_cap_usd, undead_floor_eth, undead_supply,
                    undead_market_cap_usd, total_migrations, migration_percent,
                    price_ratio, combined_market_cap_usd
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'No data available'}), 404
            
            # Get real volume data
            try:
                origins_vol, undead_vol = get_quick_volume_data()
            except:
                origins_vol, undead_vol = 0.09, 0.49
                
            # Format data for PDF
            pdf_data = {
                'eth_price_usd': row['eth_price_usd'],
                'origins': {
                    'floor_price_eth': row['origins_floor_eth'],
                    'floor_price_usd': row['origins_floor_eth'] * row['eth_price_usd'],
                    'volume_24h_eth': origins_vol,
                    'market_cap_usd': row['origins_market_cap_usd'],
                    'total_supply': row['origins_supply']
                },
                'undead': {
                    'floor_price_eth': row['undead_floor_eth'],
                    'floor_price_usd': row['undead_floor_eth'] * row['eth_price_usd'],
                    'volume_24h_eth': undead_vol,
                    'market_cap_usd': row['undead_market_cap_usd'],
                    'total_supply': row['undead_supply']
                },
                'migration_analytics': {
                    'migration_rate': {
                        'total_migrations': row['total_migrations'],
                        'migration_percent': row['migration_percent'],
                        'price_ratio': row['price_ratio']
                    }
                },
                'ecosystem_value': row['combined_market_cap_usd']
            }
            
        # Generate PDF
        from pdf_generator import PDFReportGenerator
        generator = PDFReportGenerator()
        pdf_buffer = generator.generate_pdf(pdf_data)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'GU_Migration_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fix-data')
def fix_data():
    """Fix incorrect historical data"""
    try:
        with db.get_connection() as conn:
            # Fix the incorrect 24h changes
            conn.execute("""
                UPDATE daily_analytics 
                SET origins_floor_change_24h = 0.0,
                    undead_floor_change_24h = 0.0
                WHERE analytics_date >= '2025-09-01'
                  AND (origins_floor_change_24h != 0.0 OR undead_floor_change_24h != 0.0)
            """)
            
            conn.commit()
            
            return jsonify({
                'status': 'success',
                'message': '24h changes corrected to 0%',
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)