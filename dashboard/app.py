#!/usr/bin/env python3
"""
GU Migration Tracker - Live Web Dashboard
"""
import os
import sys
import asyncio
import json
from datetime import datetime, date, timedelta
from flask import Flask, render_template, jsonify, request
import plotly.graph_objs as go
import plotly.utils

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.database.database import DatabaseManager
from src.api.opensea_client import OpenSeaClient
from src.api.price_client import get_current_eth_price
from src.utils.migration_detector import get_migration_analytics

app = Flask(__name__)

class DashboardData:
    """Manages data for the dashboard"""
    
    def __init__(self):
        # Use the correct database path (one level up from dashboard/)
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gu_migration.db')
        self.db = DatabaseManager(db_path)
        self.opensea_client = OpenSeaClient()
        self.last_update = None
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        
        import logging
        self.logger = logging.getLogger(__name__)
    
    async def get_current_data(self, force_refresh=False):
        """Get current market data with caching"""
        now = datetime.now()
        
        # Check cache
        if (not force_refresh and 
            self.last_update and 
            (now - self.last_update).seconds < self.cache_duration and
            self.cache):
            return self.cache
        
        try:
            # Fetch real-time data
            origins_stats = await self.opensea_client.get_collection_stats('gu-origins')
            await asyncio.sleep(1)
            undead_stats = await self.opensea_client.get_collection_stats('genuine-undead')
            await asyncio.sleep(1)
            
            origins_details = await self.opensea_client.get_collection_details('gu-origins')
            await asyncio.sleep(1)
            undead_details = await self.opensea_client.get_collection_details('genuine-undead')
            
            eth_price = await get_current_eth_price()
            
            # Get accurate migration data from database
            migration_stats = self.db.get_migration_stats(30)
            
            # Calculate migrations from real-time OpenSea data
            # Use actual Genuine Undead total supply from OpenSea
            total_migrations = undead_details.get('total_supply', 0) if undead_details else 0
            
            # Migration percentage = (OpenSea GU Supply / 10,000 Origins) × 100
            migration_percent = (total_migrations / 10000) * 100
            
            # Process data
            data = {
                'timestamp': now.isoformat(),
                'eth_price_usd': eth_price,
                'origins': self._process_collection_data(origins_stats, origins_details, eth_price),
                'undead': self._process_collection_data(undead_stats, undead_details, eth_price),
                'migration_analytics': {
                    'migration_rate': {
                        'total_migrations': total_migrations,  # Use calculated migrations from supply
                        'migration_percent': migration_percent
                    }
                }
            }
            
            # Update cache
            self.cache = data
            self.last_update = now
            
            return data
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            # Return cached data if available
            if self.cache:
                return self.cache
            # Return mock data if no cache
            return self._get_mock_data()
    
    def _process_collection_data(self, stats, details, eth_price):
        """Process collection data into dashboard format"""
        if not stats or not details:
            return None
        
        total_supply = details.get('total_supply', 10000)
        floor_price_eth = stats.get('floor_price', 0)
        volume_24h_eth = stats.get('one_day_volume', 0)
        volume_7d_eth = stats.get('seven_day_volume', 0)
        
        return {
            'name': details.get('name', 'Unknown'),
            'total_supply': total_supply,
            'holders_count': stats.get('num_owners', 0),
            'floor_price_eth': floor_price_eth,
            'floor_price_usd': floor_price_eth * eth_price,
            'volume_24h_eth': volume_24h_eth,
            'volume_24h_usd': volume_24h_eth * eth_price,
            'volume_7d_eth': volume_7d_eth,
            'volume_7d_usd': volume_7d_eth * eth_price,
            'market_cap_eth': floor_price_eth * total_supply,
            'market_cap_usd': floor_price_eth * total_supply * eth_price,
            'average_price_eth': stats.get('average_price', 0),
            'total_sales': stats.get('num_sales', 0)
        }
    
    def _get_mock_data(self):
        """Return mock data when API is unavailable"""
        eth_price = 4500
        return {
            'timestamp': datetime.now().isoformat(),
            'eth_price_usd': eth_price,
            'origins': {
                'name': 'GU Origins',
                'total_supply': 9992,
                'holders_count': 2040,
                'floor_price_eth': 0.0667,
                'floor_price_usd': 0.0667 * eth_price,
                'volume_24h_eth': 1.32,
                'volume_24h_usd': 1.32 * eth_price,
                'volume_7d_eth': 6.36,
                'volume_7d_usd': 6.36 * eth_price,
                'market_cap_eth': 0.0667 * 9992,
                'market_cap_usd': 0.0667 * 9992 * eth_price,
                'average_price_eth': 0.216,
                'total_sales': 69135
            },
            'undead': {
                'name': 'Genuine Undead',
                'total_supply': 5306,
                'holders_count': 692,
                'floor_price_eth': 0.0383,
                'floor_price_usd': 0.0383 * eth_price,
                'volume_24h_eth': 0.988,
                'volume_24h_usd': 0.988 * eth_price,
                'volume_7d_eth': 2.37,
                'volume_7d_usd': 2.37 * eth_price,
                'market_cap_eth': 0.0383 * 5306,
                'market_cap_usd': 0.0383 * 5306 * eth_price,
                'average_price_eth': 0.045,
                'total_sales': 1234
            },
            'migration_analytics': {'migration_rate': {'total_migrations': 0}}
        }
    
    def get_historical_chart_data(self):
        """Get historical data for charts"""
        try:
            origins_id = self.db.get_collection_id('gu-origins')
            undead_id = self.db.get_collection_id('genuine-undead')
            
            origins_history = self.db.get_historical_snapshots(origins_id, 30)
            undead_history = self.db.get_historical_snapshots(undead_id, 30)
            migration_stats = self.db.get_migration_stats(30)
            
            
            return {
                'origins_history': origins_history,
                'undead_history': undead_history,
                'migration_stats': migration_stats
            }
        except Exception as e:
            self.logger.error(f"Error in get_historical_chart_data: {e}")
            return {'origins_history': [], 'undead_history': [], 'migration_stats': {}}

