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
                    'listing_percent': (num_listed / undead_supply * 100) if undead_supply > 0 else 0
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