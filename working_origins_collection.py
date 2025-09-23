#!/usr/bin/env python3
"""
Working Origins collection using the method that successfully found the whale wallet
"""
import requests
import time
import json
from datetime import datetime

def get_origins_holders_working_method():
    """Get Origins holders using transfer events - the method that actually works"""

    headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}

    print("WORKING ORIGINS HOLDER COLLECTION")
    print("=" * 60)
    print("Using transfer events method (proven to work)...")

    all_holders = {}

    # Use transfer events - this method found our data before
    transfers_url = 'https://api.opensea.io/api/v2/events/collection/gu-origins'

    next_cursor = None
    page = 0

    # Get comprehensive transfer history
    while page < 200:  # Get much more data this time
        page += 1
        params = {
            'event_type': 'transfer',
            'limit': 50
        }
        if next_cursor:
            params['next'] = next_cursor

        try:
            response = requests.get(transfers_url, headers=headers, params=params, timeout=20)

            if response.status_code == 200:
                data = response.json()
                events = data.get('asset_events', [])

                if page % 20 == 0 or page <= 5:  # Report progress
                    print(f"Page {page}: {len(events)} transfer events")

                for event in events:
                    try:
                        # Get recipient (current owner after transfer)
                        to_account = event.get('to_account')
                        if to_account:
                            wallet = to_account.get('address', '').lower()

                            # Get NFT
                            nft = event.get('nft', {})
                            if nft:
                                token_id = nft.get('identifier')

                                if wallet and token_id:
                                    if wallet not in all_holders:
                                        all_holders[wallet] = set()
                                    all_holders[wallet].add(token_id)

                    except Exception as e:
                        continue

                next_cursor = data.get('next')
                if not next_cursor or not events:
                    print(f"Reached end of transfer data at page {page}")
                    break

                time.sleep(0.3)

            else:
                print(f"API error: {response.status_code}")
                if response.status_code == 429:
                    print("Rate limited - waiting...")
                    time.sleep(5)
                    continue
                break

        except Exception as e:
            print(f"Error on page {page}: {e}")
            time.sleep(2)
            continue

    # Now add sales events
    print(f"\\nAdding sales events...")
    next_cursor = None
    sales_page = 0

    while sales_page < 100:
        sales_page += 1
        params = {
            'event_type': 'sale',
            'limit': 50
        }
        if next_cursor:
            params['next'] = next_cursor

        try:
            response = requests.get(transfers_url, headers=headers, params=params, timeout=20)

            if response.status_code == 200:
                data = response.json()
                events = data.get('asset_events', [])

                for event in events:
                    try:
                        # Get buyer (new owner)
                        to_account = event.get('to_account')
                        if to_account:
                            wallet = to_account.get('address', '').lower()

                            # Get NFT
                            nft = event.get('nft', {})
                            if nft:
                                token_id = nft.get('identifier')

                                if wallet and token_id:
                                    if wallet not in all_holders:
                                        all_holders[wallet] = set()
                                    all_holders[wallet].add(token_id)

                    except Exception as e:
                        continue

                next_cursor = data.get('next')
                if not next_cursor or not events:
                    break

                time.sleep(0.3)

            else:
                break

        except Exception as e:
            print(f"Error on sales page {sales_page}: {e}")
            break

    # Convert to final counts
    final_holders = {}
    for wallet, tokens in all_holders.items():
        if wallet and len(tokens) > 0:
            final_holders[wallet] = len(tokens)

    print(f"\\nFINAL RESULTS:")
    print(f"Total Origins holders: {len(final_holders)}")
    print(f"Total Origins NFTs: {sum(final_holders.values())}")

    # Verify our whale wallet is included
    whale_wallet = '0xb0e9bc2d81856b46d0d0f7217435791c80df0808'
    if whale_wallet in final_holders:
        print(f"✓ WHALE WALLET FOUND: {final_holders[whale_wallet]} Origins")
    else:
        print(f"✗ Whale wallet NOT found - need more data collection")

    # Save data
    with open('working_origins_holders.json', 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'method': 'transfer_and_sales_events',
            'total_holders': len(final_holders),
            'total_nfts': sum(final_holders.values()),
            'transfer_pages': page,
            'sales_pages': sales_page,
            'holders': final_holders
        }, f, indent=2)

    print(f"Data saved to 'working_origins_holders.json'")

    return final_holders

if __name__ == "__main__":
    holders = get_origins_holders_working_method()