#!/usr/bin/env python3
"""
Investigate NFT Supply Variance
"""
import json

def investigate_supply_variance():
    """Investigate why we have 6,038 NFTs when supply is 5,322"""

    print("NFT SUPPLY VARIANCE INVESTIGATION")
    print("=" * 50)

    # Load the data
    with open('genuine_undead_bubble_data.json', 'r') as f:
        data = json.load(f)

    holders = data.get('holders', [])

    # Calculate totals
    total_nfts_in_data = sum(h.get('nftCount', 0) for h in holders)
    total_holders = len(holders)

    print(f"Data Summary:")
    print(f"  Total holders: {total_holders:,}")
    print(f"  Total NFTs counted: {total_nfts_in_data:,}")
    print(f"  Known GU supply: 5,322")
    print(f"  Variance: {total_nfts_in_data - 5322}")

    # Check the collection stats from the data file
    collection_info = data.get('collection', {})
    print(f"\nCollection Info from data:")
    if isinstance(collection_info, dict):
        print(f"  Name: {collection_info.get('name', 'N/A')}")
        print(f"  Slug: {collection_info.get('slug', 'N/A')}")
    else:
        print(f"  Collection: {collection_info}")

    # Analyze large holders to see if there are obvious outliers
    print(f"\nTop 10 Largest Holders:")
    sorted_holders = sorted(holders, key=lambda x: x.get('nftCount', 0), reverse=True)

    top_10_nfts = 0
    for i, holder in enumerate(sorted_holders[:10]):
        nft_count = holder.get('nftCount', 0)
        listed_count = holder.get('listedCount', 0)
        wallet = holder.get('wallet', 'N/A')[:10] + '...'
        print(f"  {i+1:2d}. {wallet} - {nft_count:3d} NFTs ({listed_count} listed)")
        top_10_nfts += nft_count

    print(f"\nTop 10 holders control: {top_10_nfts:,} NFTs ({top_10_nfts/total_nfts_in_data*100:.1f}%)")

    # Check if any holder has more NFTs than reasonable
    massive_holders = [h for h in holders if h.get('nftCount', 0) > 100]
    print(f"\nHolders with 100+ NFTs: {len(massive_holders)}")

    if massive_holders:
        print("Large holders breakdown:")
        for holder in massive_holders:
            wallet = holder.get('wallet', 'N/A')[:10] + '...'
            nft_count = holder.get('nftCount', 0)
            print(f"  {wallet}: {nft_count} NFTs")

    # Calculate what the supply should be based on coverage
    # From logs: 4,798 unique NFTs found (90.5% coverage)
    unique_nfts_found = 4798
    coverage_percent = 90.5

    # Estimate total supply based on coverage
    estimated_supply = int(unique_nfts_found / (coverage_percent / 100))

    print(f"\nCoverage Analysis:")
    print(f"  Unique NFTs found: {unique_nfts_found:,}")
    print(f"  Coverage reported: {coverage_percent}%")
    print(f"  Estimated total supply: {estimated_supply:,}")
    print(f"  Known supply: 5,322")
    print(f"  Estimation error: {abs(estimated_supply - 5322)} NFTs")

    # The issue might be that some NFTs are counted multiple times
    # or there are cross-collection NFTs included

    print(f"\nPossible Explanations for Variance:")
    print(f"1. Multi-collection data mixing")
    print(f"2. NFTs counted multiple times in transfers")
    print(f"3. Burned/invalid NFTs still being counted")
    print(f"4. API returning duplicate entries")

    # For posting purposes, let's calculate the corrected percentages
    # using the known supply instead of our inflated numbers

    never_listed = [h for h in holders if h.get('listedCount', 0) == 0]
    light_sellers = [h for h in holders if 1 <= h.get('listedCount', 0) <= 2]
    heavy_sellers = [h for h in holders if h.get('listedCount', 0) > 2]

    # Calculate NFTs held by each category
    never_listed_nfts = sum(h.get('nftCount', 0) for h in never_listed)
    light_seller_nfts = sum(h.get('nftCount', 0) for h in light_sellers)
    heavy_seller_nfts = sum(h.get('nftCount', 0) for h in heavy_sellers)

    # Use proportional adjustment to match known supply
    adjustment_factor = 5322 / total_nfts_in_data

    adjusted_never_listed = int(never_listed_nfts * adjustment_factor)
    adjusted_light_seller = int(light_seller_nfts * adjustment_factor)
    adjusted_heavy_seller = int(heavy_seller_nfts * adjustment_factor)

    print(f"\nADJUSTED NUMBERS FOR POSTING:")
    print(f"Total Supply Used: 5,322 (known accurate)")
    print(f"")
    print(f"Diamond Hands (Never Listed):")
    print(f"  Holders: {len(never_listed):,} ({len(never_listed)/total_holders*100:.1f}%)")
    print(f"  NFTs: {adjusted_never_listed:,} ({adjusted_never_listed/5322*100:.1f}%)")
    print(f"")
    print(f"Light Sellers (1-2 Listed):")
    print(f"  Holders: {len(light_sellers):,} ({len(light_sellers)/total_holders*100:.1f}%)")
    print(f"  NFTs: {adjusted_light_seller:,} ({adjusted_light_seller/5322*100:.1f}%)")
    print(f"")
    print(f"Heavy Sellers (3+ Listed):")
    print(f"  Holders: {len(heavy_sellers):,} ({len(heavy_sellers)/total_holders*100:.1f}%)")
    print(f"  NFTs: {adjusted_heavy_seller:,} ({adjusted_heavy_seller/5322*100:.1f}%)")

    return {
        'total_holders': total_holders,
        'never_listed': len(never_listed),
        'light_sellers': len(light_sellers),
        'heavy_sellers': len(heavy_sellers),
        'adjusted_never_listed_nfts': adjusted_never_listed,
        'adjusted_light_seller_nfts': adjusted_light_seller,
        'adjusted_heavy_seller_nfts': adjusted_heavy_seller
    }

if __name__ == "__main__":
    investigate_supply_variance()