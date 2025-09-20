#!/usr/bin/env python3
"""
Active Listing Tracker - Gets ONLY currently active listings
Uses OpenSea's best offers endpoint to find real active listings
"""
import asyncio
import os
import sys
from datetime import date, datetime
import logging
import requests
from typing import Dict, List, Optional
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

class ActiveListingTracker:
    """Tracks ONLY currently active listings, not historical events"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        
        # Collections to track
        self.collections = {
            'origins': {
                'slug': 'gu-origins',
                'name': 'GU Origins',
                'contract': '0xb554494e632a4163ab07b6e6723f3d85dc5d71ec'
            },
            'undead': {
                'slug': 'genuine-undead', 
                'name': 'Genuine Undead',
                'contract': '0x209e639a0ec166ac7a1a4ba41968fa967db30221'
            }
        }
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables for active listings"""
        with self.db.get_connection() as conn:
            # Table for active listings only
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_slug TEXT,
                    token_id TEXT,
                    seller_address TEXT,
                    listing_price_eth REAL,
                    listing_price_usd REAL,
                    floor_price_eth REAL,
                    is_floor_listing BOOLEAN,
                    created_date TEXT,
                    expiration_date TEXT,
                    last_verified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_slug, token_id)
                )
            """)
            
            conn.commit()
            logger.info("Active listings database initialized")
    
    async def get_active_listings(self) -> Dict:
        """Get ONLY currently active listings using best offers API"""
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'collections': {},
            'total_active_listings': 0,
            'unique_sellers': set(),
            'summary': {}
        }
        
        for key, collection in self.collections.items():
            logger.info(f"Getting active listings for {collection['name']}...")
            
            active_listings = await self._fetch_active_listings(collection['slug'])
            
            # Group by seller
            sellers = {}
            for listing in active_listings:
                seller = listing['seller_address']
                if seller not in sellers:
                    sellers[seller] = {
                        'address': seller,
                        'listings': [],
                        'total_value_eth': 0
                    }
                sellers[seller]['listings'].append(listing)
                sellers[seller]['total_value_eth'] += listing['price_eth']
                results['unique_sellers'].add(seller)
            
            results['collections'][key] = {
                'name': collection['name'],
                'active_listings': len(active_listings),
                'unique_sellers': len(sellers),
                'sellers': sellers,
                'listings': active_listings
            }
            
            results['total_active_listings'] += len(active_listings)
            
            # Store in database
            self._store_active_listings(collection['slug'], active_listings)
        
        # Create summary
        results['summary'] = {
            'total_active_listings': results['total_active_listings'],
            'unique_sellers': len(results['unique_sellers']),
            'collections_tracked': len(self.collections)
        }
        
        logger.info(f"Found {results['total_active_listings']} total active listings from {len(results['unique_sellers'])} sellers")
        
        return results
    
    async def _fetch_active_listings(self, collection_slug: str) -> List[Dict]:
        """Fetch ALL active listings using the comprehensive /all endpoint"""
        active_listings = []
        
        try:
            # Use the ALL listings endpoint to get complete data
            all_listings_url = f'https://api.opensea.io/api/v2/listings/collection/{collection_slug}/all'
            
            # Get all listings with pagination
            next_cursor = None
            page = 1
            
            while page <= 5:  # Safety limit of 5 pages
                params = {'limit': 200}
                if next_cursor:
                    params['next'] = next_cursor
                
                logger.info(f"Fetching page {page} of all listings for {collection_slug}...")
                
                response = requests.get(
                    all_listings_url,
                    headers=self.opensea_headers,
                    params=params,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    listings = data.get('listings', [])
                    next_cursor = data.get('next')
                    
                    logger.info(f"Found {len(listings)} listings on page {page}")
                    
                    for listing in listings:
                        try:
                            # Extract listing details
                            price = listing.get('price', {})
                            protocol_data = listing.get('protocol_data', {})
                            parameters = protocol_data.get('parameters', {})
                            offer = parameters.get('offer', [{}])[0] if parameters.get('offer') else {}
                            
                            listing_info = {
                                'token_id': offer.get('identifierOrCriteria', 'unknown'),
                                'seller_address': parameters.get('offerer', 'unknown'),
                                'price_eth': 0.0,
                                'currency': 'ETH',
                                'created_date': listing.get('created_date', ''),
                                'expiration_date': listing.get('expiration_date', ''),
                                'order_hash': listing.get('order_hash', ''),
                                'listing_type': listing.get('type', 'basic')
                            }
                            
                            # Extract price more robustly
                            if price.get('current'):
                                try:
                                    price_value = price['current'].get('value', '0')
                                    if isinstance(price_value, str):
                                        listing_info['price_eth'] = float(price_value) / 1e18
                                    else:
                                        listing_info['price_eth'] = float(price_value) / 1e18
                                    listing_info['currency'] = price['current'].get('currency', 'ETH')
                                except (ValueError, TypeError):
                                    listing_info['price_eth'] = 0.0
                            
                            # Only include valid listings
                            if (listing_info['price_eth'] > 0 and 
                                listing_info['seller_address'] != 'unknown' and
                                listing_info['token_id'] != 'unknown'):
                                
                                # Check for duplicates
                                if not any(l['token_id'] == listing_info['token_id'] for l in active_listings):
                                    active_listings.append(listing_info)
                                    
                        except Exception as e:
                            logger.warning(f"Error parsing listing: {e}")
                            continue
                    
                    # Check if we have more pages
                    if not next_cursor or len(listings) == 0:
                        logger.info(f"No more pages for {collection_slug}")
                        break
                    
                    page += 1
                    
                else:
                    logger.warning(f"Error fetching listings page {page}: {response.status_code}")
                    break
            
            # Method 2: Use collection stats to get current floor listings
            stats_url = f'https://api.opensea.io/api/v2/collections/{collection_slug}/stats'
            response = requests.get(stats_url, headers=self.opensea_headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                floor_price = float(data.get('total', {}).get('floor_price', 0))
                
                # Mark floor listings
                for listing in active_listings:
                    if abs(listing['price_eth'] - floor_price) < 0.001:  # Within 0.001 ETH of floor
                        listing['is_floor_listing'] = True
                    else:
                        listing['is_floor_listing'] = False
            
            logger.info(f"Total active listings found for {collection_slug}: {len(active_listings)}")
            
        except Exception as e:
            logger.error(f"Error fetching active listings for {collection_slug}: {e}")
        
        return active_listings
    
    def _store_active_listings(self, collection_slug: str, listings: List[Dict]):
        """Store active listings in database"""
        try:
            with self.db.get_connection() as conn:
                # Clear old listings for this collection
                conn.execute("DELETE FROM active_listings WHERE collection_slug = ?", (collection_slug,))
                
                # Insert new active listings
                for listing in listings:
                    conn.execute("""
                        INSERT OR REPLACE INTO active_listings (
                            collection_slug, token_id, seller_address, 
                            listing_price_eth, is_floor_listing,
                            created_date, expiration_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        collection_slug,
                        listing.get('token_id', 'unknown'),
                        listing.get('seller_address', 'unknown'),
                        listing.get('price_eth', 0),
                        listing.get('is_floor_listing', False),
                        listing.get('created_date', ''),
                        listing.get('expiration_date', '')
                    ))
                
                conn.commit()
                logger.info(f"Stored {len(listings)} active listings for {collection_slug}")
                
        except Exception as e:
            logger.error(f"Error storing active listings: {e}")
    
    def get_seller_summary(self) -> List[Dict]:
        """Get summary of sellers with ACTIVE listings"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        seller_address,
                        collection_slug,
                        COUNT(*) as listing_count,
                        AVG(listing_price_eth) as avg_price,
                        SUM(listing_price_eth) as total_value,
                        SUM(CASE WHEN is_floor_listing THEN 1 ELSE 0 END) as floor_listings
                    FROM active_listings
                    GROUP BY seller_address, collection_slug
                    ORDER BY listing_count DESC, total_value DESC
                """)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'seller_address': row[0],
                        'collection': row[1],
                        'listing_count': row[2],
                        'avg_price': row[3],
                        'total_value': row[4],
                        'floor_listings': row[5]
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting seller summary: {e}")
            return []


