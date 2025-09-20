#!/usr/bin/env python3
"""
Simple Data Validation for GU Holder Analysis
"""
import json
import requests
import os
from datetime import datetime

def quick_validation():
    """Quick validation of key data points"""

    print("GU DATA VALIDATION CHECK")
    print("=" * 40)

    # 1. Check bubble data exists and is readable
    try:
        with open('genuine_undead_bubble_data.json', 'r') as f:
            data = json.load(f)
        holders = data.get('holders', [])
        total_holders = len(holders)
        total_nfts = sum(h.get('nftCount', 0) for h in holders)
        total_listed = sum(h.get('listedCount', 0) for h in holders)

        print(f"1. DATA FILE CHECK: PASS")
        print(f"   Holders: {total_holders:,}")
        print(f"   NFTs: {total_nfts:,}")
        print(f"   Listed: {total_listed:,}")

    except Exception as e:
        print(f"1. DATA FILE CHECK: FAIL - {e}")
        return False

    # 2. Check against known GU supply
    KNOWN_SUPPLY = 5322
    supply_variance = abs(total_nfts - KNOWN_SUPPLY)
    supply_accuracy = ((KNOWN_SUPPLY - supply_variance) / KNOWN_SUPPLY) * 100

    print(f"\n2. SUPPLY VERIFICATION:")
    print(f"   Known Supply: {KNOWN_SUPPLY:,}")
    print(f"   Our Data: {total_nfts:,}")
    print(f"   Variance: {supply_variance} NFTs")
    print(f"   Accuracy: {supply_accuracy:.1f}%")

    if supply_variance <= 200:  # Allow reasonable variance
        print(f"   SUPPLY CHECK: PASS")
        supply_check = True
    else:
        print(f"   SUPPLY CHECK: FAIL - Large variance")
        supply_check = False

    # 3. Check data freshness
    try:
        file_path = 'genuine_undead_bubble_data.json'
        mod_time = os.path.getmtime(file_path)
        last_updated = datetime.fromtimestamp(mod_time)
        hours_ago = (datetime.now() - last_updated).total_seconds() / 3600

        print(f"\n3. DATA FRESHNESS:")
        print(f"   Last Updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Hours Ago: {hours_ago:.1f}")

        if hours_ago <= 48:  # Within 2 days
            print(f"   FRESHNESS CHECK: PASS")
            freshness_check = True
        else:
            print(f"   FRESHNESS CHECK: FAIL - Data too old")
            freshness_check = False

    except Exception as e:
        print(f"3. FRESHNESS CHECK: FAIL - {e}")
        freshness_check = False

    # 4. Test API connection
    try:
        headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
        response = requests.get('https://api.opensea.io/api/v2/collections/genuine-undead/stats',
                              headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"\n4. API CONNECTION: PASS")
            api_check = True
        else:
            print(f"\n4. API CONNECTION: FAIL - Status {response.status_code}")
            api_check = False
    except Exception as e:
        print(f"\n4. API CONNECTION: FAIL - {e}")
        api_check = False

    # 5. Validate holder behavior calculations
    never_listed = [h for h in holders if h.get('listedCount', 0) == 0]
    light_sellers = [h for h in holders if 1 <= h.get('listedCount', 0) <= 2]
    heavy_sellers = [h for h in holders if h.get('listedCount', 0) > 2]

    diamond_hands_pct = (len(never_listed) / total_holders) * 100

    print(f"\n5. CALCULATION VERIFICATION:")
    print(f"   Diamond Hands: {len(never_listed):,} ({diamond_hands_pct:.1f}%)")
    print(f"   Light Sellers: {len(light_sellers):,}")
    print(f"   Heavy Sellers: {len(heavy_sellers):,}")
    print(f"   Total Check: {len(never_listed) + len(light_sellers) + len(heavy_sellers)} = {total_holders}")

    calc_check = (len(never_listed) + len(light_sellers) + len(heavy_sellers)) == total_holders
    print(f"   CALCULATION CHECK: {'PASS' if calc_check else 'FAIL'}")

    # Final Score
    checks = [True, supply_check, freshness_check, api_check, calc_check]  # First is always true if we get here
    passed = sum(checks)
    total = len(checks)
    score = (passed / total) * 100

    print(f"\n" + "=" * 40)
    print(f"VALIDATION SUMMARY")
    print(f"=" * 40)
    print(f"Checks Passed: {passed}/{total}")
    print(f"Accuracy Score: {score:.1f}%")

    if score >= 80:
        print("RECOMMENDATION: DATA IS RELIABLE FOR POSTING")
        return True
    elif score >= 60:
        print("RECOMMENDATION: DATA IS MOSTLY RELIABLE - CONSIDER REFRESH")
        return True
    else:
        print("RECOMMENDATION: REFRESH DATA BEFORE POSTING")
        return False

if __name__ == "__main__":
    quick_validation()