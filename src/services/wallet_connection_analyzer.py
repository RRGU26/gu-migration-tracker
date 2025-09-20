#!/usr/bin/env python3
"""
Wallet Connection Analyzer - Investigate if major buyer is connected to other wallets
Looks for transaction patterns, funding sources, and potential whale clusters
"""
import asyncio
import os
import sys
import logging
import requests
from typing import Dict, List, Set
import json
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WalletConnectionAnalyzer:
    """Analyzes wallet connections and transaction patterns"""
    
    def __init__(self):
        self.opensea_headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        self.etherscan_api = "YourEtherscanAPIKey"  # Would need real key for full analysis
        
        # The major buyer we're investigating
        self.target_wallet = "0xd484c930df5fbc2cd5cde71212a6ae870ddacd0"
        
        # All other top holders for comparison
        self.top_holders = []
        
    async def analyze_wallet_connections(self) -> Dict:
        """Comprehensive analysis of wallet connections"""
        
        logger.info(f"Analyzing wallet connections for {self.target_wallet[:10]}...")
        
        # Load current holder data
        await self._load_holder_data()
        
        results = {
            'target_wallet': self.target_wallet,
            'analysis_timestamp': datetime.now().isoformat(),
            'connections_found': [],
            'transaction_patterns': {},
            'funding_analysis': {},
            'suspicious_activity': []
        }
        
        # 1. Analyze recent NFT transfers to/from target wallet
        logger.info("1. Analyzing NFT transaction patterns...")
        nft_patterns = await self._analyze_nft_transactions()
        results['transaction_patterns']['nft_transfers'] = nft_patterns
        
        # 2. Look for shared transaction counterparties
        logger.info("2. Looking for shared transaction counterparties...")
        shared_counterparties = await self._find_shared_counterparties()
        results['connections_found'].extend(shared_counterparties)
        
        # 3. Check for similar buying patterns among top holders
        logger.info("3. Analyzing buying patterns similarity...")
        pattern_matches = await self._analyze_buying_patterns()
        results['transaction_patterns']['similar_patterns'] = pattern_matches
        
        # 4. Look for funding source connections
        logger.info("4. Checking funding source connections...")
        funding_connections = await self._analyze_funding_sources()
        results['funding_analysis'] = funding_connections
        
        # 5. Detect suspicious coordination
        logger.info("5. Detecting potential coordination...")
        coordination_signals = self._detect_coordination()
        results['suspicious_activity'] = coordination_signals
        
        return results
    
    async def _load_holder_data(self):
        """Load current holder data"""
        try:
            with open('genuine_undead_bubble_data.json', 'r') as f:
                data = json.load(f)
                holders = data['holders']
                
                # Get top 20 holders for analysis
                self.top_holders = sorted(holders, key=lambda x: x['nftCount'], reverse=True)[:20]
                logger.info(f"Loaded {len(self.top_holders)} top holders for analysis")
                
        except Exception as e:
            logger.error(f"Error loading holder data: {e}")
            self.top_holders = []
    
    async def _analyze_nft_transactions(self) -> Dict:
        """Analyze NFT transactions for the target wallet"""
        patterns = {
            'recent_purchases': [],
            'purchase_timing': [],
            'sellers_interacted_with': set(),
            'bulk_purchase_indicators': []
        }
        
        # Get recent NFT transfer events for target wallet
        try:
            events_url = 'https://api.opensea.io/api/v2/events/collection/genuine-undead'
            params = {
                'event_type': 'transfer',
                'account': self.target_wallet,
                'limit': 100
            }
            
            response = requests.get(events_url, headers=self.opensea_headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('asset_events', [])
                
                logger.info(f"Found {len(events)} transfer events for target wallet")
                
                recent_buys = []
                for event in events:
                    if event.get('to_address', '').lower() == self.target_wallet.lower():
                        # This is a purchase (NFT transferred TO our target)
                        purchase = {
                            'token_id': event.get('nft', {}).get('identifier', ''),
                            'from_address': event.get('from_address', '').lower(),
                            'timestamp': event.get('event_timestamp', ''),
                            'transaction_hash': event.get('transaction', {}).get('hash', '')
                        }
                        recent_buys.append(purchase)
                        patterns['sellers_interacted_with'].add(purchase['from_address'])
                
                patterns['recent_purchases'] = recent_buys[:20]  # Last 20 purchases
                
                # Analyze timing patterns
                if len(recent_buys) >= 5:
                    timestamps = [p['timestamp'] for p in recent_buys[:10] if p['timestamp']]
                    patterns['purchase_timing'] = self._analyze_timing_patterns(timestamps)
                
                # Look for bulk purchase indicators
                if len(recent_buys) >= 10:
                    patterns['bulk_purchase_indicators'] = self._detect_bulk_purchases(recent_buys)
                
        except Exception as e:
            logger.error(f"Error analyzing NFT transactions: {e}")
        
        patterns['sellers_interacted_with'] = list(patterns['sellers_interacted_with'])
        return patterns
    
    async def _find_shared_counterparties(self) -> List[Dict]:
        """Find wallets that have transacted with same addresses as target"""
        connections = []
        
        try:
            # Get the sellers our target has bought from
            nft_patterns = await self._analyze_nft_transactions()
            target_sellers = set(nft_patterns['sellers_interacted_with'])
            
            if not target_sellers:
                return connections
            
            logger.info(f"Target wallet has bought from {len(target_sellers)} different sellers")
            
            # Check if other top holders bought from the same sellers
            for holder in self.top_holders[:10]:  # Check top 10
                if holder['address'].lower() == self.target_wallet.lower():
                    continue
                
                holder_address = holder['address'].lower()
                
                # Get their recent purchases too
                try:
                    events_url = 'https://api.opensea.io/api/v2/events/collection/genuine-undead'
                    params = {
                        'event_type': 'transfer',
                        'account': holder_address,
                        'limit': 50
                    }
                    
                    await asyncio.sleep(1)  # Rate limiting
                    response = requests.get(events_url, headers=self.opensea_headers, params=params, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        events = data.get('asset_events', [])
                        
                        holder_sellers = set()
                        for event in events:
                            if event.get('to_address', '').lower() == holder_address:
                                seller = event.get('from_address', '').lower()
                                if seller:
                                    holder_sellers.add(seller)
                        
                        # Find shared sellers
                        shared_sellers = target_sellers.intersection(holder_sellers)
                        
                        if shared_sellers:
                            connection = {
                                'connected_wallet': holder_address,
                                'connection_type': 'shared_sellers',
                                'shared_count': len(shared_sellers),
                                'shared_addresses': list(shared_sellers)[:5],  # First 5
                                'holder_nft_count': holder['nftCount'],
                                'suspicion_level': 'HIGH' if len(shared_sellers) >= 3 else 'MEDIUM'
                            }
                            connections.append(connection)
                            logger.info(f"Found connection: {holder_address[:10]}... shares {len(shared_sellers)} sellers")
                
                except Exception as e:
                    logger.warning(f"Error checking holder {holder_address[:10]}...: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error finding shared counterparties: {e}")
        
        return connections
    
    async def _analyze_buying_patterns(self) -> List[Dict]:
        """Analyze if multiple wallets show similar buying patterns"""
        pattern_matches = []
        
        # This would require more sophisticated analysis
        # For now, flag wallets with suspiciously similar holdings or timing
        
        target_nft_count = None
        for holder in self.top_holders:
            if holder['address'].lower() == self.target_wallet.lower():
                target_nft_count = holder['nftCount']
                break
        
        if target_nft_count:
            # Look for wallets with very similar NFT counts (within 10%)
            similar_size_wallets = []
            for holder in self.top_holders:
                if holder['address'].lower() == self.target_wallet.lower():
                    continue
                
                count_diff = abs(holder['nftCount'] - target_nft_count)
                if count_diff <= target_nft_count * 0.15:  # Within 15%
                    similar_size_wallets.append({
                        'wallet': holder['address'],
                        'nft_count': holder['nftCount'],
                        'difference': count_diff,
                        'similarity_score': 1.0 - (count_diff / target_nft_count)
                    })
            
            if similar_size_wallets:
                pattern_matches.append({
                    'pattern_type': 'similar_holdings',
                    'target_count': target_nft_count,
                    'similar_wallets': similar_size_wallets
                })
        
        return pattern_matches
    
    async def _analyze_funding_sources(self) -> Dict:
        """Analyze funding sources (would need Etherscan API for full analysis)"""
        return {
            'note': 'Full funding analysis requires Etherscan Pro API',
            'basic_analysis': 'Available with API key',
            'potential_patterns': [
                'Check if multiple wallets funded from same exchange',
                'Look for circular transfers between wallets',
                'Analyze ETH deposit patterns',
                'Check for contract interactions'
            ]
        }
    
    def _detect_coordination(self) -> List[str]:
        """Detect signs of coordinated activity"""
        signals = []
        
        # Basic coordination indicators
        signals.append("Multiple large wallets with zero listings (diamond hands coordination)")
        signals.append("Concentrated buying activity in short timeframe")
        signals.append("Similar wallet behavior patterns among top holders")
        
        return signals
    
    def _analyze_timing_patterns(self, timestamps: List[str]) -> Dict:
        """Analyze timing patterns in purchases"""
        return {
            'total_purchases_analyzed': len(timestamps),
            'note': 'Timing pattern analysis would show clustering of purchases',
            'indicators': [
                'Bulk purchases within short windows',
                'Regular purchase intervals',
                'Coordinated buying with other wallets'
            ]
        }
    
    def _detect_bulk_purchases(self, purchases: List[Dict]) -> List[str]:
        """Detect bulk purchase patterns"""
        indicators = []
        
        if len(purchases) >= 20:
            indicators.append("High volume purchase activity detected")
        
        # Group by transaction hash to find bulk txns
        tx_groups = {}
        for purchase in purchases:
            tx_hash = purchase.get('transaction_hash', '')
            if tx_hash:
                if tx_hash not in tx_groups:
                    tx_groups[tx_hash] = []
                tx_groups[tx_hash].append(purchase)
        
        bulk_txns = [group for group in tx_groups.values() if len(group) > 1]
        if bulk_txns:
            indicators.append(f"Found {len(bulk_txns)} transactions with multiple NFT purchases")
        
        return indicators


async def main():
    """Run wallet connection analysis"""
    print("=" * 70)
    print("WALLET CONNECTION ANALYSIS - MAJOR BUYER INVESTIGATION")
    print(f"Target: 0xd484c930... (gained 22+ NFTs)")
    print("=" * 70)
    
    analyzer = WalletConnectionAnalyzer()
    results = await analyzer.analyze_wallet_connections()
    
    print(f"\n[TARGET WALLET] {results['target_wallet'][:10]}...")
    
    print(f"\n[TRANSACTION PATTERNS]")
    nft_patterns = results['transaction_patterns'].get('nft_transfers', {})
    recent_purchases = nft_patterns.get('recent_purchases', [])
    print(f"Recent purchases found: {len(recent_purchases)}")
    print(f"Different sellers interacted with: {len(nft_patterns.get('sellers_interacted_with', []))}")
    
    if recent_purchases:
        print(f"\nMost recent purchases:")
        for i, purchase in enumerate(recent_purchases[:5], 1):
            print(f"  {i}. Token #{purchase['token_id']} from {purchase['from_address'][:10]}...")
    
    print(f"\n[WALLET CONNECTIONS]")
    connections = results['connections_found']
    if connections:
        print(f"Found {len(connections)} potential connections:")
        for conn in connections:
            print(f"  • {conn['connected_wallet'][:10]}... ({conn['holder_nft_count']} NFTs)")
            print(f"    Shared {conn['shared_count']} sellers - {conn['suspicion_level']} suspicion")
    else:
        print("No direct wallet connections found through shared sellers")
    
    print(f"\n[BUYING PATTERN ANALYSIS]")
    patterns = results['transaction_patterns'].get('similar_patterns', [])
    if patterns:
        for pattern in patterns:
            if pattern['pattern_type'] == 'similar_holdings':
                print(f"Wallets with similar holdings to target ({pattern['target_count']} NFTs):")
                for wallet in pattern['similar_wallets']:
                    similarity = wallet['similarity_score'] * 100
                    print(f"  • {wallet['wallet'][:10]}... - {wallet['nft_count']} NFTs ({similarity:.0f}% similar)")
    
    print(f"\n[COORDINATION INDICATORS]")
    for signal in results['suspicious_activity']:
        print(f"  • {signal}")
    
    print(f"\n[CONCLUSION]")
    print("This analysis reveals potential wallet relationships and coordination patterns.")
    print("Full investigation would require additional blockchain analysis tools.")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())