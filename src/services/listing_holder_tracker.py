#!/usr/bin/env python3
"""
Listing Holder Tracker for GU Migration Tracker
Tracks which specific holders have NFTs listed for sale
"""
import asyncio
import os
import sys
from datetime import date, datetime
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

class ListingHolderTracker:
    """Tracks which holders have NFTs listed for sale"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        
        # Collection contracts
        self.collections = {
            'origins': {
                'slug': 'gu-origins',
                'name': 'GU Origins',
                'contract': '0xb8d685d4e404c9b1177dfe14c2c9e0dd2f5e49ba'  # GU Origins contract
            },
            'undead': {
                'slug': 'genuine-undead', 
                'name': 'Genuine Undead',
                'contract': '0x6370100526ba0f2368f8ecf4bef93e0f7f637b1f'  # Genuine Undead contract
            }
        }
        
        # Create listing tracking tables
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables for listing tracking"""
        with self.db.get_connection() as conn:
            # Table for tracking daily listings by holder
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_holder_listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_slug TEXT,
                    analysis_date DATE,
                    holder_address TEXT,
                    token_id TEXT,
                    listing_price_eth REAL,
                    listing_price_usd REAL,
                    listing_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_slug, analysis_date, holder_address, token_id)
                )
            """)
            
            # Table for tracking holder listing patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS holder_listing_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_slug TEXT,
                    analysis_date DATE,
                    holder_address TEXT,
                    total_owned INTEGER,
                    total_listed INTEGER,
                    listing_percentage REAL,
                    avg_listing_price_eth REAL,
                    holder_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_slug, analysis_date, holder_address)
                )
            """)
            
            conn.commit()
            logger.info("Listing tracking database tables initialized")
    
    async def track_daily_listings(self, analysis_date: date = None) -> Dict:
        """Track all listings by holder for both collections"""
        if analysis_date is None:
            analysis_date = date.today()
            
        logger.info(f"Starting daily listing tracking for {analysis_date}")
        
        results = {
            'analysis_date': analysis_date.isoformat(),
            'collections': {},
            'summary': {
                'total_listings': 0,
                'unique_listing_holders': 0,
                'total_listing_value_eth': 0.0
            }
        }
        
        try:
            # Track listings for each collection
            for key, collection in self.collections.items():
                logger.info(f"Tracking listings for {collection['name']}...")
                
                collection_listings = await self._get_collection_listings(
                    collection['slug'], 
                    collection['contract']
                )
                
                # Analyze listing patterns
                listing_patterns = self._analyze_listing_patterns(collection_listings)
                
                results['collections'][key] = {
                    'collection_name': collection['name'],
                    'total_listings': len(collection_listings),
                    'listing_holders': listing_patterns['unique_holders'],
                    'listings': collection_listings,
                    'patterns': listing_patterns
                }
                
                # Update summary
                results['summary']['total_listings'] += len(collection_listings)
                results['summary']['unique_listing_holders'] += listing_patterns['unique_holders']
                results['summary']['total_listing_value_eth'] += listing_patterns['total_value_eth']
            
            # Store results
            self._store_listing_data(results, analysis_date)
            
            logger.info("Daily listing tracking completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error in daily listing tracking: {e}")
            raise
    
    async def _get_collection_listings(self, collection_slug: str, contract_address: str) -> List[Dict]:
        """Get current listings for a collection using working OpenSea endpoints"""
        listings = []
        
        try:
            # Method 1: Try to get NFTs with orders included
            logger.info(f"Getting NFTs with order data for {collection_slug}...")
            nfts_url = f'https://api.opensea.io/api/v2/collection/{collection_slug}/nfts'
            params = {
                'limit': 200,  # Get more NFTs to find listings
                'include_orders': 'true'
            }
            
            response = requests.get(nfts_url, headers=self.opensea_headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                nfts = data.get('nfts', [])
                
                for nft in nfts:
                    orders = nft.get('orders', [])
                    if orders:
                        # Found NFT with active orders (listings)
                        for order in orders:
                            try:
                                listing_info = {
                                    'token_id': nft.get('identifier', 'unknown'),
                                    'holder_address': order.get('maker', 'unknown'),
                                    'price_eth': 0.0,
                                    'currency': 'ETH',
                                    'listing_type': order.get('order_type', 'basic'),
                                    'order_hash': order.get('order_hash', ''),
                                    'created_date': order.get('created_date', ''),
                                    'expiration_date': order.get('expiration_date', '')
                                }
                                
                                # Extract price
                                current_price = order.get('current_price', '0')
                                try:
                                    listing_info['price_eth'] = float(current_price) / 1e18 if current_price else 0.0
                                except (ValueError, TypeError):
                                    listing_info['price_eth'] = 0.0
                                
                                if listing_info['price_eth'] > 0 and listing_info['holder_address'] != 'unknown':
                                    listings.append(listing_info)
                                    
                            except Exception as e:
                                logger.warning(f"Error parsing order for NFT {nft.get('identifier')}: {e}")
                                continue
                
                logger.info(f"Found {len(listings)} NFTs with active orders for {collection_slug}")
            
            # Method 2: Use recent listing events as backup
            if len(listings) == 0:
                logger.info(f"No active orders found, checking recent listing events for {collection_slug}...")
                listings = await self._get_recent_listing_events(collection_slug)
        
        except Exception as e:
            logger.error(f"Error getting listings for {collection_slug}: {e}")
        
        return listings
    
    async def _get_recent_listing_events(self, collection_slug: str) -> List[Dict]:
        """Get recent listing events as current listings"""
        recent_listings = []
        
        try:
            # Get recent listing events
            events_url = f'https://api.opensea.io/api/v2/events/collection/{collection_slug}'
            params = {
                'event_type': 'listing',
                'limit': 100  # Get more recent listings
            }
            
            response = requests.get(events_url, headers=self.opensea_headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for event in data.get('asset_events', []):
                    try:
                        nft = event.get('nft', {})
                        payment = event.get('payment', {})
                        
                        listing_info = {
                            'token_id': nft.get('identifier', 'unknown'),
                            'holder_address': event.get('maker', 'unknown'),
                            'price_eth': 0.0,
                            'currency': payment.get('symbol', 'ETH'),
                            'listing_type': 'recent_event',
                            'created_date': event.get('event_timestamp', ''),
                            'event_type': event.get('event_type', '')
                        }
                        
                        # Extract price from payment
                        price_str = payment.get('quantity', '0')
                        try:
                            listing_info['price_eth'] = float(price_str) / 1e18 if price_str else 0.0
                        except (ValueError, TypeError):
                            listing_info['price_eth'] = 0.0
                        
                        if listing_info['price_eth'] > 0 and listing_info['holder_address'] != 'unknown':
                            recent_listings.append(listing_info)
                            
                    except Exception as e:
                        logger.warning(f"Error parsing listing event: {e}")
                        continue
                
                logger.info(f"Found {len(recent_listings)} recent listing events for {collection_slug}")
        
        except Exception as e:
            logger.error(f"Error getting recent listing events for {collection_slug}: {e}")
        
        return recent_listings
    
    def _analyze_listing_patterns(self, listings: List[Dict]) -> Dict:
        """Analyze listing patterns by holder"""
        patterns = {
            'unique_holders': 0,
            'total_value_eth': 0.0,
            'holders': {},
            'whale_listers': [],
            'floor_listers': [],
            'premium_listers': []
        }
        
        if not listings:
            return patterns
        
        # Group by holder
        holder_listings = {}
        for listing in listings:
            holder = listing['holder_address']
            if holder not in holder_listings:
                holder_listings[holder] = []
            holder_listings[holder].append(listing)
        
        patterns['unique_holders'] = len(holder_listings)
        
        # Analyze each holder's listing behavior
        floor_price = min(l['price_eth'] for l in listings if l['price_eth'] > 0) if listings else 0
        
        for holder_address, holder_listings_list in holder_listings.items():
            total_listed = len(holder_listings_list)
            avg_price = sum(l['price_eth'] for l in holder_listings_list) / total_listed
            total_value = sum(l['price_eth'] for l in holder_listings_list)
            
            patterns['total_value_eth'] += total_value
            
            holder_pattern = {
                'address': holder_address,
                'total_listed': total_listed,
                'avg_listing_price': avg_price,
                'total_listing_value': total_value,
                'listings': holder_listings_list
            }
            
            # Categorize holder type
            if total_listed >= 5:
                holder_pattern['type'] = 'whale_lister'
                patterns['whale_listers'].append(holder_pattern)
            elif avg_price <= floor_price * 1.05:  # Within 5% of floor
                holder_pattern['type'] = 'floor_lister'
                patterns['floor_listers'].append(holder_pattern)
            elif avg_price >= floor_price * 1.5:  # 50%+ above floor
                holder_pattern['type'] = 'premium_lister'
                patterns['premium_listers'].append(holder_pattern)
            else:
                holder_pattern['type'] = 'regular_lister'
            
            patterns['holders'][holder_address] = holder_pattern
        
        return patterns
    
    def _store_listing_data(self, results: Dict, analysis_date: date):
        """Store listing data in database"""
        try:
            with self.db.get_connection() as conn:
                for collection_key, collection_data in results['collections'].items():
                    collection_slug = self.collections[collection_key]['slug']
                    
                    # Store individual listings
                    for listing in collection_data.get('listings', []):
                        conn.execute("""
                            INSERT OR REPLACE INTO daily_holder_listings (
                                collection_slug, analysis_date, holder_address, token_id,
                                listing_price_eth, listing_type
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            collection_slug,
                            analysis_date.isoformat(),
                            listing['holder_address'],
                            listing['token_id'],
                            listing['price_eth'],
                            listing['listing_type']
                        ))
                    
                    # Store holder patterns
                    patterns = collection_data.get('patterns', {})
                    for holder_address, holder_data in patterns.get('holders', {}).items():
                        conn.execute("""
                            INSERT OR REPLACE INTO holder_listing_patterns (
                                collection_slug, analysis_date, holder_address,
                                total_listed, avg_listing_price_eth, holder_type
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            collection_slug,
                            analysis_date.isoformat(),
                            holder_address,
                            holder_data['total_listed'],
                            holder_data['avg_listing_price'],
                            holder_data['type']
                        ))
                
                conn.commit()
                logger.info("Listing data stored successfully")
                
        except Exception as e:
            logger.error(f"Error storing listing data: {e}")
            raise
    
    def get_top_listers(self, collection_slug: str = None, limit: int = 10) -> List[Dict]:
        """Get top holders by number of listings"""
        try:
            with self.db.get_connection() as conn:
                if collection_slug:
                    cursor = conn.execute("""
                        SELECT holder_address, collection_slug, total_listed, 
                               avg_listing_price_eth, holder_type
                        FROM holder_listing_patterns 
                        WHERE collection_slug = ?
                        ORDER BY total_listed DESC, avg_listing_price_eth DESC
                        LIMIT ?
                    """, (collection_slug, limit))
                else:
                    cursor = conn.execute("""
                        SELECT holder_address, collection_slug, total_listed, 
                               avg_listing_price_eth, holder_type
                        FROM holder_listing_patterns 
                        ORDER BY total_listed DESC, avg_listing_price_eth DESC
                        LIMIT ?
                    """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting top listers: {e}")
            return []


async def main():
    """Test the listing holder tracker"""
    print("=" * 60)
    print("GU MIGRATION TRACKER - LISTING HOLDER TRACKER")
    print(f"Date: {date.today()}")
    print("=" * 60)
    
    tracker = ListingHolderTracker()
    
    # Run listing tracking
    print("Tracking current listings by holder...")
    results = await tracker.track_daily_listings()
    
    # Display results
    print(f"\n[RESULTS] Listing Analysis for {results['analysis_date']}:")
    print(f"Total Listings: {results['summary']['total_listings']}")
    print(f"Unique Listing Holders: {results['summary']['unique_listing_holders']}")
    print(f"Total Value: {results['summary']['total_listing_value_eth']:.2f} ETH")
    
    for collection_key, data in results['collections'].items():
        collection_name = data['collection_name']
        print(f"\n[>] {collection_name}:")
        print(f"   Active Listings: {data['total_listings']}")
        print(f"   Listing Holders: {data['listing_holders']}")
        
        patterns = data.get('patterns', {})
        print(f"   Whale Listers (5+ NFTs): {len(patterns.get('whale_listers', []))}")
        print(f"   Floor Listers: {len(patterns.get('floor_listers', []))}")
        print(f"   Premium Listers: {len(patterns.get('premium_listers', []))}")
        
        # Show top listers
        if patterns.get('whale_listers'):
            print(f"   Top Whale Lister: {patterns['whale_listers'][0]['total_listed']} listings")
    
    # Get top listers overall
    print(f"\n[TOP] Top Listers Across All Collections:")
    top_listers = tracker.get_top_listers(limit=5)
    for i, lister in enumerate(top_listers, 1):
        print(f"   {i}. {lister['holder_address'][:8]}... ({lister['collection_slug']}): {lister['total_listed']} listings")
    
    print("\n[SUCCESS] Listing holder tracking completed!")


if __name__ == "__main__":
    asyncio.run(main())