# Global dashboard data instance
dashboard_data = DashboardData()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/current')
def api_current():
    """API endpoint for current market data"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        data = loop.run_until_complete(dashboard_data.get_current_data())
        return jsonify(data)
    finally:
        loop.close()

@app.route('/api/refresh')
def api_refresh():
    """API endpoint to force data refresh"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        data = loop.run_until_complete(dashboard_data.get_current_data(force_refresh=True))
        return jsonify(data)
    finally:
        loop.close()

@app.route('/api/charts')
def api_charts():
    """API endpoint for chart data"""
    historical = dashboard_data.get_historical_chart_data()
    
    # Create price comparison chart
    price_chart = {
        'data': [
            {
                'x': [h['snapshot_date'] for h in historical['origins_history']],
                'y': [h['floor_price_eth'] for h in historical['origins_history']],
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'GU Origins',
                'line': {'color': '#ff6b6b', 'width': 3}
            },
            {
                'x': [h['snapshot_date'] for h in historical['undead_history']],
                'y': [h['floor_price_eth'] for h in historical['undead_history']],
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Genuine Undead',
                'line': {'color': '#4ecdc4', 'width': 3}
            }
        ],
        'layout': {
            'title': 'Floor Price Trends - Last 30 Days',
            'xaxis': {'title': 'Date', 'showgrid': True, 'gridcolor': 'rgba(128,128,128,0.2)'},
            'yaxis': {'title': 'Floor Price (ETH)', 'showgrid': True, 'gridcolor': 'rgba(128,128,128,0.2)'},
            'hovermode': 'x unified',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'legend': {
                'x': 0,
                'y': 1,
                'bgcolor': 'rgba(255,255,255,0.8)',
                'bordercolor': 'rgba(0,0,0,0.2)',
                'borderwidth': 1
            }
        }
    }
    
    # Create volume chart
    volume_chart = {
        'data': [
            {
                'x': [h['snapshot_date'] for h in historical['origins_history']],
                'y': [h['volume_24h_eth'] for h in historical['origins_history']],
                'type': 'bar',
                'name': 'GU Origins',
                'marker': {'color': '#ff6b6b', 'opacity': 0.7}
            },
            {
                'x': [h['snapshot_date'] for h in historical['undead_history']],
                'y': [h['volume_24h_eth'] for h in historical['undead_history']],
                'type': 'bar',
                'name': 'Genuine Undead',
                'marker': {'color': '#4ecdc4', 'opacity': 0.7}
            }
        ],
        'layout': {
            'title': '24h Volume Comparison',
            'xaxis': {'title': 'Date'},
            'yaxis': {'title': '24h Volume (ETH)'},
            'barmode': 'group',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'paper_bgcolor': 'rgba(0,0,0,0)'
        }
    }
    
    # Genuine Undead Supply Growth Chart with optimal scaling
    if historical['undead_history']:
        supply_values = [h.get('total_supply', 0) for h in historical['undead_history']]
        if supply_values:
            min_supply = min(supply_values)
            max_supply = max(supply_values)
            range_supply = max_supply - min_supply
            
            # Calculate optimal Y-axis range for better visibility
            if range_supply < max_supply * 0.1:  # Less than 10% change
                # Zoom in to show small changes
                padding = max(range_supply * 0.1, 50)  # At least 50 unit padding
                y_min = max(0, min_supply - padding)
                y_max = max_supply + padding
            else:
                # Normal scaling with padding
                padding = range_supply * 0.05
                y_min = max(0, min_supply - padding)
                y_max = max_supply + padding
        else:
            y_min, y_max = 0, 10000
        
        supply_chart = {
            'data': [{
                'x': [h['snapshot_date'] for h in historical['undead_history']],
                'y': supply_values,
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Collection Supply',
                'line': {'color': '#10b981', 'width': 4},
                'marker': {'size': 6},
                'fill': 'tonexty',
                'fillcolor': 'rgba(16, 185, 129, 0.1)',
                'hovertemplate': '<b>%{y:,}</b> NFTs<br>Date: %{x}<extra></extra>'
            }],
            'layout': {
                'title': 'Genuine Undead Collection Growth - Last 30 Days',
                'xaxis': {'title': 'Date', 'showgrid': True, 'gridcolor': 'rgba(128,128,128,0.2)'},
                'yaxis': {
                    'title': 'Total Supply', 
                    'range': [y_min, y_max],
                    'showgrid': True, 
                    'gridcolor': 'rgba(128,128,128,0.2)',
                    'tickformat': ',.0f'
                },
                'hovermode': 'x unified',
                'plot_bgcolor': 'rgba(0,0,0,0)',
                'paper_bgcolor': 'rgba(0,0,0,0)',
                'annotations': [{
                    'text': f'Growth: +{max_supply - min_supply:,} NFTs (organic + migrations)',
                    'x': 0.5,
                    'y': 1.1,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 12, 'color': 'gray'}
                }]
            }
        }
    else:
        supply_chart = {
            'data': [],
            'layout': {
                'title': 'Collection growth data will appear over time',
                'plot_bgcolor': 'rgba(0,0,0,0)',
                'paper_bgcolor': 'rgba(0,0,0,0)',
                'annotations': [{
                    'text': 'No supply data yet',
                    'x': 0.5,
                    'y': 0.5,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False
                }]
            }
        }
    
    # Combined Market Cap Chart (GU Ecosystem Only)
    dates = []
    combined_market_cap = []
    
    if historical['origins_history'] and historical['undead_history']:
        # Calculate combined market cap over time
        for i, date_str in enumerate([h['snapshot_date'] for h in historical['origins_history']]):
            dates.append(date_str)
            
            # Get corresponding data points
            origins_mc = historical['origins_history'][i].get('market_cap_usd', 0) if i < len(historical['origins_history']) else 0
            undead_mc = historical['undead_history'][i].get('market_cap_usd', 0) if i < len(historical['undead_history']) else 0
            
            combined_mc = origins_mc + undead_mc
            combined_market_cap.append(combined_mc)
    
    market_cap_chart = {
        'data': [
            {
                'x': dates,
                'y': combined_market_cap,
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Combined Market Cap',
                'line': {'color': '#8b5cf6', 'width': 4},
                'marker': {'size': 6},
                'fill': 'tonexty',
                'fillcolor': 'rgba(139, 92, 246, 0.1)',
                'hovertemplate': '<b>$%{y:,.0f}</b><br>Date: %{x}<extra></extra>'
            }
        ],
        'layout': {
            'title': 'GU Ecosystem Market Cap - Last 30 Days',
            'xaxis': {
                'title': 'Date', 
                'showgrid': True, 
                'gridcolor': 'rgba(128,128,128,0.2)',
                'tickangle': -45
            },
            'yaxis': {
                'title': 'Market Cap (USD)', 
                'tickformat': '$,.0s',  # Simplified format (1M, 10M, etc.)
                'showgrid': True, 
                'gridcolor': 'rgba(128,128,128,0.2)'
            },
            'hovermode': 'x unified',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'margin': {'l': 80, 'r': 20, 't': 60, 'b': 80},
            'annotations': [{
                'text': 'Origins + Genuine Undead combined valuation',
                'x': 0.5,
                'y': 1.1,
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 12, 'color': 'gray'}
            }]
        }
    }
    
    # Migration chart with corrected cumulative calculation
    migration_breakdown = historical['migration_stats'].get('daily_breakdown', [])
    if migration_breakdown:
        # Sort by date to ensure correct cumulative calculation
        migration_breakdown = sorted(migration_breakdown, key=lambda x: x['migration_date'])
        
        # Calculate cumulative migrations properly
        cumulative_migrations = []
        total = 0
        daily_counts = []
        dates = []
        
        for m in migration_breakdown:
            daily_count = m.get('daily_count', 0)
            total += daily_count
            
            dates.append(m['migration_date'])
            daily_counts.append(daily_count)
            cumulative_migrations.append(total)
        
        
        migration_chart = {
            'data': [
                {
                    'x': dates,
                    'y': daily_counts,
                    'type': 'bar',
                    'name': 'Daily Migrations',
                    'marker': {'color': '#45b7d1', 'opacity': 0.7},
                    'yaxis': 'y',
                    'hovertemplate': '<b>%{y}</b> migrations<br>%{x}<extra></extra>'
                },
                {
                    'x': dates,
                    'y': cumulative_migrations,
                    'type': 'scatter',
                    'mode': 'lines+markers',
                    'name': 'Cumulative Total',
                    'line': {'color': '#dc2626', 'width': 3},
                    'marker': {'size': 6},
                    'yaxis': 'y2',
                    'hovertemplate': '<b>%{y}</b> total migrations<br>%{x}<extra></extra>'
                }
            ],
            'layout': {
                'title': 'Migration Activity - Last 30 Days (Origins → Genuine Undead)',
                'xaxis': {'title': 'Date', 'showgrid': True, 'gridcolor': 'rgba(128,128,128,0.2)'},
                'yaxis': {
                    'title': 'Daily Migrations', 
                    'side': 'left',
                    'showgrid': True,
                    'gridcolor': 'rgba(128,128,128,0.2)'
                },
                'yaxis2': {
                    'title': 'Cumulative Total',
                    'side': 'right',
                    'overlaying': 'y',
                    'showgrid': False,
                    'tickformat': ',.0f'
                },
                'hovermode': 'x unified',
                'plot_bgcolor': 'rgba(0,0,0,0)',
                'paper_bgcolor': 'rgba(0,0,0,0)',
                'annotations': [{
                    'text': f'Total migrations in 30 days: {total:,}',
                    'x': 0.5,
                    'y': 1.1,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 12, 'color': 'gray'}
                }]
            }
        }
    else:
        migration_chart = {
            'data': [],
            'layout': {
                'title': 'Migration tracking will begin after multiple days of data',
                'plot_bgcolor': 'rgba(0,0,0,0)',
                'paper_bgcolor': 'rgba(0,0,0,0)',
                'annotations': [{
                    'text': 'Migration data will appear here<br>once the system runs for several days',
                    'x': 0.5,
                    'y': 0.5,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 14, 'color': 'gray'}
                }]
            }
        }
    
    return jsonify({
        'price_chart': price_chart,
        'volume_chart': volume_chart,
        'supply_chart': supply_chart,
        'market_cap_chart': market_cap_chart,
        'migration_chart': migration_chart
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/export-pdf')
def export_pdf():
    """Generate and return a PDF report"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Get current data
        data = loop.run_until_complete(dashboard_data.get_current_data())
        
        # Import PDF generator
        from pdf_generator import PDFReportGenerator
        from flask import make_response
        
        # Prepare data for PDF
        migration = data.get('migration_analytics', {}).get('migration_rate', {})
        
        pdf_data = {
            'total_migrations': migration.get('total_migrations', 0),
            'migration_percent': migration.get('migration_percent', 0),
            'price_ratio': data['undead']['floor_price_eth'] / data['origins']['floor_price_eth'] if data.get('origins') and data.get('undead') and data['origins']['floor_price_eth'] > 0 else 1,
            'ecosystem_value': (data.get('origins', {}).get('market_cap_usd', 0) + data.get('undead', {}).get('market_cap_usd', 0)),
            'origins': data.get('origins', {}),
            'undead': data.get('undead', {}),
            'eth_price': data.get('eth_price_usd', 0)
        }
        
        # Generate PDF
        generator = PDFReportGenerator()
        pdf_buffer = generator.generate_compact_report(pdf_data)  # Use compact for Twitter
        
        # Create response
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="RR_GU_Analytics_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        loop.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)