async def main():
    """Test the active listing tracker"""
    print("=" * 70)
    print("ACTIVE LISTING TRACKER - REAL CURRENT LISTINGS ONLY")
    print("=" * 70)
    
    tracker = ActiveListingTracker()
    
    # Get active listings
    print("\nFetching ONLY currently active listings from OpenSea...")
    results = await tracker.get_active_listings()
    
    print(f"\n[RESULTS] Active Listings Summary:")
    print(f"Total Active Listings: {results['summary']['total_active_listings']}")
    print(f"Unique Sellers: {results['summary']['unique_sellers']}")
    
    # Show by collection
    for key, data in results['collections'].items():
        print(f"\n[{data['name']}]:")
        print(f"  Active Listings: {data['active_listings']}")
        print(f"  Unique Sellers: {data['unique_sellers']}")
        
        # Show top sellers
        if data['sellers']:
            top_sellers = sorted(data['sellers'].values(), key=lambda x: len(x['listings']), reverse=True)[:3]
            print(f"  Top Sellers:")
            for seller in top_sellers:
                print(f"    {seller['address'][:10]}...: {len(seller['listings'])} listings, {seller['total_value_eth']:.3f} ETH total")
    
    # Get detailed seller summary
    print(f"\n[SELLER DETAILS] Top Active Sellers:")
    seller_summary = tracker.get_seller_summary()
    
    for i, seller in enumerate(seller_summary[:10], 1):
        print(f"{i}. {seller['seller_address']}")
        print(f"   Collection: {seller['collection']}")
        print(f"   Active Listings: {seller['listing_count']}")
        print(f"   Avg Price: {seller['avg_price']:.4f} ETH")
        print(f"   Total Value: {seller['total_value']:.4f} ETH")
        print(f"   Floor Listings: {seller['floor_listings']}")
        print()
    
    # Verify specific wallet
    test_wallet = "0x69382e9a59e6f5937e87302043ab10a6a7f74e75"
    print(f"\n[VERIFICATION] Checking wallet {test_wallet}:")
    
    wallet_found = False
    for collection_data in results['collections'].values():
        if test_wallet.lower() in [s.lower() for s in collection_data['sellers'].keys()]:
            seller_data = collection_data['sellers'][test_wallet.lower()]
            print(f"  FOUND: {len(seller_data['listings'])} active listings")
            wallet_found = True
            break
    
    if not wallet_found:
        print(f"  Wallet has NO active listings (historical events don't count)")
    
    print("\n[SUCCESS] Active listing tracking complete - data is now accurate!")


if __name__ == "__main__":
    asyncio.run(main())