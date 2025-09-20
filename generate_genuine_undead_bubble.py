#!/usr/bin/env python3
"""
Generate bubble chart data specifically for Genuine Undead collection
Ensures complete coverage of all 5300 NFTs
"""
import asyncio
import json
import os
import sys
from datetime import date, datetime

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.append(src_dir)

from services.complete_holder_fetcher import CompleteHolderFetcher
from services.active_listing_tracker import ActiveListingTracker

async def generate_genuine_undead_bubble_data():
    """Generate comprehensive bubble chart data for Genuine Undead only"""
    
    print("=" * 70)
    print("GENERATING BUBBLE CHART DATA FOR GENUINE UNDEAD")
    print("Target: Complete coverage of 5300 NFTs")
    print("=" * 70)
    
    try:
        # Initialize services
        holder_fetcher = CompleteHolderFetcher()
        listing_tracker = ActiveListingTracker()
        
        print("\n1. Getting complete holder data for Genuine Undead...")
        holder_results = await holder_fetcher.fetch_all_holders_via_listings()
        
        print("\n2. Getting active listing data...")
        listing_results = await listing_tracker.get_active_listings()
        
        # Create comprehensive dataset for bubble chart
        bubble_data = []
        
        # Process holder data
        holders = holder_results.get('holders', [])
        
        # Get listing data for Genuine Undead
        listing_data = listing_results.get('collections', {}).get('undead', {})
        listing_sellers = listing_data.get('sellers', {})
        
        print(f"\n3. Processing {len(holders)} holders...")
        
        # Create bubble data for each holder
        for holder in holders:
            holder_address = holder.get('wallet_address', '').lower()
            nft_count = holder.get('nft_count', 0)
            
            # Get listing details from listing tracker
            listed_count = 0
            listing_value_eth = 0
            floor_listings = 0
            
            if holder_address in listing_sellers:
                seller_data = listing_sellers[holder_address]
                listed_count = len(seller_data.get('listings', []))
                listing_value_eth = seller_data.get('total_value_eth', 0)
                
                # Count floor listings
                for listing in seller_data.get('listings', []):
                    if listing.get('is_floor_listing', False):
                        floor_listings += 1
            
            # We already have listed_ids from the holder data
            listed_from_holder = len(holder.get('listed_ids', []))
            if listed_from_holder > listed_count:
                listed_count = listed_from_holder
            
            # Calculate listing rate
            listing_rate = (listed_count / nft_count * 100) if nft_count > 0 else 0
            
            # Determine holder category
            holder_category = categorize_holder(nft_count, listing_rate, listed_count)
            
            # Add to bubble data
            bubble_item = {
                'address': holder_address,
                'nftCount': nft_count,
                'listedCount': listed_count,
                'listingRate': round(listing_rate, 2),
                'listingValueEth': round(listing_value_eth, 4),
                'floorListings': floor_listings,
                'collection': 'genuine-undead',
                'category': holder_category,
                'isWhale': nft_count >= 20,  # 20+ for Genuine Undead whales
                'isActiveSeller': listed_count > 0,
                'isFloorSeller': floor_listings > 0,
                'nftIds': holder.get('nft_ids', [])[:10]  # First 10 IDs for reference
            }
            
            bubble_data.append(bubble_item)
        
        # Calculate summary statistics
        summary_stats = calculate_summary_stats(bubble_data, holder_results)
        
        # Prepare final dataset
        chart_data = {
            'timestamp': datetime.now().isoformat(),
            'date': date.today().isoformat(),
            'collection': 'genuine-undead',
            'total_supply': 5300,
            'tokens_found': holder_results.get('tokens_found', 0),
            'coverage_percent': holder_results.get('coverage_percent', 0),
            'summary': summary_stats,
            'holders': bubble_data
        }
        
        # Save to JSON file
        output_file = os.path.join(current_dir, 'genuine_undead_bubble_data.json')
        with open(output_file, 'w') as f:
            json.dump(chart_data, f, indent=2)
        
        print(f"\n[SUCCESS] Genuine Undead bubble chart data generated!")
        print(f"[FILE] Saved to: {output_file}")
        print(f"[COVERAGE] {holder_results.get('tokens_found', 0)}/{5300} NFTs tracked ({holder_results.get('coverage_percent', 0):.1f}%)")
        print(f"[DATA] {len(bubble_data)} holders processed")
        print(f"[STATS] {summary_stats['activeListers']} active sellers")
        print(f"[STATS] {summary_stats['whaleHolders']} whale holders (20+ NFTs)")
        print(f"[STATS] {summary_stats['totalNFTs']} total NFTs tracked")
        print(f"[STATS] {summary_stats['listedNFTs']} listed NFTs")
        print(f"[STATS] {summary_stats['avgListingRate']:.1f}% average listing rate")
        
        return chart_data
        
    except Exception as e:
        print(f"[ERROR] Failed to generate bubble chart data: {e}")
        import traceback
        traceback.print_exc()
        return None

