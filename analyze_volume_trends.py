#!/usr/bin/env python
"""
GU v2 (Genuine Undead) Volume Trend Analysis

Fetches 90-day sales data from OpenSea API and generates volume analysis.
Combines January data into December for cleaner monthly reporting.

Usage:
    python analyze_volume_trends.py
"""

import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time
import json

OPENSEA_API_KEY = '518c0d7ea6ad4116823f41c5245b1098'
COLLECTION_SLUG = 'genuine-undead'


def fetch_sales(days=90):
    """Fetch all sales from the last N days"""
    headers = {'X-API-KEY': OPENSEA_API_KEY}
    all_sales = []
    next_cursor = None
    cutoff = datetime.now() - timedelta(days=days)

    print(f'Fetching {days}-day sales history...')

    for i in range(30):
        for attempt in range(3):
            try:
                params = {'event_type': 'sale', 'limit': 50}
                if next_cursor:
                    params['next'] = next_cursor
                response = requests.get(
                    f'https://api.opensea.io/api/v2/events/collection/{COLLECTION_SLUG}',
                    headers=headers, params=params, timeout=45
                )
                if response.status_code == 200:
                    break
                time.sleep(2)
            except Exception as e:
                time.sleep(3)
        else:
            print(f'Failed batch {i+1} after 3 attempts')
            break

        if response.status_code != 200:
            print(f'API error: {response.status_code}')
            break

        data = response.json()
        events = data.get('asset_events', [])
        if not events:
            break

        hit_cutoff = False
        for event in events:
            ts = event.get('event_timestamp')
            if isinstance(ts, int):
                dt = datetime.fromtimestamp(ts)
                if dt < cutoff:
                    hit_cutoff = True
                    continue

                payment = event.get('payment', {})
                price_wei = int(payment.get('quantity', 0) or 0)
                price_eth = price_wei / 1e18

                nft = event.get('nft', {})
                token_id = nft.get('identifier', '?')

                all_sales.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'price_eth': price_eth,
                    'datetime': dt,
                    'token_id': token_id
                })

        if hit_cutoff:
            break

        next_cursor = data.get('next')
        if not next_cursor:
            break

        time.sleep(0.5)

    print(f'Found {len(all_sales)} sales')
    return all_sales


def analyze_volume(all_sales, combine_current_month=True):
    """Analyze volume by month and week"""

    # Monthly aggregation
    monthly_volume = defaultdict(float)
    monthly_count = defaultdict(int)

    # Weekly aggregation
    weekly_volume = defaultdict(float)
    weekly_count = defaultdict(int)

    # Daily aggregation (last 7 days)
    daily_volume = defaultdict(float)
    daily_count = defaultdict(int)
    daily_sales = defaultdict(list)

    now = datetime.now()

    for sale in all_sales:
        dt = sale['datetime']

        # Monthly - combine current month into previous if requested
        month = dt.strftime('%Y-%m')
        if combine_current_month and month == now.strftime('%Y-%m'):
            # Roll into previous month
            prev = (now.replace(day=1) - timedelta(days=1))
            month = prev.strftime('%Y-%m')
        monthly_volume[month] += sale['price_eth']
        monthly_count[month] += 1

        # Weekly
        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime('%Y-%m-%d')
        weekly_volume[week_key] += sale['price_eth']
        weekly_count[week_key] += 1

        # Daily (last 7 days)
        if dt > now - timedelta(days=7):
            day = sale['date']
            daily_volume[day] += sale['price_eth']
            daily_count[day] += 1
            if sale['price_eth'] >= 0.3:
                daily_sales[day].append(sale)

    return {
        'monthly_volume': dict(monthly_volume),
        'monthly_count': dict(monthly_count),
        'weekly_volume': dict(weekly_volume),
        'weekly_count': dict(weekly_count),
        'daily_volume': dict(daily_volume),
        'daily_count': dict(daily_count),
        'daily_sales': {k: [{'token_id': s['token_id'], 'price_eth': s['price_eth']} for s in v]
                        for k, v in daily_sales.items()}
    }


