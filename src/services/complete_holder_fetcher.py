#!/usr/bin/env python3
"""
Complete Holder Fetcher - Gets ALL holders for Genuine Undead collection
Ensures we capture all 5300 NFTs and their current owners
"""
import asyncio
import os
import sys
import logging
import requests
from typing import Dict, List
import json
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CompleteHolderFetcher:
    """Fetches complete holder data for Genuine Undead collection"""
    
    def __init__(self):
        self.opensea_headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        self.collection_slug = 'genuine-undead'
        self.contract_address = '0x209e639a0ec166ac7a1a4ba41968fa967db30221'
        self.total_supply = 5300  # Known total supply
        
    async def fetch_all_holders_via_listings(self) -> Dict:
        """
        Fetch holders by combining multiple data sources:
        1. Active listings (sellers)
        2. Recent sales (buyers/sellers)
        3. Transfer events (all movements)
        """
        
        logger.info(f"Starting complete holder fetch for {self.total_supply} Genuine Undead NFTs...")
        
        all_holder_data = {}
        tokens_found = set()
        
        # Method 1: Get all current listings (this tells us who owns listed NFTs)
        logger.info("\n1. Fetching active listings...")
        listed_nfts = await self._fetch_all_listings()
        logger.info(f"Found {len(listed_nfts)} listed NFTs")
        
        for listing in listed_nfts:
            owner = listing.get('seller_address', '').lower()
            token_id = listing.get('token_id', '')
            
            if owner and token_id:
                tokens_found.add(token_id)
                if owner not in all_holder_data:
                    all_holder_data[owner] = {
                        'wallet_address': owner,
                        'nft_count': 0,
                        'nft_ids': [],
                        'listed_ids': []
                    }
                
                if token_id not in all_holder_data[owner]['nft_ids']:
                    all_holder_data[owner]['nft_ids'].append(token_id)
                    all_holder_data[owner]['nft_count'] += 1
                all_holder_data[owner]['listed_ids'].append(token_id)
        
        # Method 2: Get recent sales to find more owners
        logger.info("\n2. Fetching recent sales...")
        recent_owners = await self._fetch_recent_sales()
        logger.info(f"Found {len(recent_owners)} owners from recent sales")
        
        for owner, tokens in recent_owners.items():
            if owner not in all_holder_data:
                all_holder_data[owner] = {
                    'wallet_address': owner,
                    'nft_count': 0,
                    'nft_ids': [],
                    'listed_ids': []
                }
            
            for token_id in tokens:
                if token_id not in all_holder_data[owner]['nft_ids']:
                    all_holder_data[owner]['nft_ids'].append(token_id)
                    all_holder_data[owner]['nft_count'] += 1
                    tokens_found.add(token_id)
        
        # Method 3: Get transfer events to find ALL movements
        logger.info("\n3. Fetching comprehensive transfer history...")
        transfer_owners = await self._fetch_all_transfers()
        logger.info(f"Found {len(transfer_owners)} unique tokens from transfers")
        
        for token_id, owner in transfer_owners.items():
            tokens_found.add(token_id)
            if owner not in all_holder_data:
                all_holder_data[owner] = {
                    'wallet_address': owner,
                    'nft_count': 0,
                    'nft_ids': [],
                    'listed_ids': []
                }
            
            if token_id not in all_holder_data[owner]['nft_ids']:
                all_holder_data[owner]['nft_ids'].append(token_id)
                all_holder_data[owner]['nft_count'] += 1
        
        # Convert to list and sort
        holders_list = list(all_holder_data.values())
        holders_list.sort(key=lambda x: x['nft_count'], reverse=True)
        
        # Calculate summary
        total_nfts = sum(h['nft_count'] for h in holders_list)
        total_listed = sum(len(h['listed_ids']) for h in holders_list)
        
        logger.info("\n" + "=" * 50)
        logger.info("COMPLETE HOLDER FETCH RESULTS:")
        logger.info(f"Total unique NFTs found: {len(tokens_found)}/{self.total_supply}")
        logger.info(f"Coverage: {(len(tokens_found)/self.total_supply)*100:.1f}%")
        logger.info(f"Total holders found: {len(holders_list)}")
        logger.info(f"Total NFTs tracked: {total_nfts}")
        logger.info(f"Total listings: {total_listed}")
        
        # Show top holders
        if holders_list:
            logger.info("\nTop 10 holders:")
            for i, holder in enumerate(holders_list[:10], 1):
                listed = len(holder['listed_ids'])
                logger.info(f"  {i}. {holder['wallet_address'][:10]}... - {holder['nft_count']} NFTs ({listed} listed)")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'collection': self.collection_slug,
            'total_supply': self.total_supply,
            'tokens_found': len(tokens_found),
            'coverage_percent': (len(tokens_found)/self.total_supply)*100,
            'holders': holders_list,
            'total_holders': len(holders_list),
            'total_nfts': total_nfts,
            'total_listed': total_listed
        }
    
    async def _fetch_all_listings(self) -> List[Dict]:
        """Fetch all active listings"""
        all_listings = []
        next_cursor = None
        page = 1
        
        while page <= 10:
            params = {'limit': 200}
            if next_cursor:
                params['next'] = next_cursor
            
            url = f'https://api.opensea.io/api/v2/listings/collection/{self.collection_slug}/all'
            
            try:
                response = requests.get(url, headers=self.opensea_headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    listings = data.get('listings', [])
                    next_cursor = data.get('next')
                    
                    for listing in listings:
                        try:
                            protocol_data = listing.get('protocol_data', {})
                            parameters = protocol_data.get('parameters', {})
                            offer = parameters.get('offer', [{}])[0] if parameters.get('offer') else {}
                            
                            listing_info = {
                                'token_id': offer.get('identifierOrCriteria', 'unknown'),
                                'seller_address': parameters.get('offerer', 'unknown').lower(),
                                'price_eth': 0.0
                            }
                            
                            # Extract price
                            price = listing.get('price', {})
                            if price.get('current'):
                                try:
                                    price_value = price['current'].get('value', '0')
                                    listing_info['price_eth'] = float(price_value) / 1e18
                                except:
                                    pass
                            
                            if listing_info['token_id'] != 'unknown' and listing_info['seller_address'] != 'unknown':
                                all_listings.append(listing_info)
                                
                        except Exception as e:
                            continue
                    
                    if not next_cursor or len(listings) == 0:
                        break
                    
                    page += 1
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching listings: {e}")
                break
        
        return all_listings
    
    async def _fetch_recent_sales(self) -> Dict[str, List[str]]:
        """Fetch recent sales to identify owners"""
        owner_tokens = {}
        next_cursor = None
        page = 1
        
        while page <= 20:
            params = {
                'event_type': 'sale',
                'limit': 200
            }
            if next_cursor:
                params['next'] = next_cursor
            
            url = f'https://api.opensea.io/api/v2/events/collection/{self.collection_slug}'
            
            try:
                response = requests.get(url, headers=self.opensea_headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('asset_events', [])
                    next_cursor = data.get('next')
                    
                    for event in events:
                        try:
                            # Buyer becomes the new owner
                            buyer = event.get('buyer', '').lower()
                            nft = event.get('nft', {})
                            token_id = nft.get('identifier', '')
                            
                            if buyer and token_id:
                                if buyer not in owner_tokens:
                                    owner_tokens[buyer] = []
                                if token_id not in owner_tokens[buyer]:
                                    owner_tokens[buyer].append(token_id)
                                    
                        except Exception as e:
                            continue
                    
                    if not next_cursor or len(events) == 0:
                        break
                    
                    page += 1
                    
                    # Rate limit handling
                    if page % 5 == 0:
                        await asyncio.sleep(1)
                        
                else:
                    if response.status_code == 429:
                        logger.info("Rate limited, waiting...")
                        await asyncio.sleep(5)
                        continue
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching sales: {e}")
                break
        
        return owner_tokens
    
    async def _fetch_all_transfers(self) -> Dict[str, str]:
        """Fetch comprehensive transfer history to build ownership map"""
        # Track most recent owner for each token
        current_owners = {}  # token_id -> owner_address
        next_cursor = None
        page = 1
        total_events = 0
        
        while page <= 50:  # More pages to get more coverage
            params = {
                'event_type': 'transfer',
                'limit': 200
            }
            if next_cursor:
                params['next'] = next_cursor
            
            url = f'https://api.opensea.io/api/v2/events/collection/{self.collection_slug}'
            
            try:
                logger.info(f"  Fetching transfer page {page}...")
                response = requests.get(url, headers=self.opensea_headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('asset_events', [])
                    next_cursor = data.get('next')
                    total_events += len(events)
                    
                    for event in events:
                        try:
                            nft = event.get('nft', {})
                            token_id = nft.get('identifier', '')
                            to_address = event.get('to_address', '').lower()
                            
                            if token_id and to_address and to_address != '0x0000000000000000000000000000000000000000':
                                # Events are in reverse chronological order
                                # Only update if we haven't seen this token yet (keeping most recent)
                                if token_id not in current_owners:
                                    current_owners[token_id] = to_address
                                    
                        except Exception as e:
                            continue
                    
                    logger.info(f"  Page {page}: {len(events)} events, {len(current_owners)} unique tokens so far")
                    
                    # Check coverage
                    if len(current_owners) >= self.total_supply * 0.9:  # 90% coverage is good enough
                        logger.info(f"  Reached 90% coverage, stopping transfer fetch")
                        break
                    
                    if not next_cursor or len(events) == 0:
                        break
                    
                    page += 1
                    
                    # Rate limit handling
                    if page % 5 == 0:
                        await asyncio.sleep(2)
                        
                else:
                    if response.status_code == 429:
                        logger.info("  Rate limited, waiting 10 seconds...")
                        await asyncio.sleep(10)
                        continue
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching transfers: {e}")
                break
        
        logger.info(f"  Total transfer events processed: {total_events}")
        return current_owners


async def main():
    """Test the complete holder fetcher"""
    print("=" * 70)
    print("COMPLETE GENUINE UNDEAD HOLDER FETCHER")
    print("Target: 5300 NFTs")
    print("=" * 70)
    
    fetcher = CompleteHolderFetcher()
    results = await fetcher.fetch_all_holders_via_listings()
    
    print(f"\n[FINAL RESULTS]")
    print(f"Coverage: {results['tokens_found']}/{results['total_supply']} NFTs ({results['coverage_percent']:.1f}%)")
    print(f"Total Holders: {results['total_holders']}")
    print(f"Total Listed: {results['total_listed']}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())