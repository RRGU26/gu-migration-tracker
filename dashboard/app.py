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
    """Manages data for the dashboard using stored analytics"""
    
    def __init__(self):
        # Use the correct database path (one level up from dashboard/)
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gu_migration.db')
        self.db = DatabaseManager(db_path)
        self.opensea_client = OpenSeaClient()
        self.last_update = None
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        
        # Import the analytics service
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from src.services.daily_analytics_service import DailyAnalyticsService
        # Pass the same database path to the analytics service
        self.analytics_service = DailyAnalyticsService(db_path)
        
        import logging
        self.logger = logging.getLogger(__name__)
    
    def get_stored_analytics_data(self):
        """Get data from stored analytics instead of live API calls"""
        try:
            # Get latest analytics from database
            analytics = self.analytics_service.get_latest_analytics()
            
            if not analytics:
                self.logger.warning("No stored analytics found, using fallback data")
                return self._get_fallback_data()
            
            # Format data for dashboard/PDF consumption
            return {
                'eth_price_usd': analytics['eth_price_usd'],
                'origins': {
                    'floor_price_eth': analytics['origins_floor_eth'],
                    'total_supply': analytics['origins_supply'],
                    'market_cap_usd': analytics['origins_market_cap_usd'],
                    'floor_change_24h': analytics['origins_floor_change_24h'],
                    'volume_24h_eth': 0  # Will be enhanced with live data
                },
                'undead': {
                    'floor_price_eth': analytics['undead_floor_eth'],
                    'total_supply': analytics['undead_supply'],
                    'market_cap_usd': analytics['undead_market_cap_usd'],
                    'floor_change_24h': analytics['undead_floor_change_24h'],
                    'volume_24h_eth': 0  # Will be enhanced with live data
                },
                'migration_analytics': {
                    'migration_rate': {
                        'total_migrations': analytics['total_migrations'],
                        'migration_percent': analytics['migration_percent'],
                        'price_ratio': analytics['price_ratio']
                    }
                },
                'ecosystem_value': analytics['combined_market_cap_usd'],
                'last_updated': analytics['analytics_date']
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stored analytics: {e}")
            return self._get_fallback_data()
    
    def _get_fallback_data(self):
        """Fallback data when analytics aren't available"""
        return {
            'eth_price_usd': 4500,
            'origins': {
                'floor_price_eth': 0.066749,
                'total_supply': 5341616,
                'market_cap_usd': 2015000000,
                'floor_change_24h': -2.5,
                'volume_24h_eth': 1.32
            },
            'undead': {
                'floor_price_eth': 0.055497,
                'total_supply': 6000,
                'market_cap_usd': 1499000,
                'floor_change_24h': 1.2,
                'volume_24h_eth': 1.37
            },
            'migration_analytics': {
                'migration_rate': {
                    'total_migrations': 26,
                    'migration_percent': 0.43,
                    'price_ratio': 0.831
                }
            },
            'ecosystem_value': 2016499000,
            'last_updated': '2025-08-31'
        }

    def _get_24h_floor_change(self, collection_slug, current_floor_price):
        """Calculate 24h floor price change from stored analytics"""
        try:
            # Get the latest analytics which already has calculated 24h changes
            with self.db.get_connection() as conn:
                # Map collection slug to the appropriate change field
                if collection_slug == 'gu-origins':
                    cursor = conn.execute("""
                        SELECT origins_floor_change_24h 
                        FROM daily_analytics 
                        ORDER BY analytics_date DESC 
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    if result and result[0] is not None:
                        return result[0]
                        
                elif collection_slug == 'genuine-undead':
                    cursor = conn.execute("""
                        SELECT undead_floor_change_24h 
                        FROM daily_analytics 
                        ORDER BY analytics_date DESC 
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    if result and result[0] is not None:
                        return result[0]
            
            # Fallback: Calculate manually if not in analytics
            collection_id = self.db.get_collection_id(collection_slug)
            if not collection_id:
                return 0.0
            
            # Get floor price from 24 hours ago
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            
            # Query database for floor price from yesterday
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT floor_price_eth FROM daily_snapshots WHERE collection_id = ? AND snapshot_date = ?",
                    (collection_id, yesterday_str)
                )
                result = cursor.fetchone()
            
            if result and result[0] and result[0] > 0:
                yesterday_floor = result[0]
                # Calculate percentage change
                change_percent = ((current_floor_price - yesterday_floor) / yesterday_floor) * 100
                return change_percent
            else:
                # If no data from exactly 24h ago, try to get the most recent data within last 3 days
                cursor.execute(
                    "SELECT floor_price_eth FROM daily_snapshots WHERE collection_id = ? AND snapshot_date >= ? ORDER BY snapshot_date DESC LIMIT 1",
                    (collection_id, (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'))
                )
                result = cursor.fetchone()
                
                if result and result[0] and result[0] > 0:
                    prev_floor = result[0]
                    change_percent = ((current_floor_price - prev_floor) / prev_floor) * 100
                    return change_percent
                
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating 24h floor change: {e}")
            return 0.0
    
    def _get_market_cap_chart_data(self):
        """Get market cap data for yesterday and today for PDF charts"""
        try:
            # Get yesterday and today data
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            start_date = yesterday - timedelta(days=2)  # Get a few extra days for context
            
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT ds.snapshot_date, c.slug, ds.floor_price_eth, ds.total_supply
                    FROM daily_snapshots ds
                    JOIN collections c ON ds.collection_id = c.id
                    WHERE ds.snapshot_date >= ? AND ds.snapshot_date <= ?
                    ORDER BY ds.snapshot_date, c.slug
                """, (start_date.isoformat(), today.isoformat()))
                
                rows = cursor.fetchall()
                
                # Organize data by date and collection
                dates = []
                origins_mc = []
                undead_mc = []
                
                current_eth_price = 4500  # Default, could be fetched from API
                
                # Group by date
                from collections import defaultdict
                by_date = defaultdict(dict)
                
                for row in rows:
                    date_str = row['snapshot_date']
                    slug = row['slug']
                    floor_eth = row['floor_price_eth']
                    supply = row['total_supply']
                    
                    market_cap_usd = floor_eth * supply * current_eth_price
                    by_date[date_str][slug] = market_cap_usd
                
                # Convert to arrays for plotting
                sorted_dates = sorted(by_date.keys())
                for date_str in sorted_dates:
                    dates.append(date_str)
                    origins_mc.append(by_date[date_str].get('gu-origins', 0))
                    undead_mc.append(by_date[date_str].get('genuine-undead', 0))
                
                return {
                    'dates': dates,
                    'origins_market_cap': origins_mc,
                    'undead_market_cap': undead_mc
                }
                
        except Exception as e:
            self.logger.error(f"Error getting market cap chart data: {e}")
            return {}
    
    def _get_migration_chart_data(self):
        """Get migration data based on OpenSea supply changes for PDF charts"""
        try:
            # Get recent snapshot data to track supply changes
            today = datetime.now().date()
            start_date = today - timedelta(days=5)  # Get 5 days for context
            
            with self.db.get_connection() as conn:
                # Get Genuine Undead supply changes (increases indicate migrations)
                cursor = conn.execute("""
                    SELECT snapshot_date, total_supply
                    FROM daily_snapshots ds
                    JOIN collections c ON ds.collection_id = c.id
                    WHERE c.slug = 'genuine-undead' 
                    AND snapshot_date >= ? AND snapshot_date <= ?
                    ORDER BY snapshot_date
                """, (start_date.isoformat(), today.isoformat()))
                
                rows = cursor.fetchall()
                
                dates = []
                daily_migrations = []
                cumulative_migrations = []
                
                previous_supply = None
                base_supply = 26  # Start with the 26 burned GU
                
                for row in rows:
                    current_supply = row['total_supply']
                    date_str = row['snapshot_date']
                    
                    if previous_supply is not None:
                        # Daily migration = increase in Genuine Undead supply
                        daily_change = current_supply - previous_supply
                        daily_migrations.append(max(0, daily_change))  # Only positive changes
                    else:
                        # First day, use base supply difference
                        daily_migrations.append(max(0, current_supply - base_supply))
                    
                    dates.append(date_str)
                    # Cumulative = current Genuine Undead supply (represents total migrations)
                    cumulative_migrations.append(current_supply)
                    previous_supply = current_supply
                
                # If we have no data, return sample data
                if not dates:
                    dates = ['2025-08-30', '2025-08-31', '2025-09-01']
                    daily_migrations = [26, 15, 8]  # Start with 26 burned, then daily increases
                    cumulative_migrations = [26, 41, 49]
                
                # Fill in missing dates with zeros if needed
                all_dates = []
                current_date = start_date
                while current_date <= today:
                    all_dates.append(current_date.isoformat())
                    current_date += timedelta(days=1)
                
                return {
                    'dates': dates,
                    'daily_migrations': daily_migrations,
                    'cumulative_migrations': cumulative_migrations
                }
                
        except Exception as e:
            self.logger.error(f"Error getting migration chart data: {e}")
            # Return sample data on error
            return {
                'dates': ['2025-08-30', '2025-08-31', '2025-09-01'],
                'daily_migrations': [26, 15, 8],
                'cumulative_migrations': [26, 41, 49]
            }
    
    def _get_market_cap_chart_from_analytics(self):
        """Get market cap chart data from stored daily analytics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT analytics_date, origins_market_cap_usd, undead_market_cap_usd, eth_price_usd
                    FROM daily_analytics 
                    WHERE analytics_date >= date('now', '-7 days')
                    ORDER BY analytics_date
                """)
                rows = cursor.fetchall()
                
                if rows:
                    dates = []
                    origins_mc = []
                    undead_mc = []
                    
                    for row in rows:
                        dates.append(row['analytics_date'])
                        origins_mc.append(row['origins_market_cap_usd'] or 0)
                        undead_mc.append(row['undead_market_cap_usd'] or 0)
                    
                    return {
                        'dates': dates,
                        'origins_market_cap': origins_mc,
                        'undead_market_cap': undead_mc
                    }
                
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting market cap chart from analytics: {e}")
            return {}
    
    def _get_migration_chart_from_analytics(self):
        """Get migration chart data from stored daily analytics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT analytics_date, daily_new_migrations, total_migrations
                    FROM daily_analytics 
                    WHERE analytics_date >= date('now', '-7 days')
                    ORDER BY analytics_date
                """)
                rows = cursor.fetchall()
                
                if rows:
                    dates = []
                    daily_migrations = []
                    cumulative_migrations = []
                    
                    for row in rows:
                        dates.append(row['analytics_date'])
                        daily_migrations.append(row['daily_new_migrations'] or 0)
                        cumulative_migrations.append(row['total_migrations'] or 26)
                    
                    return {
                        'dates': dates,
                        'daily_migrations': daily_migrations,
                        'cumulative_migrations': cumulative_migrations
                    }
                
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting migration chart from analytics: {e}")
            return {}
    
    async def get_current_data(self, force_refresh=False):
        """Get current market data - prefer database over live API due to rate limits"""
        now = datetime.now()
        
        # Check cache
        if (not force_refresh and 
            self.last_update and 
            (now - self.last_update).seconds < self.cache_duration and
            self.cache):
            return self.cache
        
        # First, try to get data from stored analytics (more reliable)
        stored_data = self.get_stored_analytics_data()
        
        if stored_data and stored_data.get('eth_price_usd'):
            # Use stored data from database
            data = {
                'timestamp': now.isoformat(),
                'eth_price_usd': stored_data['eth_price_usd'],
                'origins': stored_data['origins'],
                'undead': stored_data['undead'],
                'migration_analytics': stored_data['migration_analytics']
            }
            
            # Update cache
            self.cache = data
            self.last_update = now
            return data
        
        # Fallback to live API (often rate limited)
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
            
            # Calculate migrations from real-time OpenSea data
            # Use actual Genuine Undead total supply from OpenSea
            undead_supply = undead_details.get('total_supply', 5037) if undead_details else 5037
            
            # CORRECTED: Add 26 burned GU to total migrations
            total_migrations = undead_supply + 26
            
            # CORRECTED: Migration percentage = (Undead Supply / 9,993 Origins) × 100
            migration_percent = (undead_supply / 9993) * 100
            
            # Calculate price ratio
            origins_floor = origins_stats.get('floor_price', 0.0575) if origins_stats else 0.0575
            undead_floor = undead_stats.get('floor_price', 0.0383) if undead_stats else 0.0383
            price_ratio = undead_floor / origins_floor if origins_floor > 0 else 0.666
            
            # Process data
            data = {
                'timestamp': now.isoformat(),
                'eth_price_usd': eth_price,
                'origins': self._process_collection_data(origins_stats, origins_details, eth_price, 'gu-origins'),
                'undead': self._process_collection_data(undead_stats, undead_details, eth_price, 'genuine-undead'),
                'migration_analytics': {
                    'migration_rate': {
                        'total_migrations': total_migrations,  # Includes 26 burned
                        'migration_percent': migration_percent,  # Corrected formula
                        'price_ratio': price_ratio
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
    
    def _process_collection_data(self, stats, details, eth_price, collection_slug):
        """Process collection data into dashboard format"""
        if not stats or not details:
            return None
        
        total_supply = details.get('total_supply', 10000)
        floor_price_eth = stats.get('floor_price', 0)
        volume_24h_eth = stats.get('one_day_volume', 0)
        volume_7d_eth = stats.get('seven_day_volume', 0)
        
        # Calculate 24h floor price change from database
        floor_change_24h = self._get_24h_floor_change(collection_slug, floor_price_eth)
        
        return {
            'name': details.get('name', 'Unknown'),
            'total_supply': total_supply,
            'holders_count': stats.get('num_owners', 0),
            'floor_price_eth': floor_price_eth,
            'floor_price_usd': floor_price_eth * eth_price,
            'floor_change_24h': floor_change_24h,
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
        
        # Calculate 24h changes (includes manual test data)
        origins_change = self._get_24h_floor_change('gu-origins', 0.0667)
        undead_change = self._get_24h_floor_change('genuine-undead', 0.0383)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'eth_price_usd': eth_price,
            'origins': {
                'name': 'GU Origins',
                'total_supply': 9992,
                'holders_count': 2040,
                'floor_price_eth': 0.0667,
                'floor_price_usd': 0.0667 * eth_price,
                'floor_change_24h': origins_change,  # Real 24h floor change from database
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
                'floor_change_24h': undead_change,  # Real 24h floor change from database
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
    
    # Create price comparison chart - handles empty data gracefully
    if historical['origins_history'] or historical['undead_history']:
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
                'title': 'Floor Price Trends - Building History',
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
    else:
        # Empty state for new tracking
        price_chart = {
            'data': [],
            'layout': {
                'title': 'Floor Price Trends - Data Collection Starting',
                'xaxis': {'title': 'Date', 'showgrid': True, 'gridcolor': 'rgba(128,128,128,0.2)'},
                'yaxis': {'title': 'Floor Price (ETH)', 'showgrid': True, 'gridcolor': 'rgba(128,128,128,0.2)'},
                'plot_bgcolor': 'rgba(0,0,0,0)',
                'paper_bgcolor': 'rgba(0,0,0,0)',
                'annotations': [{
                    'text': 'Historical data will appear as daily snapshots are collected',
                    'x': 0.5,
                    'y': 0.5,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 14, 'color': 'gray'}
                }]
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
                'legend': {
                    'x': 0.02,
                    'y': 0.98,
                    'bgcolor': 'rgba(255,255,255,0.9)',
                    'bordercolor': 'rgba(128,128,128,0.3)',
                    'borderwidth': 1,
                    'font': {'size': 12},
                    'orientation': 'v',
                    'xanchor': 'left',
                    'yanchor': 'top'
                },
                'margin': {'l': 80, 'r': 80, 't': 80, 'b': 80},
                'annotations': [{
                    'text': f'Total migrations in 30 days: {total:,}',
                    'x': 0.5,
                    'y': 1.15,
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

@app.route('/api/fix-data')
def fix_data():
    """Fix historical price data"""
    try:
        with dashboard_data.db.get_connection() as conn:
            # Fix Aug 31 - Genuine Undead was ~0.03 ETH, not 0.0555
            conn.execute("""
                UPDATE daily_analytics 
                SET undead_floor_eth = 0.0300,
                    origins_floor_eth = 0.0575,
                    undead_floor_change_24h = 0,
                    origins_floor_change_24h = 0
                WHERE analytics_date = '2025-08-31'
            """)
            
            # Fix Sep 1 - Undead increased to 0.0383 (27.7% gain)
            conn.execute("""
                UPDATE daily_analytics 
                SET undead_floor_eth = 0.0383,
                    origins_floor_eth = 0.0575,
                    origins_floor_change_24h = 0.0,
                    undead_floor_change_24h = 27.67
                WHERE analytics_date = '2025-09-01'  
            """)
            
            # Fix Sep 2 and 3 - Prices stable (0% change)
            conn.execute("""
                UPDATE daily_analytics 
                SET origins_floor_change_24h = 0.0,
                    undead_floor_change_24h = 0.0
                WHERE analytics_date IN ('2025-09-02', '2025-09-03')
            """)
            
            conn.commit()
            
            # Clear cache to force refresh
            dashboard_data.cache = {}
            dashboard_data.last_update = None
            
            return jsonify({
                'status': 'success', 
                'message': 'Historical data corrected',
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/export-pdf')
def export_pdf():
    """Generate and return a PDF report using stored analytics"""
    try:
        # Import Flask response tools
        from flask import make_response
        
        # Get data from stored analytics (no API calls needed)
        data = dashboard_data.get_stored_analytics_data()
        
        # Import PDF generator
        from pdf_generator import PDFReportGenerator
        
        # Prepare data for PDF with proper error handling
        migration = data.get('migration_analytics', {}).get('migration_rate', {})
        origins = data.get('origins', {})
        undead = data.get('undead', {})
        
        # Calculate price ratio safely
        origins_floor = origins.get('floor_price_eth', 0)
        undead_floor = undead.get('floor_price_eth', 0)
        price_ratio = undead_floor / origins_floor if origins_floor > 0 else 1.0
        
        # Get chart data from stored analytics (much more reliable)
        market_cap_chart = dashboard_data._get_market_cap_chart_from_analytics()
        migration_chart = dashboard_data._get_migration_chart_from_analytics()
        
        # Ensure we always have chart data (use current values if no trend data)
        if not market_cap_chart.get('dates'):
            market_cap_chart = {
                'dates': [data.get('last_updated', '2025-08-31')],
                'origins_market_cap': [origins.get('market_cap_usd', 0)],
                'undead_market_cap': [undead.get('market_cap_usd', 0)]
            }
        
        if not migration_chart.get('dates'):
            migration_chart = {
                'dates': [data.get('last_updated', '2025-08-31')],
                'daily_migrations': [migration.get('total_migrations', 26)],
                'cumulative_migrations': [migration.get('total_migrations', 26)]
            }
        
        pdf_data = {
            'total_migrations': migration.get('total_migrations', 0),
            'migration_percent': migration.get('migration_percent', 0),
            'price_ratio': price_ratio,
            'ecosystem_value': (origins.get('market_cap_usd', 0) + undead.get('market_cap_usd', 0)),
            'origins': origins,
            'undead': undead,
            'eth_price': data.get('eth_price_usd', 0),
            'market_cap_chart': market_cap_chart,
            'migration_chart': migration_chart
        }
        
        # Generate PDF
        generator = PDFReportGenerator()
        pdf_buffer = generator.generate_compact_report(pdf_data)
        
        # Create response
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="RR_GU_Analytics_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
        
        return response
        
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"PDF export failed: {str(e)}")
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)