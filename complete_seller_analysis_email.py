#!/usr/bin/env python3
"""
Complete seller analysis email with ALL sellers and their near-floor listings
"""
import asyncio
import os
import smtplib
from email.mime.text import MIMEText
from datetime import date
import requests

async def send_complete_seller_analysis():
    """Send email with complete seller analysis including all sellers"""
    
    # Gmail setup
    sender_email = os.getenv('GMAIL_EMAIL')
    sender_password = os.getenv('GMAIL_APP_PASSWORD')
    recipient_email = "RRGU26@gmail.com"
    
    print("=" * 60)
    print("GU MIGRATION TRACKER - COMPLETE SELLER ANALYSIS")
    print("=" * 60)
    
    headers = {'X-API-KEY': os.environ.get('OPENSEA_API_KEY', '')}
    
    try:
        # Get collection stats
        print("Fetching collection stats...")
        stats_url = 'https://api.opensea.io/api/v2/collections/genuine-undead/stats'
        response = requests.get(stats_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            stats_data = response.json()
            collection_stats = stats_data.get('total', {})
            num_owners = collection_stats.get('num_owners', 695)
            total_supply = 5322  # Known supply
        else:
            num_owners = 695
            total_supply = 5322
        
        # Get listings data
        print("Fetching listing data...")
        listings_url = 'https://api.opensea.io/api/v2/listings/collection/genuine-undead/all'
        
        # Need to paginate to get ALL listings
        all_listings = []
        next_cursor = None

        for page in range(20):  # Get up to 20 pages (1000 listings max)
            params = {'limit': 50}
            if next_cursor:
                params['next'] = next_cursor

            response = requests.get(listings_url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                listings = data.get('listings', [])
                all_listings.extend(listings)

                print(f"Page {page + 1}: Retrieved {len(listings)} listings (total so far: {len(all_listings)})")

                next_cursor = data.get('next')
                if not next_cursor or not listings:
                    print(f"Pagination complete - no more listings available")
                    break
            else:
                print(f"API error on page {page + 1}: {response.status_code}")
                break

        print(f"Retrieved {len(all_listings)} total listings from API")

        # Process all listings and deduplicate by NFT ID
        prices = []
        seller_data = {}
        listing_details = []  # Store detailed info for each listing
        unique_listings = {}  # Track by NFT ID to avoid duplicates
        
        for listing in all_listings:
            try:
                # Get price in ETH
                price_data = listing.get('price', {}).get('current', {})
                if price_data.get('currency') == 'ETH':
                    price_wei = int(price_data.get('value', 0))
                    price_eth = price_wei / 1e18
                else:
                    continue  # Skip non-ETH listings

                if price_eth > 0:
                    # Get seller info from protocol_data
                    protocol_data = listing.get('protocol_data', {})
                    parameters = protocol_data.get('parameters', {})
                    seller_address = parameters.get('offerer', '').lower()

                    # Get NFT ID
                    offer = parameters.get('offer', [{}])[0]
                    nft_id = offer.get('identifierOrCriteria', 'Unknown')

                    # Skip if we've already seen this NFT (avoid duplicates)
                    if nft_id in unique_listings:
                        continue

                    # Only add to tracking after deduplication check passes
                    unique_listings[nft_id] = True
                    prices.append(price_eth)

                    listing_details.append({
                        'seller': seller_address,
                        'price': price_eth,
                        'nft_id': nft_id
                    })

                    if seller_address:
                        if seller_address not in seller_data:
                            seller_data[seller_address] = {
                                'prices': [],
                                'count': 0,
                                'near_floor': 0,
                                'nft_ids': []
                            }
                        seller_data[seller_address]['prices'].append(price_eth)
                        seller_data[seller_address]['nft_ids'].append(nft_id)
                        seller_data[seller_address]['count'] += 1

            except Exception as e:
                print(f"Error processing listing: {e}")
                continue

        actual_unique_count = len(unique_listings)
        print(f"After deduplication: {actual_unique_count} unique listings")

        # Use the accurate unique count, not the price count which includes duplicates
        display_count = actual_unique_count
        print(f"Note: Using unique count {actual_unique_count} vs raw price count {len(prices)}")
        print(f"Reporting actual deduplicated count: {display_count}")

        # Calculate metrics using unique listings
        if prices:
            prices.sort()
            floor_price = prices[0]
            floor_plus_20 = floor_price * 1.2
            # Count only unique deduplicated listings within 20% of floor
            within_20_percent = sum(1 for listing in listing_details if listing['price'] <= floor_plus_20)
            # Calculate average from unique listings only
            avg_price = sum(listing['price'] for listing in listing_details) / len(listing_details) if listing_details else 0

            # Update listing percentage calculation to use display_count
            listing_percentage = (display_count / total_supply * 100) if total_supply > 0 else 0
            
            # Calculate seller metrics
            for seller_address, data in seller_data.items():
                data['avg_price'] = sum(data['prices']) / len(data['prices'])
                data['near_floor'] = sum(1 for p in data['prices'] if p <= floor_plus_20)
                data['min_price'] = min(data['prices'])
                data['max_price'] = max(data['prices'])
                
            # Sort sellers by listing count
            all_sellers = sorted(seller_data.items(), key=lambda x: x[1]['count'], reverse=True)
            
            # Separate sellers with near-floor listings
            sellers_with_near_floor = [(addr, data) for addr, data in all_sellers if data['near_floor'] > 0]
            
        else:
            floor_price = 0.0305  # Fallback
            within_20_percent = 0
            avg_price = 0
            all_sellers = []
            sellers_with_near_floor = []
        
        # Create email body
        floor_usd = floor_price * 4200  # Approximate ETH/USD
        
        subject = f"🧟 GU Genuine Undead - Complete Seller Analysis ({date.today().strftime('%B %d, %Y')})"
        
        body = f"""GU MIGRATION TRACKER - COMPLETE SELLER ANALYSIS REPORT
Date: {date.today().strftime('%B %d, %Y')}

═══════════════════════════════════════════════════════════════

🧟 GENUINE UNDEAD COLLECTION OVERVIEW:

┌─────────────────────────────────────────────────────┐
│ Holders                                      {num_owners:,} │
│ Supply                                     {total_supply:,} │
│ Floor Price                         {floor_price:.4f} ETH │
│ Listed ({listing_percentage:.1f}%)                              {display_count:,} │
│ Active Sellers                               {len(seller_data):,} │
│ Floor USD                                  ${floor_usd:.0f} │
└─────────────────────────────────────────────────────┘

🎯 LISTING DEPTH ANALYSIS:

Total Active Listings      {display_count:,}
Within 20% of Floor        {within_20_percent:,} listings
Floor Range               {floor_price:.4f} - {floor_plus_20:.4f} ETH
Average Listing Price     {avg_price:.4f} ETH
Near-Floor Percentage     {(within_20_percent/display_count*100 if display_count > 0 else 0):.1f}%

═══════════════════════════════════════════════════════════════

🚨 SELLERS WITH LISTINGS WITHIN 20% OF FLOOR ({len(sellers_with_near_floor)} sellers):
"""

        # List all sellers with near-floor listings
        if sellers_with_near_floor:
            body += "\n"
            for seller_address, data in sellers_with_near_floor:
                near_floor_pct = (data['near_floor'] / data['count'] * 100) if data['count'] > 0 else 0
                body += f"""
{seller_address}
  • Total Listed: {data['count']:,} NFTs
  • Near Floor: {data['near_floor']:,} listings ({near_floor_pct:.0f}%)
  • Price Range: {data['min_price']:.4f} - {data['max_price']:.4f} ETH
  • Avg Price: {data['avg_price']:.4f} ETH
  • NFT IDs: {', '.join(str(id) for id in data['nft_ids'][:5])}{' ...' if len(data['nft_ids']) > 5 else ''}
"""
        else:
            body += "\n\nNo sellers with listings within 20% of floor."
        
        body += f"""

═══════════════════════════════════════════════════════════════

📋 ALL ACTIVE SELLERS ({len(all_sellers)} total):

"""

        # List ALL sellers
        if all_sellers:
            for seller_address, data in all_sellers:
                near_floor_marker = "🔴" if data['near_floor'] > 0 else "⚪"
                body += f"""
{near_floor_marker} {seller_address}
   Listed: {data['count']} | Avg: {data['avg_price']:.4f} ETH | Near Floor: {data['near_floor']}
"""
        else:
            body += "No active sellers found."
        
        body += f"""

═══════════════════════════════════════════════════════════════

📊 MARKET INSIGHTS:

SELLER CONCENTRATION:
• Top seller has {all_sellers[0][1]['count'] if all_sellers else 0} listings ({(all_sellers[0][1]['count']/display_count*100 if all_sellers and display_count > 0 else 0):.1f}% of market)
• Top 5 sellers control {sum(data['count'] for _, data in all_sellers[:5]) if all_sellers else 0} listings ({(sum(data['count'] for _, data in all_sellers[:5])/display_count*100 if all_sellers and display_count > 0 else 0):.1f}% of market)
• {len(sellers_with_near_floor)} sellers competing at floor level

PRICING BEHAVIOR:
• {within_20_percent} of {display_count} listings are within 20% of floor
• {len([s for s, d in all_sellers if d['count'] >= 3])} sellers have 3+ listings (potential bulk sellers)
• {"High competition" if len(sellers_with_near_floor) > 10 else "Moderate competition" if len(sellers_with_near_floor) > 5 else "Low competition"} at floor price

RISK ASSESSMENT:
• Immediate sell pressure: {within_20_percent} NFTs
• Potential cascade risk: {"HIGH" if within_20_percent > 50 else "MEDIUM" if within_20_percent > 25 else "LOW"}
• Seller diversity: {"Good" if len(seller_data) > 20 else "Moderate" if len(seller_data) > 10 else "Concentrated"}

═══════════════════════════════════════════════════════════════

Generated by GU Migration Tracker - Complete Seller Analysis
Next report: Tomorrow at 9:00 AM EST
"""
        
        # Send email
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = recipient_email
        
        print(f"Sending complete seller analysis to {recipient_email}...")
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        print("[SUCCESS] Complete seller analysis sent!")
        print(f"[TOTALS] {len(seller_data):,} sellers, {display_count:,} listings")
        print(f"[NEAR FLOOR] {len(sellers_with_near_floor):,} sellers have listings within 20% of floor")
        print(f"[DEPTH] {within_20_percent:,} total listings within 20% of {floor_price:.4f} ETH floor")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send complete analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(send_complete_seller_analysis())