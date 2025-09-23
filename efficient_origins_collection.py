#!/usr/bin/env python3
"""
Efficient Origins holder collection using direct NFT scanning
"""
import requests
import time
import json
from datetime import datetime

def get_all_origins_holders_efficient():
    """Get ALL Origins holders using direct NFT collection scan (most reliable method)"""

    headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}

    print("EFFICIENT ORIGINS HOLDER COLLECTION")
    print("=" * 60)
    print("Using direct NFT scanning method...")

    all_holders = {}
    nfts_url = 'https://api.opensea.io/api/v2/collection/gu-origins/nfts'

    next_cursor = None
    page = 0
    total_nfts_processed = 0

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

                print(f"Page {page}: Processing {len(nfts)} NFTs...")
                total_nfts_processed += len(nfts)

                for nft in nfts:
                    try:
                        # Get current owners
                        owners = nft.get('owners', [])
                        token_id = nft.get('identifier')

                        for owner in owners:
                            wallet = owner.get('address', '').lower()
                            if wallet and token_id:
                                if wallet not in all_holders:
                                    all_holders[wallet] = []
                                all_holders[wallet].append(token_id)

                    except Exception as e:
                        continue

                # Progress update every 5 pages
                if page % 5 == 0:
                    print(f"  Progress: {len(all_holders)} holders found, {total_nfts_processed} NFTs processed")

                next_cursor = data.get('next')
                if not next_cursor or not nfts:
                    print(f"Collection complete - reached end of data")
                    break

                time.sleep(0.5)  # Rate limiting

            else:
                print(f"API error: {response.status_code}")
                if response.status_code == 429:
                    print("Rate limited - waiting 5 seconds...")
                    time.sleep(5)
                    continue
                break

        except Exception as e:
            print(f"Error on page {page}: {e}")
            time.sleep(2)
            continue

    # Convert to counts and validate
    final_holders = {}
    total_nfts_tracked = 0

    for wallet, tokens in all_holders.items():
        if wallet and len(tokens) > 0:
            # Remove duplicates
            unique_tokens = list(set(tokens))
            final_holders[wallet] = len(unique_tokens)
            total_nfts_tracked += len(unique_tokens)

    print(f"\\nFINAL RESULTS:")
    print(f"Total Origins holders: {len(final_holders)}")
    print(f"Total Origins NFTs: {total_nfts_tracked}")
    print(f"Pages processed: {page}")

    # Save data
    with open('efficient_origins_holders.json', 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'method': 'efficient_nft_scan',
            'total_holders': len(final_holders),
            'total_nfts': total_nfts_tracked,
            'pages_processed': page,
            'holders': final_holders
        }, f, indent=2)

    print(f"Data saved to 'efficient_origins_holders.json'")

    return final_holders

if __name__ == "__main__":
    holders = get_all_origins_holders_efficient()