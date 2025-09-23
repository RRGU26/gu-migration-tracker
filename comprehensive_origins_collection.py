#!/usr/bin/env python3
"""
Comprehensive Origins holder collection using multiple data sources
"""
import requests
import time
import json
from datetime import datetime

def get_comprehensive_origins_holders():
    """Get ALL Origins holders using multiple comprehensive methods"""

    headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}

    print("COMPREHENSIVE ORIGINS HOLDER COLLECTION")
    print("=" * 60)

    all_holders = {}

    # Method 1: Direct NFT collection scan (most reliable)
    print("1. Scanning ALL Origins NFTs for current owners...")
    nfts_url = 'https://api.opensea.io/api/v2/collection/gu-origins/nfts'

    next_cursor = None
    page = 0

    while True:
        page += 1
        params = {'limit': 200}
        if next_cursor:
            params['next'] = next_cursor

        try:
            response = requests.get(nfts_url, headers=headers, params=params, timeout=20)

            if response.status_code == 200:
                data = response.json()
                nfts = data.get('nfts', [])

                print(f"  NFT page {page}: {len(nfts)} NFTs")

                for nft in nfts:
                    try:
                        # Get current owners
                        owners = nft.get('owners', [])
                        token_id = nft.get('identifier')

                        for owner in owners:
                            wallet = owner.get('address', '').lower()
                            if wallet and token_id:
                                if wallet not in all_holders:
                                    all_holders[wallet] = set()
                                all_holders[wallet].add(token_id)

                    except Exception as e:
                        continue

                next_cursor = data.get('next')
                if not next_cursor or not nfts:
                    break

                time.sleep(0.5)  # Rate limiting

            else:
                print(f"  NFT API error: {response.status_code}")
                if response.status_code == 429:
                    time.sleep(5)
                    continue
                break

        except Exception as e:
            print(f"  Error on NFT page {page}: {e}")
            time.sleep(2)
            continue

    print(f"Method 1 found: {len(all_holders)} holders, {sum(len(tokens) for tokens in all_holders.values())} total NFTs")

    # Method 2: Transfer events (comprehensive history)
    print("\\n2. Collecting transfer history comprehensively...")
    transfers_url = 'https://api.opensea.io/api/v2/events/collection/gu-origins'

    next_cursor = None
    page = 0

    # Get MUCH more transfer history
    while page < 100:  # Get up to 100 pages of transfers
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

                if page % 10 == 0:  # Report every 10 pages
                    print(f"  Transfer page {page}: {len(events)} events")

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
                    break

                time.sleep(0.3)

            else:
                print(f"  Transfer API error: {response.status_code}")
                if response.status_code == 429:
                    time.sleep(5)
                    continue
                break

        except Exception as e:
            print(f"  Error on transfer page {page}: {e}")
            time.sleep(2)
            continue

    print(f"After transfers: {len(all_holders)} holders")

    # Method 3: Sales events
    print("\\n3. Collecting sales history...")
    next_cursor = None
    page = 0

    while page < 50:  # Get sales history
        page += 1
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
            print(f"  Error on sales page {page}: {e}")
            break

    print(f"After sales: {len(all_holders)} holders")

    # Method 4: Active listings
    print("\\n4. Collecting active listings...")
    listings_url = 'https://api.opensea.io/api/v2/listings/collection/gu-origins/all'

    next_cursor = None
    page = 0

    while page < 20:
        page += 1
        params = {'limit': 50}
        if next_cursor:
            params['next'] = next_cursor

        try:
            response = requests.get(listings_url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                listings = data.get('listings', [])

                for listing in listings:
                    try:
                        # Get seller
                        protocol_data = listing.get('protocol_data', {})
                        parameters = protocol_data.get('parameters', {})
                        seller_address = parameters.get('offerer', '').lower()

                        # Get NFT ID
                        offer = parameters.get('offer', [{}])[0]
                        token_id = offer.get('identifierOrCriteria')

                        if seller_address and token_id:
                            if seller_address not in all_holders:
                                all_holders[seller_address] = set()
                            all_holders[seller_address].add(token_id)

                    except Exception as e:
                        continue

                next_cursor = data.get('next')
                if not next_cursor or not listings:
                    break

                time.sleep(0.3)

            else:
                break

        except Exception as e:
            print(f"  Error on listings page {page}: {e}")
            break

    # Final processing
    final_holders = {}
    for wallet, tokens in all_holders.items():
        if wallet and len(tokens) > 0:
            final_holders[wallet] = len(tokens)

    print(f"\\nFINAL COMPREHENSIVE RESULTS:")
    print(f"Total Origins holders found: {len(final_holders)}")
    print(f"Total Origins NFTs tracked: {sum(final_holders.values())}")

    # Save comprehensive data
    with open('comprehensive_origins_holders.json', 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'method': 'comprehensive_collection',
            'total_holders': len(final_holders),
            'total_nfts': sum(final_holders.values()),
            'holders': final_holders
        }, f, indent=2)

    print(f"Data saved to 'comprehensive_origins_holders.json'")

    return final_holders

if __name__ == "__main__":
    comprehensive_holders = get_comprehensive_origins_holders()