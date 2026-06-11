#!/usr/bin/env python3
"""
Individual Holder Fetcher - Gets actual holder addresses and their NFT counts
This is needed for bubble chart visualization showing individual wallets
"""
import asyncio
import os
import sys
import logging
import requests
from typing import Dict, List, Optional
import json
from datetime import datetime

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

class IndividualHolderFetcher:
    """Fetches individual holder addresses and their NFT counts"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_headers = {'X-API-KEY': os.environ.get('OPENSEA_API_KEY', '')}
        
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
        """Initialize database tables for individual holders"""
        with self.db.get_connection() as conn:
            # Table for individual holder data
            conn.execute("""
                CREATE TABLE IF NOT EXISTS individual_holders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_slug TEXT,
                    wallet_address TEXT,
                    nft_count INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_slug, wallet_address)
                )
            """)
            
            conn.commit()
            logger.info("Individual holders database initialized")
    
    async def fetch_all_holders(self) -> Dict:
        """Fetch individual holder data for all collections"""
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'collections': {},
            'total_holders': 0,
            'summary': {}
        }
        
        for key, collection in self.collections.items():
            logger.info(f"Fetching individual holders for {collection['name']}...")
            
            holders = await self._fetch_collection_holders(collection['slug'])
            
            results['collections'][key] = {
                'name': collection['name'],
                'slug': collection['slug'],
                'holders': holders,
                'holder_count': len(holders)
            }
            
            results['total_holders'] += len(holders)
            
            # Store in database
            self._store_holders(collection['slug'], holders)
        
        # Create summary
        results['summary'] = {
            'total_holders': results['total_holders'],
            'collections_processed': len(self.collections)
        }
        
        logger.info(f"Fetched {results['total_holders']} total individual holders")
        
        return results
    
    async def _fetch_collection_holders(self, collection_slug: str) -> List[Dict]:
        """Fetch all individual holders for a collection using ownership events"""
        holders_dict = {}
        
        try:
            # Use the events endpoint to find current ownership via transfers
            events_url = f'https://api.opensea.io/api/v2/events/collection/{collection_slug}'
            
            # Get recent transfer events to build ownership map
            next_cursor = None
            page = 1
            total_events = 0
            
            # Track the most recent owner for each token
            current_owners = {}  # token_id -> owner_address
            
            while page <= 100:  # Process MORE events to capture all 5300 NFTs
                params = {
                    'event_type': 'transfer',
                    'limit': 200
                }
                if next_cursor:
                    params['next'] = next_cursor
                
                logger.info(f"Fetching page {page} of transfer events for {collection_slug}...")
                
                response = requests.get(
                    events_url,
                    headers=self.opensea_headers,
                    params=params,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('asset_events', [])
                    next_cursor = data.get('next')
                    
                    logger.info(f"Found {len(events)} transfer events on page {page}")
                    total_events += len(events)
                    
                    for event in events:
                        try:
                            # Get transfer details
                            nft = event.get('nft', {})
                            token_id = nft.get('identifier', '')
                            to_address = event.get('to_address', '').lower()
                            
                            if token_id and to_address and to_address != 'unknown':
                                # Track most recent owner (events are in reverse chronological order)
                                if token_id not in current_owners:
                                    current_owners[token_id] = to_address
                                    
                        except Exception as e:
                            logger.warning(f"Error parsing transfer event: {e}")
                            continue
                    
                    # Check if we have more pages
                    if not next_cursor or len(events) == 0:
                        logger.info(f"No more events for {collection_slug}")
                        break
                    
                    page += 1
                    
                else:
                    logger.warning(f"Error fetching events page {page}: {response.status_code}")
                    if response.status_code == 429:  # Rate limit
                        logger.info("Rate limited, waiting 5 seconds...")
                        await asyncio.sleep(5)
                        continue
                    break
            
            # Build holders dictionary from current ownership
            for token_id, owner_address in current_owners.items():
                if owner_address not in holders_dict:
                    holders_dict[owner_address] = {
                        'wallet_address': owner_address,
                        'nft_count': 0,
                        'nft_ids': []
                    }
                
                holders_dict[owner_address]['nft_count'] += 1
                holders_dict[owner_address]['nft_ids'].append(token_id)
            
            # Convert to list and sort by NFT count
            holders_list = list(holders_dict.values())
            holders_list.sort(key=lambda x: x['nft_count'], reverse=True)
            
            logger.info(f"Total transfer events processed: {total_events}")
            logger.info(f"Unique tokens tracked: {len(current_owners)}")
            logger.info(f"Unique holders found: {len(holders_list)}")
            
            # Show top holders
            if holders_list:
                logger.info("Top 5 holders:")
                for i, holder in enumerate(holders_list[:5], 1):
                    logger.info(f"  {i}. {holder['wallet_address'][:10]}... - {holder['nft_count']} NFTs")
            
            return holders_list
            
        except Exception as e:
            logger.error(f"Error fetching holders for {collection_slug}: {e}")
            return []
    
    def _store_holders(self, collection_slug: str, holders: List[Dict]):
        """Store individual holder data in database"""
        try:
            with self.db.get_connection() as conn:
                # Clear old data for this collection
                conn.execute("DELETE FROM individual_holders WHERE collection_slug = ?", (collection_slug,))
                
                # Insert new holder data
                for holder in holders:
                    conn.execute("""
                        INSERT OR REPLACE INTO individual_holders (
                            collection_slug, wallet_address, nft_count
                        ) VALUES (?, ?, ?)
                    """, (
                        collection_slug,
                        holder.get('wallet_address', 'unknown'),
                        holder.get('nft_count', 0)
                    ))
                
                conn.commit()
                logger.info(f"Stored {len(holders)} individual holders for {collection_slug}")
                
        except Exception as e:
            logger.error(f"Error storing individual holders: {e}")
    
    def get_stored_holders(self, collection_slug: str = None) -> List[Dict]:
        """Get individual holders from database"""
        try:
            with self.db.get_connection() as conn:
                if collection_slug:
                    cursor = conn.execute("""
                        SELECT collection_slug, wallet_address, nft_count, last_updated
                        FROM individual_holders
                        WHERE collection_slug = ?
                        ORDER BY nft_count DESC
                    """, (collection_slug,))
                else:
                    cursor = conn.execute("""
                        SELECT collection_slug, wallet_address, nft_count, last_updated
                        FROM individual_holders
                        ORDER BY nft_count DESC
                    """)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'collection_slug': row[0],
                        'wallet_address': row[1],
                        'nft_count': row[2],
                        'last_updated': row[3]
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting stored holders: {e}")
            return []


async def main():
    """Test the individual holder fetcher"""
    print("=" * 70)
    print("INDIVIDUAL HOLDER FETCHER - REAL WALLET ADDRESSES & COUNTS")
    print("=" * 70)
    
    fetcher = IndividualHolderFetcher()
    
    # Fetch all holders
    print("\nFetching individual holder data from OpenSea...")
    results = await fetcher.fetch_all_holders()
    
    print(f"\n[RESULTS] Individual Holder Summary:")
    print(f"Total Holders: {results['summary']['total_holders']}")
    
    # Show by collection
    for key, data in results['collections'].items():
        print(f"\n[{data['name']}]:")
        print(f"  Individual Holders: {data['holder_count']}")
        
        # Show top holders
        if data['holders']:
            top_holders = data['holders'][:5]
            print(f"  Top Holders:")
            for i, holder in enumerate(top_holders, 1):
                print(f"    {i}. {holder['wallet_address'][:15]}... - {holder['nft_count']} NFTs")
    
    print(f"\n[SUCCESS] Individual holder data fetched and stored!")


if __name__ == "__main__":
    asyncio.run(main())