def print_report(all_sales, analysis):
    """Print formatted analysis report"""

    print()
    print('=' * 60)
    print('GU v2 (GENUINE UNDEAD) - 90 DAY VOLUME ANALYSIS')
    print(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 60)
    print()

    # Big sales
    big_sales = [s for s in all_sales if s['price_eth'] >= 0.5]
    if big_sales:
        print(f'BIG SALES (>0.5 ETH): {len(big_sales)} total')
        print('-' * 40)
        for s in sorted(big_sales, key=lambda x: x['price_eth'], reverse=True)[:10]:
            print(f"  {s['datetime'].strftime('%m/%d')}  #{s['token_id']:<5}  {s['price_eth']:>7.4f} ETH")
        print()

    # Monthly chart
    monthly_volume = analysis['monthly_volume']
    monthly_count = analysis['monthly_count']

    if monthly_volume:
        print('MONTHLY VOLUME')
        print('-' * 60)

        max_vol = max(monthly_volume.values())
        for month in sorted(monthly_volume.keys()):
            vol = monthly_volume[month]
            count = monthly_count[month]
            bar_len = int((vol / max_vol) * 40)
            bar = '#' * bar_len

            dt = datetime.strptime(month, '%Y-%m')
            month_name = dt.strftime('%b %Y')

            print(f'{month_name:<10} {bar} {vol:.1f} ETH ({count} sales)')
        print()

    # Weekly trend
    weekly_volume = analysis['weekly_volume']
    weekly_count = analysis['weekly_count']

    if weekly_volume:
        print('WEEKLY TREND')
        print('-' * 60)

        max_vol = max(weekly_volume.values())
        weeks = sorted(weekly_volume.keys(), reverse=True)

        for week in weeks[:13]:
            vol = weekly_volume[week]
            count = weekly_count[week]
            bar_len = int((vol / max_vol) * 30)
            bar = '#' * bar_len
            print(f'{week}  {vol:>7.2f} ETH  {count:>4} sales  {bar}')
        print()

    # Last 7 days
    daily_volume = analysis['daily_volume']
    daily_count = analysis['daily_count']
    daily_sales = analysis['daily_sales']

    if daily_volume:
        print('LAST 7 DAYS')
        print('-' * 40)
        for day in sorted(daily_volume.keys(), reverse=True):
            vol = daily_volume[day]
            count = daily_count[day]
            bar = '#' * int(vol * 5)
            note = ''
            if day in daily_sales:
                note = ' <- ' + ', '.join([f"#{s['token_id']}:{s['price_eth']:.2f}" for s in daily_sales[day]])
            print(f"{day}  {vol:>6.2f} ETH  {count:>2} sales  {bar}{note}")
        print()

    # Totals
    total_vol = sum(monthly_volume.values())
    total_sales = len(all_sales)
    total_big = sum(s['price_eth'] for s in big_sales)

    print('TOTALS')
    print('-' * 40)
    print(f'Total Volume:     {total_vol:>8.2f} ETH')
    print(f'Total Sales:      {total_sales:>8}')
    print(f'Avg Sale Price:   {total_vol/max(total_sales,1):>8.4f} ETH')
    if big_sales:
        print(f'Big Sales Vol:    {total_big:>8.2f} ETH ({total_big/total_vol*100:.0f}%)')
    print()

    # MoM changes
    months = sorted(monthly_volume.keys())
    if len(months) >= 2:
        print('MONTH-OVER-MONTH')
        print('-' * 40)
        for i in range(1, len(months)):
            prev = monthly_volume[months[i-1]]
            curr = monthly_volume[months[i]]
            if prev > 0:
                change = ((curr / prev) - 1) * 100
                arrow = '^' if change > 0 else 'v'
                print(f'  {months[i-1]} -> {months[i]}: {arrow} {abs(change):.0f}%')


def save_data(all_sales, analysis, filename='data/volume_analysis.json'):
    """Save analysis data to JSON"""
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_sales': len(all_sales),
        'analysis': analysis,
        'big_sales': [
            {
                'date': s['date'],
                'token_id': s['token_id'],
                'price_eth': s['price_eth']
            }
            for s in all_sales if s['price_eth'] >= 0.5
        ]
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)

    print(f'Data saved to {filename}')


def main():
    # Fetch sales data
    all_sales = fetch_sales(days=90)

    if not all_sales:
        print('No sales data found')
        return

    # Analyze
    analysis = analyze_volume(all_sales, combine_current_month=True)

    # Print report
    print_report(all_sales, analysis)

    # Save data
    save_data(all_sales, analysis)


if __name__ == '__main__':
    main()