def categorize_holder(nft_count, listing_rate, listed_count):
    """Categorize holder based on holdings and listing behavior"""
    
    # Adjusted thresholds for Genuine Undead
    is_whale = nft_count >= 20  # 20+ NFTs is whale for this collection
    high_listing_rate = listing_rate >= 25
    
    if is_whale and not high_listing_rate:
        return "whale_holder"  # 🐋 Whale Holder
    elif is_whale and high_listing_rate:
        return "active_seller"  # 🔥 Active Seller  
    elif not is_whale and not high_listing_rate:
        return "diamond_hands"  # 💎 Diamond Hands
    elif not is_whale and high_listing_rate:
        return "small_trader"  # 📈 Small Trader
    else:
        return "regular_holder"

def calculate_summary_stats(bubble_data, holder_results):
    """Calculate summary statistics for the dashboard"""
    
    if not bubble_data:
        return {
            'totalHolders': 0,
            'activeListers': 0,
            'whaleHolders': 0,
            'avgListingRate': 0,
            'totalNFTs': 0,
            'listedNFTs': 0,
            'totalListingValue': 0,
            'categoryCounts': {},
            'coverageStats': {}
        }
    
    total_holders = len(bubble_data)
    active_listers = len([h for h in bubble_data if h['listedCount'] > 0])
    whale_holders = len([h for h in bubble_data if h['isWhale']])
    
    total_nfts = sum(h['nftCount'] for h in bubble_data)
    listed_nfts = sum(h['listedCount'] for h in bubble_data)
    total_listing_value = sum(h['listingValueEth'] for h in bubble_data)
    
    # Calculate average listing rate (only for active listers)
    active_listers_data = [h for h in bubble_data if h['listedCount'] > 0]
    avg_listing_rate = sum(h['listingRate'] for h in active_listers_data) / len(active_listers_data) if active_listers_data else 0
    
    # Category counts
    category_counts = {}
    for holder in bubble_data:
        category = holder['category']
        category_counts[category] = category_counts.get(category, 0) + 1
    
    # Coverage stats
    coverage_stats = {
        'tokens_found': holder_results.get('tokens_found', 0),
        'total_supply': 5300,
        'coverage_percent': holder_results.get('coverage_percent', 0)
    }
    
    return {
        'totalHolders': total_holders,
        'activeListers': active_listers,
        'whaleHolders': whale_holders,
        'avgListingRate': round(avg_listing_rate, 2),
        'totalNFTs': total_nfts,
        'listedNFTs': listed_nfts,
        'totalListingValue': round(total_listing_value, 4),
        'categoryCounts': category_counts,
        'listingPercentage': round((listed_nfts / total_nfts * 100) if total_nfts > 0 else 0, 2),
        'coverageStats': coverage_stats
    }

async def main():
    """Generate and display bubble chart data"""
    data = await generate_genuine_undead_bubble_data()
    
    if data:
        print("\n" + "=" * 50)
        print("GENUINE UNDEAD BUBBLE CHART DATA PREVIEW:")
        print("=" * 50)
        
        # Show coverage
        coverage = data.get('coverage_percent', 0)
        print(f"\nCOVERAGE: {data.get('tokens_found', 0)}/5300 NFTs ({coverage:.1f}%)")
        
        # Show sample holders
        sample_holders = data['holders'][:5]
        for i, holder in enumerate(sample_holders, 1):
            print(f"\n{i}. {holder['address'][:10]}...")
            print(f"   NFTs: {holder['nftCount']}, Listed: {holder['listedCount']} ({holder['listingRate']}%)")
            print(f"   Category: {holder['category']}")
            print(f"   Value: {holder['listingValueEth']} ETH")
        
        print(f"\n[TOTAL] {len(data['holders'])} holders ready for visualization")

if __name__ == "__main__":
    asyncio.run(main())