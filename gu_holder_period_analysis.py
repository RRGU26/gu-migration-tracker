#!/usr/bin/env python3
"""
GU Holder Period Analysis - Create buckets based on listing activity
"""
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def analyze_holder_periods():
    """Analyze GU holders and categorize by listing activity periods"""

    # Load existing data
    try:
        with open('genuine_undead_bubble_data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Bubble data not found. Running data collection first...")
        return

    holders = data['holders']
    total_supply = 5322

    # For this analysis, we'll categorize based on current listing behavior
    # Since we don't have historical listing data, we'll use current listings as proxy

    # Category 1: Never Listed / Diamond Hands (no current listings)
    never_listed = [h for h in holders if h['listedCount'] == 0]

    # Category 2: Active Sellers (has current listings)
    active_sellers = [h for h in holders if h['listedCount'] > 0]

    # Further split active sellers by listing intensity
    light_sellers = [h for h in active_sellers if h['listedCount'] <= 2]
    heavy_sellers = [h for h in active_sellers if h['listedCount'] > 2]

    # Calculate NFTs in each category
    never_listed_nfts = sum(h['nftCount'] for h in never_listed)
    light_seller_nfts = sum(h['nftCount'] for h in light_sellers)
    heavy_seller_nfts = sum(h['nftCount'] for h in heavy_sellers)

    # Create analysis data
    categories = [
        {
            'name': 'Diamond Hands\n(Never Listed)',
            'holders': len(never_listed),
            'nfts': never_listed_nfts,
            'color': '#2E8B57'  # Sea Green
        },
        {
            'name': 'Light Sellers\n(1-2 Listed)',
            'holders': len(light_sellers),
            'nfts': light_seller_nfts,
            'color': '#FFD700'  # Gold
        },
        {
            'name': 'Heavy Sellers\n(3+ Listed)',
            'holders': len(heavy_sellers),
            'nfts': heavy_seller_nfts,
            'color': '#DC143C'  # Crimson
        }
    ]

    # Print analysis
    print('=' * 60)
    print('GU HOLDER BEHAVIOR ANALYSIS')
    print('=' * 60)
    print(f'Total Holders: {len(holders):,}')
    print(f'Total NFTs Analyzed: {sum(c["nfts"] for c in categories):,}')
    print()

    for cat in categories:
        holder_pct = (cat['holders'] / len(holders)) * 100
        nft_pct = (cat['nfts'] / sum(c["nfts"] for c in categories)) * 100
        avg_holding = cat['nfts'] / cat['holders'] if cat['holders'] > 0 else 0

        print(f"{cat['name'].replace(chr(10), ' ')}:")
        print(f"  Holders: {cat['holders']:,} ({holder_pct:.1f}%)")
        print(f"  NFTs: {cat['nfts']:,} ({nft_pct:.1f}%)")
        print(f"  Avg Holding: {avg_holding:.1f} NFTs per holder")
        print()

    return categories, holders

def create_holder_visualization(categories):
    """Create visualization of holder behavior"""

    # Set up the plot style
    plt.style.use('dark_background')
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor('#1a1a1a')

    # Color scheme
    colors = [cat['color'] for cat in categories]
    names = [cat['name'] for cat in categories]

    # 1. Holder Distribution Pie Chart
    holder_counts = [cat['holders'] for cat in categories]
    wedges1, texts1, autotexts1 = ax1.pie(holder_counts, labels=names, colors=colors,
                                          autopct='%1.1f%%', startangle=90,
                                          textprops={'fontsize': 10, 'color': 'white'})
    ax1.set_title('Holder Distribution by Behavior', fontsize=14, fontweight='bold', color='white', pad=20)

    # 2. NFT Distribution Pie Chart
    nft_counts = [cat['nfts'] for cat in categories]
    wedges2, texts2, autotexts2 = ax2.pie(nft_counts, labels=names, colors=colors,
                                          autopct='%1.1f%%', startangle=90,
                                          textprops={'fontsize': 10, 'color': 'white'})
    ax2.set_title('NFT Distribution by Holder Behavior', fontsize=14, fontweight='bold', color='white', pad=20)

    # 3. Bar Chart - Holders vs NFTs
    x = np.arange(len(categories))
    width = 0.35

    ax3.bar(x - width/2, holder_counts, width, label='Holders', color=colors, alpha=0.8)
    ax3_twin = ax3.twinx()
    ax3_twin.bar(x + width/2, nft_counts, width, label='NFTs', color=colors, alpha=0.6)

    ax3.set_xlabel('Holder Categories', color='white', fontweight='bold')
    ax3.set_ylabel('Number of Holders', color='white', fontweight='bold')
    ax3_twin.set_ylabel('Number of NFTs', color='white', fontweight='bold')
    ax3.set_title('Holders vs NFTs by Category', fontsize=14, fontweight='bold', color='white', pad=20)
    ax3.set_xticks(x)
    ax3.set_xticklabels([name.replace('\n', ' ') for name in names], rotation=45, ha='right')
    ax3.tick_params(colors='white')
    ax3_twin.tick_params(colors='white')
    ax3.legend(loc='upper left')
    ax3_twin.legend(loc='upper right')

    # 4. Average Holdings per Category
    avg_holdings = [cat['nfts']/cat['holders'] if cat['holders'] > 0 else 0 for cat in categories]
    bars = ax4.bar(names, avg_holdings, color=colors, alpha=0.8)

    ax4.set_title('Average NFTs per Holder by Category', fontsize=14, fontweight='bold', color='white', pad=20)
    ax4.set_ylabel('Average NFTs per Holder', color='white', fontweight='bold')
    ax4.tick_params(colors='white')

    # Add value labels on bars
    for bar, avg in zip(bars, avg_holdings):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{avg:.1f}', ha='center', va='bottom', color='white', fontweight='bold')

    plt.xticks(rotation=45, ha='right')

    # Adjust layout and save
    plt.tight_layout()
    plt.savefig('gu_holder_behavior_analysis.png', dpi=300, bbox_inches='tight',
                facecolor='#1a1a1a', edgecolor='none')

    # Also create a summary text file
    with open('gu_holder_analysis_summary.txt', 'w') as f:
        f.write("GU HOLDER BEHAVIOR ANALYSIS SUMMARY\n")
        f.write("="*50 + "\n\n")

        total_holders = sum(cat['holders'] for cat in categories)
        total_nfts = sum(cat['nfts'] for cat in categories)

        f.write(f"Total Holders: {total_holders:,}\n")
        f.write(f"Total NFTs: {total_nfts:,}\n\n")

        for cat in categories:
            holder_pct = (cat['holders'] / total_holders) * 100
            nft_pct = (cat['nfts'] / total_nfts) * 100
            avg_holding = cat['nfts'] / cat['holders'] if cat['holders'] > 0 else 0

            f.write(f"{cat['name'].replace(chr(10), ' ')}:\n")
            f.write(f"  Holders: {cat['holders']:,} ({holder_pct:.1f}%)\n")
            f.write(f"  NFTs: {cat['nfts']:,} ({nft_pct:.1f}%)\n")
            f.write(f"  Avg Holding: {avg_holding:.1f} NFTs per holder\n\n")

    print("Visualization saved as 'gu_holder_behavior_analysis.png'")
    print("Summary saved as 'gu_holder_analysis_summary.txt'")

    return fig

if __name__ == "__main__":
    categories, holders = analyze_holder_periods()
    if categories:
        create_holder_visualization(categories)