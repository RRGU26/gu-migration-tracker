#!/usr/bin/env python3
"""
Generate conviction table and quadrant map visualizations
Similar to BLOXX's charts with GU added
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json

import os

# Load results
script_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(script_dir, 'conviction_results.json'), 'r') as f:
    results = json.load(f)

collections = results['rankings']

# Color scheme
COLORS = {
    'Genuine Undead': '#8B0000',  # Dark red for GU
    'default': '#1f77b4'  # Blue for others
}


def generate_quadrant_map():
    """Generate the NFT Conviction Quadrant Map"""
    fig, ax = plt.subplots(figsize=(12, 10))

    # Plot each collection
    for c in collections:
        x, y = c['7d'], c['30d']
        color = COLORS.get(c['name'], COLORS['default'])
        size = 100 if c['name'] == 'Genuine Undead' else 60

        ax.scatter(x, y, s=size, c=color, zorder=5)

        # Label positioning
        offset_x, offset_y = 1.5, 0.5
        if c['name'] == 'Genuine Undead':
            offset_x, offset_y = 2, 1
            ax.annotate(c['name'], (x, y), xytext=(x + offset_x, y + offset_y),
                       fontsize=11, fontweight='bold', color=color)
        else:
            ax.annotate(c['name'], (x, y), xytext=(x + offset_x, y + offset_y),
                       fontsize=9, color='#333333')

    # Quadrant lines
    ax.axvline(x=50, color='#00CED1', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.axhline(y=40, color='#00CED1', linestyle='--', linewidth=1.5, alpha=0.8)

    # Axis settings
    ax.set_xlim(30, 95)
    ax.set_ylim(20, 65)
    ax.set_xlabel('7-Day Hold % (Entry Conviction)', fontsize=12)
    ax.set_ylabel('30-Day Hold % (Retention Strength)', fontsize=12)
    ax.set_title('NFT Conviction Quadrant Map', fontsize=16, fontweight='bold')

    # Grid
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#fafafa')

    plt.tight_layout()
    output_path = os.path.join(script_dir, 'conviction_quadrant_map.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()


def generate_table():
    """Generate the conviction rankings table with diamond hands"""
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axis('off')

    # Table data - include diamond hands
    headers = ['Rank', 'Project', '7d Hold %', '30d Hold %', 'Diamond Hands %', 'Combined Score']
    table_data = []

    # Sort by score (those with scores first)
    sorted_collections = sorted(collections, key=lambda x: (x.get('score') is not None, x.get('score') or 0), reverse=True)

    for i, c in enumerate(sorted_collections, 1):
        dh = c.get('diamond_hands')
        score = c.get('score')
        row = [
            str(i),
            c['name'],
            f"{c['7d']}",
            f"{c['30d']}",
            f"{dh:.1f}" if dh else "N/A",
            f"{score:.1f}" if score else "N/A"
        ]
        table_data.append(row)

    # Create table
    table = ax.table(
        cellText=table_data,
        colLabels=headers,
        cellLoc='center',
        loc='center',
        colWidths=[0.08, 0.26, 0.12, 0.12, 0.16, 0.16]
    )

    # Style table
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)

    # Header styling
    for j, header in enumerate(headers):
        cell = table[(0, j)]
        cell.set_facecolor('#4a4a4a')
        cell.set_text_props(color='white', fontweight='bold')

    # Row styling - highlight GU
    for i, c in enumerate(sorted_collections, 1):
        for j in range(len(headers)):
            cell = table[(i, j)]
            if c['name'] == 'Genuine Undead':
                cell.set_facecolor('#ffebee')
                cell.set_text_props(color='#8B0000', fontweight='bold')
            elif i % 2 == 0:
                cell.set_facecolor('#f5f5f5')

    # Title
    ax.set_title('NFT Conviction Rankings with Diamond Hands', fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    output_path = os.path.join(script_dir, 'conviction_table.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()


def main():
    print("Generating conviction visualizations...")
    print()

    generate_quadrant_map()
    generate_table()

    print()
    print("=" * 50)
    print("GENUINE UNDEAD CONVICTION SUMMARY")
    print("=" * 50)

    gu = next(c for c in collections if c['name'] == 'Genuine Undead')

    # Sort by score for ranking
    scored = [c for c in collections if c.get('score')]
    scored.sort(key=lambda x: x['score'], reverse=True)
    gu_rank = next((i+1 for i, c in enumerate(scored) if c['name'] == 'Genuine Undead'), len(collections))

    print(f"7-Day Hold %:     {gu['7d']}%")
    print(f"30-Day Hold %:    {gu['30d']}%")
    print(f"Diamond Hands %:  {gu.get('diamond_hands', 'N/A')}%")
    print(f"Combined Score:   {gu.get('score', 'N/A')}")
    print(f"Rank:             #{gu_rank} of {len(scored)} (with complete data)")

    if gu['7d'] >= 50 and gu['30d'] >= 40:
        quadrant = "TOP-RIGHT (High Conviction)"
    elif gu['7d'] >= 50:
        quadrant = "BOTTOM-RIGHT (High Entry, Low Retention)"
    elif gu['30d'] >= 40:
        quadrant = "TOP-LEFT (Low Entry, High Retention)"
    else:
        quadrant = "BOTTOM-LEFT (Low Conviction)"

    print(f"Quadrant:      {quadrant}")
    print()
    print("Files generated:")
    print("  - conviction_quadrant_map.png")
    print("  - conviction_table.png")


if __name__ == '__main__':
    main()
