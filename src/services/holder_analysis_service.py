#!/usr/bin/env python3
"""
Holder Analysis Service for GU Migration Tracker
Tracks daily NFT holder behavior, listings, and floor price patterns
"""
import asyncio
import os
import sys
from datetime import date, datetime, timedelta
import logging
import requests
from typing import Dict, List, Tuple, Optional
import json

# Add src and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(src_dir)
sys.path.append(src_dir)
sys.path.append(root_dir)

from database.database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HolderAnalysisService:
    """Service for analyzing NFT holder behavior and listing patterns"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_headers = {'X-API-KEY': os.environ.get('OPENSEA_API_KEY', '')}
        
        # Collection identifiers
        self.collections = {
            'origins': {
                'slug': 'gu-origins',
                'name': 'GU Origins',
                'collection_id': 1
            },
            'undead': {
                'slug': 'genuine-undead', 
                'name': 'Genuine Undead',
                'collection_id': 2
            }
        }
        
        # Create holder analysis tables if they don't exist
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables for holder analysis"""
        with self.db.get_connection() as conn:
            # Table for tracking daily holder counts
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_holder_counts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER,
                    analysis_date DATE,
                    total_holders INTEGER,
                    unique_holders INTEGER,
                    avg_holdings_per_holder REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, analysis_date)
                )
            """)
            
            # Table for tracking listing behavior
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_listing_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER,
                    analysis_date DATE,
                    total_listings INTEGER,
                    floor_listings INTEGER,
                    above_floor_listings INTEGER,
                    avg_listing_price REAL,
                    median_listing_price REAL,
                    whale_listings INTEGER,
                    new_holder_listings INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, analysis_date)
                )
            """)
            
            # Table for tracking specific holder behavior patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS holder_behavior_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER,
                    analysis_date DATE,
                    diamond_hands_count INTEGER,
                    paper_hands_count INTEGER,
                    whale_accumulation INTEGER,
                    new_holders_count INTEGER,
                    holder_churn_rate REAL,
                    avg_hold_time_days REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, analysis_date)
                )
            """)
            
            conn.commit()
            logger.info("Holder analysis database tables initialized")
    
    async def analyze_daily_holders(self, analysis_date: date = None) -> Dict:
        """Run comprehensive daily holder analysis for both collections"""
        if analysis_date is None:
            analysis_date = date.today()
            
        logger.info(f"Starting daily holder analysis for {analysis_date}")
        
        results = {
            'analysis_date': analysis_date.isoformat(),
            'collections': {},
            'summary': {}
        }
        
        try:
            # Analyze each collection
            for key, collection in self.collections.items():
                logger.info(f"Analyzing {collection['name']} holders...")
                
                collection_analysis = await self._analyze_collection_holders(
                    collection['slug'], 
                    collection['collection_id'],
                    analysis_date
                )
                
                results['collections'][key] = collection_analysis
            
            # Generate cross-collection insights
            results['summary'] = self._generate_summary_insights(results['collections'])
            
            # Store results in database
            self._store_holder_analysis(results, analysis_date)
            
            logger.info("Daily holder analysis completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error in daily holder analysis: {e}")
            raise
    
    async def _analyze_collection_holders(self, collection_slug: str, collection_id: int, analysis_date: date) -> Dict:
        """Analyze holders for a specific collection"""
        analysis = {
            'collection_slug': collection_slug,
            'total_supply': 0,
            'unique_holders': 0,
            'listings': {
                'total': 0,
                'floor_count': 0,
                'above_floor': 0,
                'avg_price': 0.0,
                'whale_listings': 0
            },
            'holder_patterns': {
                'diamond_hands': 0,
                'new_holders': 0,
                'concentration': 0.0
            }
        }
        
        try:
            # Get collection stats from OpenSea
            stats_url = f'https://api.opensea.io/api/v2/collections/{collection_slug}/stats'
            stats_response = requests.get(stats_url, headers=self.opensea_headers, timeout=10)
            
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                analysis['total_supply'] = int(stats_data.get('total', {}).get('supply', 0))
                analysis['floor_price'] = float(stats_data.get('total', {}).get('floor_price', 0))
            
            # Get collection info for more details
            collection_url = f'https://api.opensea.io/api/v2/collections/{collection_slug}'
            collection_response = requests.get(collection_url, headers=self.opensea_headers, timeout=10)
            
            if collection_response.status_code == 200:
                collection_data = collection_response.json()
                analysis['total_supply'] = int(collection_data.get('total_supply', analysis['total_supply']))
            
            # Get real unique holders from OpenSea
            analysis['unique_holders'] = await self._get_real_unique_holders(collection_slug)
            
            # Get listings data (simplified - would need listings endpoint for full analysis)
            analysis['listings'] = await self._analyze_listings(collection_slug, analysis['floor_price'])
            
            logger.info(f"{collection_slug}: {analysis['unique_holders']} holders, {analysis['listings']['total']} listings")
            
        except Exception as e:
            logger.error(f"Error analyzing {collection_slug}: {e}")
        
        return analysis
    
    async def _get_real_unique_holders(self, collection_slug: str) -> int:
        """Get actual unique holders from OpenSea stats endpoint"""
        try:
            # Use OpenSea's stats endpoint which has num_owners
            stats_url = f'https://api.opensea.io/api/v2/collections/{collection_slug}/stats'
            response = requests.get(stats_url, headers=self.opensea_headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Get real owner count from stats
                owners = data.get('total', {}).get('num_owners', 0)
                if owners > 0:
                    logger.info(f"Got real owner count for {collection_slug}: {owners}")
                    return int(owners)
            
            logger.warning(f"Could not get real owner data for {collection_slug}")
            
        except Exception as e:
            logger.error(f"Error getting real holder data for {collection_slug}: {e}")
        
        # Fallback to estimation if API fails
        return 0
    
    async def _analyze_listings(self, collection_slug: str, floor_price: float) -> Dict:
        """Get real listing data from OpenSea"""
        listings_analysis = {
            'total': 0,
            'floor_count': 0,
            'above_floor': 0,
            'avg_price': 0.0,
            'whale_listings': 0,
            'listing_percentage': 0.0
        }
        
        try:
            # Get real listing data from OpenSea stats
            stats_url = f'https://api.opensea.io/api/v2/collections/{collection_slug}/stats'
            response = requests.get(stats_url, headers=self.opensea_headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                total_stats = data.get('total', {})
                
                # Note: OpenSea stats doesn't include listing counts
                # We'll need to estimate based on typical market behavior
                # But we can get real volume and sales data
                
                # Get real sales and volume data
                total_volume = total_stats.get('volume', 0)
                total_sales = total_stats.get('sales', 0)
                floor_price = total_stats.get('floor_price', 0)
                
                if total_volume > 0:
                    listings_analysis['total_volume_eth'] = float(total_volume)
                if total_sales > 0:
                    listings_analysis['total_sales'] = int(total_sales)
                if floor_price > 0:
                    listings_analysis['floor_price_verified'] = float(floor_price)
                    
                logger.info(f"Real market data for {collection_slug}: {total_sales} sales, {total_volume:.2f} ETH volume")
                
                # Get volume data for context
                for interval in data.get('intervals', []):
                    if interval.get('interval') == 'one_day':
                        volume_24h = float(interval.get('volume', 0))
                        if volume_24h > 0:
                            listings_analysis['volume_24h'] = volume_24h
                        break
                
                # Estimate floor vs above-floor distribution (still need estimation)
                if listings_analysis['total'] > 0:
                    listings_analysis['floor_count'] = int(listings_analysis['total'] * 0.3)  # 30% typically at floor
                    listings_analysis['above_floor'] = listings_analysis['total'] - listings_analysis['floor_count']
                    
                    # Average listing price (typically 10-20% above floor)
                    listings_analysis['avg_price'] = floor_price * 1.15
                    
                    # Whale listings estimate
                    listings_analysis['whale_listings'] = int(listings_analysis['total'] * 0.15)
            
            else:
                logger.warning(f"Could not get listing data for {collection_slug}, status: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error getting real listing data for {collection_slug}: {e}")
        
        return listings_analysis
    
    async def _get_collection_supply(self, collection_slug: str) -> int:
        """Get current supply for a collection"""
        try:
            url = f'https://api.opensea.io/api/v2/collections/{collection_slug}'
            response = requests.get(url, headers=self.opensea_headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return int(data.get('total_supply', 0))
        except Exception as e:
            logger.error(f"Error getting supply for {collection_slug}: {e}")
        
        return 0
    
    def _generate_summary_insights(self, collections_data: Dict) -> Dict:
        """Generate cross-collection insights and trends"""
        summary = {
            'total_unique_holders': 0,
            'migration_holder_overlap': 0,
            'listing_pressure': 'low',
            'market_sentiment': 'neutral',
            'key_insights': []
        }
        
        try:
            # Calculate total holders across both collections
            origins_holders = collections_data.get('origins', {}).get('unique_holders', 0)
            undead_holders = collections_data.get('undead', {}).get('unique_holders', 0)
            
            # Estimate holder overlap (those who hold both collections)
            # In migration scenarios, typically 20-40% of holders hold both
            estimated_overlap = int(min(origins_holders, undead_holders) * 0.35)  # 35% overlap estimate
            summary['migration_holder_overlap'] = estimated_overlap
            
            # Calculate actual unique holders (subtract overlap to avoid double counting)
            summary['total_unique_holders'] = origins_holders + undead_holders - estimated_overlap
            
            # Analyze listing pressure
            total_listings = 0
            total_supply = 0
            
            for collection_data in collections_data.values():
                total_listings += collection_data.get('listings', {}).get('total', 0)
                total_supply += collection_data.get('total_supply', 0)
            
            if total_supply > 0:
                listing_ratio = total_listings / total_supply
                if listing_ratio < 0.03:
                    summary['listing_pressure'] = 'low'
                elif listing_ratio > 0.08:
                    summary['listing_pressure'] = 'high'
                else:
                    summary['listing_pressure'] = 'moderate'
            
            # Generate key insights
            summary['key_insights'] = self._generate_key_insights(collections_data, summary)
            
        except Exception as e:
            logger.error(f"Error generating summary insights: {e}")
        
        return summary
    
    def _generate_key_insights(self, collections_data: Dict, summary: Dict) -> List[str]:
        """Generate human-readable insights from the analysis"""
        insights = []
        
        try:
            # Migration progress insight
            undead_supply = collections_data.get('undead', {}).get('total_supply', 0)
            if undead_supply > 5000:
                migration_pct = (undead_supply / 9993) * 100
                insights.append(f"Migration Progress: {migration_pct:.1f}% of Origins have migrated to Undead ({undead_supply:,} of 9,993)")
            
            # Holder distribution insight
            total_holders = summary.get('total_unique_holders', 0)
            holder_overlap = summary.get('migration_holder_overlap', 0)
            if total_holders > 0:
                insights.append(f"Community Size: ~{total_holders:,} unique holders (estimated {holder_overlap:,} hold both collections)")
            
            # Listing pressure insight
            listing_pressure = summary.get('listing_pressure', 'moderate')
            pressure_messages = {
                'low': 'Strong holder confidence with minimal selling pressure',
                'moderate': 'Balanced market with normal trading activity', 
                'high': 'Increased selling pressure - potential buying opportunity'
            }
            insights.append(f"Market Sentiment: {pressure_messages.get(listing_pressure, 'Normal trading activity')}")
            
            # Floor price comparison
            origins_floor = collections_data.get('origins', {}).get('floor_price', 0)
            undead_floor = collections_data.get('undead', {}).get('floor_price', 0)
            
            if origins_floor > 0 and undead_floor > 0:
                ratio = undead_floor / origins_floor
                if ratio > 1.1:
                    insights.append(f"Undead trading at {ratio:.1f}x premium to Origins - migration creating value")
                elif ratio < 0.9:
                    insights.append(f"Undead trading at discount to Origins - potential arbitrage opportunity")
                else:
                    insights.append(f"Price parity maintained between collections (ratio: {ratio:.2f})")
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
        
        return insights
    
    def _store_holder_analysis(self, results: Dict, analysis_date: date):
        """Store analysis results in database"""
        try:
            with self.db.get_connection() as conn:
                for collection_key, collection_data in results['collections'].items():
                    collection_id = self.collections[collection_key]['collection_id']
                    
                    # Store holder counts
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_holder_counts (
                            collection_id, analysis_date, total_holders, unique_holders, 
                            avg_holdings_per_holder
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        collection_id,
                        analysis_date.isoformat(),
                        collection_data.get('total_supply', 0),
                        collection_data.get('unique_holders', 0),
                        1.0  # Simplified average
                    ))
                    
                    # Store listing analysis
                    listings = collection_data.get('listings', {})
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_listing_analysis (
                            collection_id, analysis_date, total_listings, floor_listings,
                            above_floor_listings, avg_listing_price, median_listing_price,
                            whale_listings, new_holder_listings
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        collection_id,
                        analysis_date.isoformat(),
                        listings.get('total', 0),
                        listings.get('floor_count', 0),
                        listings.get('above_floor', 0),
                        listings.get('avg_price', 0.0),
                        listings.get('avg_price', 0.0),  # Using avg as median estimate
                        listings.get('whale_listings', 0),
                        0  # Would need historical data to calculate
                    ))
                
                conn.commit()
                logger.info("Holder analysis data stored successfully")
                
        except Exception as e:
            logger.error(f"Error storing holder analysis: {e}")
            raise
    
    def get_recent_holder_trends(self, days: int = 7) -> Dict:
        """Get holder trends for the past N days"""
        try:
            with self.db.get_connection() as conn:
                # Get recent holder data
                cursor = conn.execute("""
                    SELECT hc.analysis_date, c.name, hc.unique_holders, hc.total_holders,
                           la.total_listings, la.avg_listing_price
                    FROM daily_holder_counts hc
                    LEFT JOIN daily_listing_analysis la ON hc.collection_id = la.collection_id 
                        AND hc.analysis_date = la.analysis_date
                    LEFT JOIN collections c ON hc.collection_id = c.id
                    WHERE hc.analysis_date >= date('now', '-{} days')
                    ORDER BY hc.analysis_date DESC, hc.collection_id
                """.format(days))
                
                trends_data = cursor.fetchall()
                
                # Format trends data
                trends = {
                    'period_days': days,
                    'collections': {},
                    'insights': []
                }
                
                for row in trends_data:
                    date_str = row[0]
                    collection_name = row[1] or 'Unknown'
                    
                    if collection_name not in trends['collections']:
                        trends['collections'][collection_name] = []
                    
                    trends['collections'][collection_name].append({
                        'date': date_str,
                        'unique_holders': row[2],
                        'total_holders': row[3],
                        'total_listings': row[4] or 0,
                        'avg_listing_price': row[5] or 0.0
                    })
                
                return trends
                
        except Exception as e:
            logger.error(f"Error getting holder trends: {e}")
            return {'period_days': days, 'collections': {}, 'insights': []}


async def main():
    """Test the holder analysis service"""
    service = HolderAnalysisService()
    
    print("=== GU MIGRATION TRACKER - HOLDER ANALYSIS ===")
    print(f"Analysis Date: {date.today()}")
    print("=" * 50)
    
    # Run daily analysis
    results = await service.analyze_daily_holders()
    
    # Display results
    print("\n[CHART] HOLDER ANALYSIS RESULTS:")
    print(f"Analysis Date: {results['analysis_date']}")
    
    for collection_key, data in results['collections'].items():
        collection_name = service.collections[collection_key]['name']
        print(f"\n[>] {collection_name}:")
        print(f"   Total Supply: {data.get('total_supply', 0):,}")
        print(f"   Unique Holders: {data.get('unique_holders', 0):,}")
        print(f"   Floor Price: {data.get('floor_price', 0):.4f} ETH")
        
        listings = data.get('listings', {})
        print(f"   Active Listings: {listings.get('total', 0)} ({listings.get('listing_percentage', 0):.1f}%)")
        print(f"   Floor Listings: {listings.get('floor_count', 0)}")
        print(f"   24h Volume: {listings.get('volume_24h', 0):.2f} ETH")
        print(f"   Avg Listing Price: {listings.get('avg_price', 0):.4f} ETH")
    
    print(f"\n[TREND] SUMMARY INSIGHTS:")
    summary = results.get('summary', {})
    print(f"   Total Unique Holders: {summary.get('total_unique_holders', 0):,}")
    print(f"   Listing Pressure: {summary.get('listing_pressure', 'unknown').title()}")
    print(f"   Market Sentiment: {summary.get('market_sentiment', 'neutral').title()}")
    
    for insight in summary.get('key_insights', []):
        print(f"   * {insight}")
    
    print("\n[SUCCESS] Holder analysis completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())