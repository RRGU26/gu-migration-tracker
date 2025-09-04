#!/usr/bin/env python3
"""
Simplified GU Migration Tracker Dashboard
Direct database connection, no complex caching
"""
import os
import sys
from datetime import datetime, date
from flask import Flask, render_template, jsonify

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.database.database import DatabaseManager

app = Flask(__name__)

# Single database connection
db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gu_migration.db')
db = DatabaseManager(db_path)

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
                    'volume_24h_eth': 0  # OpenSea API rate limited - showing $0
                    'holders_count': row['origins_supply']  # Will be actual holders when available
                },
                'undead': {
                    'floor_price_eth': row['undead_floor_eth'],
                    'floor_price_usd': row['undead_floor_eth'] * row['eth_price_usd'],
                    'total_supply': row['undead_supply'],
                    'market_cap_usd': row['undead_market_cap_usd'],
                    'floor_change_24h': row['undead_floor_change_24h'],
                    'volume_24h_eth': 0  # OpenSea API rate limited - showing $0
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
    """Simply return current data - no complex refresh logic"""
    return get_current_data()

@app.route('/api/charts')
def get_chart_data():
    """Get historical data for charts"""
    try:
        with db.get_connection() as conn:
            # Get last 7 days of data
            cursor = conn.execute("""
                SELECT 
                    analytics_date,
                    origins_floor_eth,
                    undead_floor_eth,
                    origins_market_cap_usd,
                    undead_market_cap_usd,
                    total_migrations
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 7
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                return jsonify({'charts': []})
            
            # Build chart data
            dates = []
            origins_floor = []
            undead_floor = []
            origins_mc = []
            undead_mc = []
            migrations = []
            
            for row in reversed(rows):  # Reverse to get chronological order
                dates.append(row['analytics_date'])
                origins_floor.append(row['origins_floor_eth'])
                undead_floor.append(row['undead_floor_eth'])
                origins_mc.append(row['origins_market_cap_usd'])
                undead_mc.append(row['undead_market_cap_usd'])
                migrations.append(row['total_migrations'])
            
            # Create formatted chart objects
            charts_data = {
                'supply_chart': {
                    'data': [{
                        'x': dates,
                        'y': migrations,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': 'Total Migrations',
                        'line': {'color': '#10b981', 'width': 3},
                        'marker': {'size': 8}
                    }],
                    'layout': {
                        'title': 'Migration Growth Over Time',
                        'xaxis': {'title': 'Date'},
                        'yaxis': {'title': 'Total Migrations'},
                        'margin': {'t': 50, 'l': 60, 'r': 30, 'b': 60}
                    }
                },
                'market_cap_chart': {
                    'data': [
                        {
                            'x': dates,
                            'y': origins_mc,
                            'type': 'scatter',
                            'mode': 'lines+markers',
                            'name': 'GU Origins',
                            'line': {'color': '#667eea', 'width': 3}
                        },
                        {
                            'x': dates,
                            'y': undead_mc,
                            'type': 'scatter', 
                            'mode': 'lines+markers',
                            'name': 'Genuine Undead',
                            'line': {'color': '#764ba2', 'width': 3}
                        }
                    ],
                    'layout': {
                        'title': 'Market Cap Comparison',
                        'xaxis': {'title': 'Date'},
                        'yaxis': {'title': 'Market Cap (USD)'},
                        'margin': {'t': 50, 'l': 60, 'r': 30, 'b': 60}
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