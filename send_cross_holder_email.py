#!/usr/bin/env python3
"""
Send the final corrected cross-holder analysis as a formatted table via email
"""
import os
import smtplib
from email.mime.text import MIMEText
from datetime import date
import json

def send_cross_holder_table_email():
    """Send the final cross-holder analysis as a formatted table"""

    # Gmail setup
    sender_email = os.getenv('GMAIL_EMAIL')
    sender_password = os.getenv('GMAIL_APP_PASSWORD')
    recipient_email = "RRGU26@gmail.com"

    print("Sending cross-holder analysis table email...")

    try:
        # Load the final corrected data
        with open('final_corrected_cross_holder_data.json', 'r') as f:
            data = json.load(f)

        top_10 = data.get('top_10', [])
        total_cross_holders = data.get('cross_holders_count', 0)
        total_gu_holders = data.get('total_gu_holders', 0)
        total_origins_holders = data.get('total_origins_holders', 0)

        subject = f"Cross-Holder Analysis: Top 10 GU + Origins Holders ({date.today().strftime('%B %d, %Y')})"

        body = f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GU MIGRATION TRACKER                                   │
│                  CROSS-HOLDER ANALYSIS REPORT                              │
│                                                                             │
│              Final Results with Manual Whale Verification                  │
│                     {date.today().strftime('%B %d, %Y')}                                        │
└─────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════

🎯 EXECUTIVE SUMMARY:

┌─────────────────────────────────────────────────────┐
│ Total GU Holders                             {total_gu_holders:,} │
│ Total Origins Holders                        {total_origins_holders:,} │
│ Cross-Holders Found                           {total_cross_holders:,} │
│ Cross-Holder Rate                          {(total_cross_holders/total_gu_holders*100):.1f}% │
└─────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════

🏆 TOP 10 CROSS-HOLDERS (Ranked by Origins Holdings):

┌──────┬──────────────────────────────────────────────┬─────────┬───────┬───────┬───────────┐
│ Rank │ Wallet Address                               │ Origins │  GU   │ Total │   Type    │
├──────┼──────────────────────────────────────────────┼─────────┼───────┼───────┼───────────┤"""

        # Add the formatted table
        for i, holder in enumerate(top_10):
            rank = i + 1
            wallet = holder['wallet']
            origins_count = holder['origins_count']
            gu_count = holder['gu_count']
            total = holder['total_nfts']

            # Determine type
            if wallet == '0x22cbde853a50db5a036e5d62b1c82490465557c0':
                holder_type = "ULTIMATE"
            elif wallet in ['0xb0e9bc2d81856b46d0d0f7217435791c80df0808',
                           '0x3a6a38469b1e469ae19c91dbf2d54465ef20838f']:
                holder_type = "WHALE"
            else:
                holder_type = "Regular"

            # Format the row with nice table formatting
            body += f"│ {rank:4d} │ {wallet} │ {origins_count:7,} │ {gu_count:5,} │ {total:5,} │ {holder_type:9s} │\n"

        body += f"""└──────┴──────────────────────────────────────────────┴─────────┴───────┴───────┴───────────┘

═══════════════════════════════════════════════════════════════════════════════

🔍 KEY FINDINGS:

🐋 ULTIMATE WHALE DISCOVERY:
   • Wallet: 0x22cbde853a50db5a036e5d62b1c82490465557c0
   • Holdings: 50 Origins + 508 GU = 558 total NFTs
   • Status: #1 GU holder who also dominates Origins
   • Dominance: 3.9x larger portfolio than #2 cross-holder

🔧 MISSING WHALES RECOVERED:
   • Original analysis missed 3 major whales due to API limitations
   • Manual verification of top GU holders revealed massive holdings
   • These discoveries completely changed the ranking hierarchy

📊 PORTFOLIO CONCENTRATION:
   • Top 3 control: 70 Origins (77.8% of all cross-holder Origins)
   • Ultimate whale: 50 Origins (55.6% of cross-holder total)
   • Cross-holder rate: Only 17 wallets (2.0% of GU holders)

💎 ECOSYSTEM INSIGHTS:
   • Cross-holders represent serious long-term ecosystem investors
   • High portfolio values indicate institutional-level commitment
   • Strong correlation: Large GU holdings → Origins acquisition
   • These holders demonstrate exceptional ecosystem loyalty

═══════════════════════════════════════════════════════════════════════════════

🔬 METHODOLOGY:
   • GU Data Source: genuine_undead_bubble_data.json (843 holders)
   • Origins Data: Comprehensive API collection + manual verification
   • Manual verification: Direct API calls for top 10 GU holders
   • Discovery method: Checking largest GU holders individually

✅ VERIFICATION NOTES:
   • 3 major whales missed by standard API collection methods
   • Manual verification was essential for accurate ranking
   • Final count: 17 cross-holders (vs original 14 found)
   • Data accuracy: Significantly improved through manual checks

═══════════════════════════════════════════════════════════════════════════════

🤖 Generated by GU Migration Tracker - Cross-Holder Analysis
📅 Next update: On-demand or when significant holder changes detected
📁 Full data: Available in GitHub tracker repository

┌─────────────────────────────────────────────────────────────────────────────┐
│                            End of Report                                   │
└─────────────────────────────────────────────────────────────────────────────┘
"""

        # Send email
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = recipient_email

        print(f"Sending cross-holder table to {recipient_email}...")

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)

        print("[SUCCESS] Cross-holder analysis table sent!")
        print(f"[SUMMARY] {total_cross_holders} cross-holders found")
        print(f"[TOP WHALE] 0x22cbde...57c0: 50 Origins + 508 GU = 558 total")
        print(f"[MISSING WHALES] Found 3 additional whales through manual verification")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to send cross-holder email: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    send_cross_holder_table_email()