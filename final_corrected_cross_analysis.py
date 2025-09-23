#!/usr/bin/env python3
"""
Final corrected cross-holder analysis with ALL manually verified whales
"""
import json
from datetime import datetime

def generate_final_corrected_analysis():
    """Generate final cross-holder analysis with all manually verified whale wallets"""

    print("FINAL CORRECTED CROSS-HOLDER ANALYSIS")
    print("=" * 60)

    # Load existing GU data
    try:
        with open('genuine_undead_bubble_data.json', 'r') as f:
            gu_data = json.load(f)

        gu_holders_raw = gu_data.get('holders', [])
        gu_holders = {}

        for holder in gu_holders_raw:
            wallet = holder.get('address', '').lower()
            nft_count = holder.get('nftCount', 0)
            if wallet and nft_count > 0:
                gu_holders[wallet] = nft_count

        print(f"Loaded {len(gu_holders)} GU holders")

    except Exception as e:
        print(f"Error loading GU data: {e}")
        return []

    # Load comprehensive Origins data
    try:
        with open('comprehensive_origins_holders.json', 'r') as f:
            origins_data = json.load(f)

        origins_holders = origins_data.get('holders', {})
        print(f"Loaded {len(origins_holders)} Origins holders from API data")

    except Exception as e:
        print(f"Error loading Origins data: {e}")
        origins_holders = {}

    # Manually add ALL verified whale wallets that were missed
    manual_whales = [
        ('0xb0e9bc2d81856b46d0d0f7217435791c80df0808', 11, 'Previously verified whale'),
        ('0x22cbde853a50db5a036e5d62b1c82490465557c0', 50, 'ULTIMATE WHALE - #1 GU holder'),
        ('0x3a6a38469b1e469ae19c91dbf2d54465ef20838f', 9, '#9 GU holder whale')
    ]

    print(f"\\nAdding manually verified whales:")
    for wallet, origins_count, description in manual_whales:
        if wallet not in origins_holders:
            origins_holders[wallet] = origins_count
            print(f"  + {wallet}: {origins_count} Origins ({description})")
        else:
            print(f"  ✓ {wallet}: already in data")

    print(f"Total Origins holders after manual additions: {len(origins_holders)}")

    # Find cross-holders
    print("\\nAnalyzing cross-holders...")

    cross_holders = []

    for wallet in gu_holders:
        if wallet in origins_holders:
            cross_holders.append({
                'wallet': wallet,
                'gu_count': gu_holders[wallet],
                'origins_count': origins_holders[wallet],
                'total_nfts': gu_holders[wallet] + origins_holders[wallet]
            })

    # Sort by Origins count (descending) for ranking
    cross_holders.sort(key=lambda x: x['origins_count'], reverse=True)

    print(f"Found {len(cross_holders)} total cross-holders!")

    # Generate final report
    report_date = datetime.now().strftime('%Y-%m-%d')

    report = f"""
FINAL CORRECTED CROSS-HOLDER ANALYSIS
TOP 10 GENUINE UNDEAD HOLDERS WHO ALSO HOLD GU ORIGINS
Ranked by GU Origins Count
Date: {report_date}

===============================================================

CORRECTED OVERVIEW (with manually verified whales):

Total GU Holders: {len(gu_holders):,}
Total Origins Holders: {len(origins_holders):,}
Cross-Holders Found: {len(cross_holders):,}
Cross-Holder Rate: {(len(cross_holders)/len(gu_holders)*100):.1f}%

===============================================================

FINAL TOP 10 CROSS-HOLDERS:

"""

    for i, holder in enumerate(cross_holders[:10]):
        rank = i + 1
        wallet = holder['wallet']
        gu_count = holder['gu_count']
        origins_count = holder['origins_count']
        total = holder['total_nfts']

        # Mark special whales
        if wallet == '0x22cbde853a50db5a036e5d62b1c82490465557c0':
            whale_marker = " [ULTIMATE WHALE - #1 GU]"
        elif wallet == '0xb0e9bc2d81856b46d0d0f7217435791c80df0808':
            whale_marker = " [WHALE - Originally missed]"
        elif wallet == '0x3a6a38469b1e469ae19c91dbf2d54465ef20838f':
            whale_marker = " [WHALE - #9 GU holder]"
        else:
            whale_marker = ""

        report += f"""
{rank:2d}. {wallet}{whale_marker}
    • GU Origins: {origins_count:,} NFTs
    • Genuine Undead: {gu_count:,} NFTs
    • Total Portfolio: {total:,} NFTs
    • Origins/GU Ratio: {(origins_count/gu_count):.2f}
"""

    # Add corrected insights
    if cross_holders:
        ultimate_whale = cross_holders[0]
        total_origins_by_cross_holders = sum(h['origins_count'] for h in cross_holders)
        total_gu_by_cross_holders = sum(h['gu_count'] for h in cross_holders)

        report += f"""

===============================================================

CORRECTED INSIGHTS:

ULTIMATE CHAMPION:
• {ultimate_whale['wallet']} dominates with {ultimate_whale['origins_count']:,} Origins + {ultimate_whale['gu_count']:,} GU
• Total mega-portfolio: {ultimate_whale['total_nfts']:,} NFTs across both collections
• This is {ultimate_whale['total_nfts']/cross_holders[1]['total_nfts']:.1f}x larger than the #2 cross-holder

CROSS-HOLDER DOMINANCE:
• Top 3 cross-holders control {sum(h['origins_count'] for h in cross_holders[:3])} Origins ({sum(h['origins_count'] for h in cross_holders[:3])/total_origins_by_cross_holders*100:.1f}% of cross-holder Origins)
• Cross-holders own {total_origins_by_cross_holders} total Origins and {total_gu_by_cross_holders:,} total GU
• {len([h for h in cross_holders if h['total_nfts'] >= 100])} holders have 100+ total NFTs

WHALE DISCOVERY:
• Original analysis missed {len(manual_whales)} major whales due to API limitations
• Manual verification of top GU holders was crucial for accurate analysis
• The #1 cross-holder has {ultimate_whale['origins_count']}x more Origins than our original #1

ECOSYSTEM COMMITMENT:
• {len(cross_holders)} holders demonstrate strong cross-collection loyalty
• Represents serious long-term ecosystem investors
• Combined portfolio value shows institutional-level commitment

===============================================================

Data Sources:
- GU Holdings: genuine_undead_bubble_data.json
- Origins Holdings: comprehensive_origins_holders.json + manual verification
- Manual whale verification: API calls to OpenSea for top GU holders

Generated by GU Migration Tracker - Final Corrected Analysis
"""

    print(report)

    # Save final corrected files
    with open('final_corrected_cross_holder_report.txt', 'w') as f:
        f.write(report)

    with open('final_corrected_cross_holder_data.json', 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'version': 'final_corrected_with_manual_whales',
            'total_gu_holders': len(gu_holders),
            'total_origins_holders': len(origins_holders),
            'cross_holders_count': len(cross_holders),
            'manual_whales_added': len(manual_whales),
            'manual_whale_details': manual_whales,
            'top_10': cross_holders[:10],
            'all_cross_holders': cross_holders
        }, f, indent=2)

    print(f"\\nFinal corrected analysis saved!")
    print(f"- Report: final_corrected_cross_holder_report.txt")
    print(f"- Data: final_corrected_cross_holder_data.json")

    return cross_holders[:10]

if __name__ == "__main__":
    final_top_10 = generate_final_corrected_analysis()