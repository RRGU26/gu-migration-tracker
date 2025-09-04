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
    """Get live floor prices and supplies directly from OpenSea API"""
    try:
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        
        # Get Origins floor price and supply
        origins_response = requests.get('https://api.opensea.io/api/v2/collections/gu-origins/stats', 
                                       headers=headers, timeout=5)
        origins_floor = 0.0575  # Fallback
        origins_supply = 9993  # Fallback
        if origins_response.status_code == 200:
            origins_data = origins_response.json()
            origins_floor = float(origins_data.get('total', {}).get('floor_price', 0.0575))
            origins_supply = int(origins_data.get('total', {}).get('supply', 9993))
        
        # Get Undead floor price and supply  
        undead_response = requests.get('https://api.opensea.io/api/v2/collections/genuine-undead/stats',
                                      headers=headers, timeout=5)
        undead_floor = 0.0383  # Fallback
        undead_supply = 5307  # Correct fallback based on contract
        if undead_response.status_code == 200:
            undead_data = undead_response.json()
            undead_floor = float(undead_data.get('total', {}).get('floor_price', 0.0383))
            undead_supply = int(undead_data.get('total', {}).get('supply', 5307))
        
        return origins_floor, undead_floor, origins_supply, undead_supply
        
    except Exception as e:
        print(f"Floor price/supply fetch error: {e}")
        return 0.0575, 0.0383, 9993, 5307

@app.route('/')
def index():
    """Serve the dashboard"""
    return render_template('dashboard.html')

@app.route('/api/current')
def get_current_data():
    """Get current data directly from database - no caching, always fresh"""
    try:
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
            
            # Build response directly from database
            data = {
                'timestamp': datetime.now().isoformat(),
                'analytics_date': row['analytics_date'],
                'eth_price_usd': row['eth_price_usd'],
                'origins': {
                    'floor_price_eth': row['origins_floor_eth'],
                    'floor_price_usd': row['origins_floor_eth'] * row['eth_price_usd'],
                    'total_supply': row['origins_supply'],
                    'market_cap_usd': row['origins_market_cap_usd'],
                    'floor_change_24h': row['origins_floor_change_24h'],
                    'volume_24h_eth': origins_vol,
                    'holders_count': row['origins_supply']  # Will be actual holders when available
                },
                'undead': {
                    'floor_price_eth': row['undead_floor_eth'],
                    'floor_price_usd': row['undead_floor_eth'] * row['eth_price_usd'],
                    'total_supply': row['undead_supply'],
                    'market_cap_usd': row['undead_market_cap_usd'],
                    'floor_change_24h': row['undead_floor_change_24h'],
                    'volume_24h_eth': undead_vol,
                    'holders_count': row['undead_supply']  # Will be actual holders when available
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
            
            return jsonify(data)
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/refresh')
def refresh_data():
    """Get live ETH price and fresh volume data immediately"""
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
                    live_eth_price = 4382  # Final fallback to known current price
        
        # Get live floor prices and supplies
        try:
            origins_floor, undead_floor, origins_supply, undead_supply = get_live_floor_prices_and_supply()
        except:
            origins_floor, undead_floor, origins_supply, undead_supply = 0.0575, 0.0383, 9993, 5307  # Fallback
            
        with db.get_connection() as conn:
            # Update ETH price and floor prices in database
            today = date.today().isoformat()
            conn.execute("""
                UPDATE daily_analytics 
                SET eth_price_usd = ?, origins_floor_eth = ?, undead_floor_eth = ?
                WHERE analytics_date = ?
            """, (live_eth_price, origins_floor, undead_floor, today))
            
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
                
            # Get yesterday's floor prices to calculate real 24h change
            from datetime import timedelta
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            print(f"Fetching yesterday's data for: {yesterday}")
            cursor_yesterday = conn.execute("""
                SELECT origins_floor_eth, undead_floor_eth
                FROM daily_analytics
                WHERE analytics_date = ?
            """, (yesterday,))
            
            yesterday_row = cursor_yesterday.fetchone()
            
            # Calculate 24h changes: compare live prices to yesterday's 9 AM database prices
            origins_change_24h = 0.0
            undead_change_24h = 0.0
            
            if yesterday_row:
                # Use yesterday's database prices as baseline
                yesterday_origins = yesterday_row['origins_floor_eth']
                yesterday_undead = yesterday_row['undead_floor_eth']
                
                # Calculate changes: live prices vs yesterday's 9 AM
                if yesterday_origins > 0:
                    origins_change_24h = ((origins_floor - yesterday_origins) / yesterday_origins) * 100
                if yesterday_undead > 0:
                    undead_change_24h = ((undead_floor - yesterday_undead) / yesterday_undead) * 100
                    
                print(f"Yesterday 9AM: Origins={yesterday_origins}, Undead={yesterday_undead}")
                print(f"Current live: Origins={origins_floor}, Undead={undead_floor}")
                print(f"24h changes: Origins={origins_change_24h:.1f}%, Undead={undead_change_24h:.1f}%")
            else:
                # Fallback to known yesterday values if not in database
                yesterday_origins = 0.0575
                yesterday_undead = 0.0383
                origins_change_24h = ((origins_floor - yesterday_origins) / yesterday_origins) * 100
                undead_change_24h = ((undead_floor - yesterday_undead) / yesterday_undead) * 100
                print("Using fallback yesterday prices")

            # Get fresh volume data
            try:
                origins_vol, undead_vol = get_quick_volume_data()
            except:
                origins_vol, undead_vol = 0.09, 0.49

            # Recalculate market caps with live floor prices, ETH price, and supplies
            origins_mc = origins_floor * live_eth_price * origins_supply
            undead_mc = undead_floor * live_eth_price * undead_supply
            
            # Build response with live data
            data = {
                'timestamp': datetime.now().isoformat(),
                'analytics_date': row['analytics_date'],
                'eth_price_usd': live_eth_price,
                'origins': {
                    'floor_price_eth': origins_floor,
                    'floor_price_usd': origins_floor * live_eth_price,
                    'total_supply': origins_supply,
                    'market_cap_usd': origins_mc,
                    'floor_change_24h': origins_change_24h,
                    'volume_24h_eth': origins_vol,
                    'holders_count': origins_supply
                },
                'undead': {
                    'floor_price_eth': undead_floor,
                    'floor_price_usd': undead_floor * live_eth_price,
                    'total_supply': undead_supply,
                    'market_cap_usd': undead_mc,
                    'floor_change_24h': undead_change_24h,
                    'volume_24h_eth': undead_vol,
                    'holders_count': undead_supply
                },
                'migration_analytics': {
                    'migration_rate': {
                        'total_migrations': undead_supply + 26,  # Current undead supply + 26 burned
                        'migration_percent': ((undead_supply + 26) / origins_supply) * 100,  
                        'price_ratio': undead_floor / origins_floor if origins_floor > 0 else row['price_ratio']
                    }
                },
                'ecosystem_value': origins_mc + undead_mc
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
            
            # Build chart data
            dates = []
            origins_mc = []
            undead_mc = []
            migrations = []
            undead_supply = []
            
            for row in reversed(rows):  # Reverse to get chronological order
                dates.append(row['analytics_date'])
                origins_mc.append(row['origins_market_cap_usd'])
                undead_mc.append(row['undead_market_cap_usd'])
                migrations.append(row['total_migrations'])
                undead_supply.append(row['undead_supply'])
            
            # Create clean, professional charts
            charts_data = {
                'supply_chart': {
                    'data': [{
                        'x': dates,
                        'y': undead_supply,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': 'Undead Collection',
                        'line': {'color': '#10b981', 'width': 3},
                        'marker': {'size': 8, 'color': '#10b981', 'line': {'color': 'white', 'width': 1}},
                        'hovertemplate': '<b>%{y:,}</b> NFTs<br>%{x}<extra></extra>'
                    }],
                    'layout': {
                        'title': {
                            'text': 'Genuine Undead Collection Growth',
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
                            'tickformat': ',.0f',
                            'range': [4900, 5100]
                        },
                        'plot_bgcolor': 'rgba(0,0,0,0)',
                        'paper_bgcolor': 'rgba(0,0,0,0)',
                        'margin': {'t': 50, 'l': 60, 'r': 20, 'b': 40},
                        'showlegend': False,
                        'height': 350
                    }
                },
                'market_cap_chart': {
                    'data': [
                        {
                            'x': dates,
                            'y': origins_mc,
                            'type': 'scatter',
                            'mode': 'lines+markers',
                            'name': 'Origins',
                            'line': {'color': '#667eea', 'width': 3},
                            'marker': {'size': 6, 'color': '#667eea'},
                            'hovertemplate': '<b>$%{y:,.0f}</b><br>GU Origins<br>%{x}<extra></extra>'
                        },
                        {
                            'x': dates,
                            'y': undead_mc,
                            'type': 'scatter', 
                            'mode': 'lines+markers',
                            'name': 'Undead',
                            'line': {'color': '#10b981', 'width': 3},
                            'marker': {'size': 6, 'color': '#10b981'},
                            'hovertemplate': '<b>$%{y:,.0f}</b><br>Genuine Undead<br>%{x}<extra></extra>'
                        }
                    ],
                    'layout': {
                        'title': {
                            'text': 'Market Cap Comparison',
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
                            'tickformat': '$,.0f',
                            'range': [0, 4000000]
                        },
                        'plot_bgcolor': 'rgba(0,0,0,0)',
                        'paper_bgcolor': 'rgba(0,0,0,0)',
                        'margin': {'t': 50, 'l': 80, 'r': 20, 'b': 60},
                        'legend': {
                            'x': 1,
                            'y': 1,
                            'xanchor': 'right',
                            'yanchor': 'top',
                            'bgcolor': 'rgba(255,255,255,0.95)',
                            'bordercolor': '#d1d5db',
                            'borderwidth': 1,
                            'font': {'size': 13, 'family': 'Arial, sans-serif', 'color': '#111827'},
                            'orientation': 'v'
                        },
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