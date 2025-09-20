#!/usr/bin/env python3
"""
Daily Holder Report Generator for GU Migration Tracker
Generates and emails comprehensive daily holder analysis reports
"""
import asyncio
import os
import sys
from datetime import date, datetime
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json
from typing import Dict, List

# Add src and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(src_dir)
sys.path.append(src_dir)
sys.path.append(root_dir)

from services.holder_analysis_service import HolderAnalysisService
from database.database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DailyHolderReportGenerator:
    """Generates and emails daily holder analysis reports"""
    
    def __init__(self):
        self.holder_service = HolderAnalysisService()
        self.db = DatabaseManager()
        
        # Email configuration (using Trading-Dashboard pattern)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("GMAIL_EMAIL", "your-email@gmail.com")
        self.sender_password = os.getenv("GMAIL_APP_PASSWORD", "")
        self.recipient_email = "RRGU26@gmail.com"
        
        if not self.sender_password:
            logger.warning("Gmail App Password not found in environment variables")
    
    async def generate_and_send_daily_report(self, report_date: date = None) -> bool:
        """Generate and email the daily holder analysis report"""
        if report_date is None:
            report_date = date.today()
            
        logger.info(f"Generating daily holder report for {report_date}")
        
        try:
            # Run holder analysis
            analysis_results = await self.holder_service.analyze_daily_holders(report_date)
            
            # Generate report content
            report_html = self._generate_html_report(analysis_results, report_date)
            report_text = self._generate_text_report(analysis_results, report_date)
            
            # Send email
            success = self._send_email_report(report_html, report_text, report_date)
            
            if success:
                logger.info("Daily holder report sent successfully")
                return True
            else:
                logger.error("Failed to send daily holder report")
                return False
                
        except Exception as e:
            logger.error(f"Error generating daily holder report: {e}")
            return False
    
    def _generate_html_report(self, analysis_results: Dict, report_date: date) -> str:
        """Generate HTML version of the daily report"""
        
        collections = analysis_results.get('collections', {})
        summary = analysis_results.get('summary', {})
        
        # Get current ETH price for USD conversions
        eth_price_usd = self._get_current_eth_price()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background-color: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; font-size: 16px; }}
                .content {{ padding: 30px; }}
                .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .metric-card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; text-align: center; border-left: 4px solid #667eea; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #333; margin-bottom: 5px; }}
                .metric-label {{ color: #666; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
                .collection-section {{ margin-bottom: 30px; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; }}
                .collection-header {{ background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #e9ecef; }}
                .collection-body {{ padding: 20px; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }}
                .stat-item {{ text-align: center; }}
                .stat-value {{ font-size: 18px; font-weight: bold; color: #495057; }}
                .stat-label {{ font-size: 12px; color: #6c757d; margin-top: 5px; }}
                .insights-section {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin-top: 20px; }}
                .insight-item {{ margin-bottom: 10px; padding-left: 20px; position: relative; }}
                .insight-item::before {{ content: '•'; color: #667eea; font-weight: bold; position: absolute; left: 0; }}
                .footer {{ text-align: center; padding: 20px; color: #6c757d; font-size: 14px; border-top: 1px solid #e9ecef; }}
                .price-badge {{ background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
                .change-positive {{ color: #28a745; }}
                .change-negative {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏛️ GU Migration Tracker</h1>
                    <p>Daily Holder Analysis Report - {report_date.strftime('%B %d, %Y')}</p>
                </div>
                
                <div class="content">
                    <!-- Summary Metrics -->
                    <div class="summary-grid">
                        <div class="metric-card">
                            <div class="metric-value">{summary.get('total_unique_holders', 0):,}</div>
                            <div class="metric-label">Total Holders</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{summary.get('migration_holder_overlap', 0):,}</div>
                            <div class="metric-label">Estimated Overlap</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{summary.get('listing_pressure', 'N/A').title()}</div>
                            <div class="metric-label">Listing Pressure</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value"><span class="price-badge">${eth_price_usd:,.0f}</span></div>
                            <div class="metric-label">ETH Price</div>
                        </div>
                    </div>
        """
        
        # Add collection-specific sections
        for collection_key, collection_data in collections.items():
            collection_name = collection_data.get('collection_slug', collection_key).replace('-', ' ').title()
            
            if collection_key == 'origins':
                collection_name = "🎭 GU Origins"
                collection_color = "#e74c3c"
            else:
                collection_name = "🧟 Genuine Undead" 
                collection_color = "#9b59b6"
            
            floor_price = collection_data.get('floor_price', 0)
            floor_usd = floor_price * eth_price_usd
            total_supply = collection_data.get('total_supply', 0)
            unique_holders = collection_data.get('unique_holders', 0)
            listings = collection_data.get('listings', {})
            
            html_content += f"""
                    <div class="collection-section">
                        <div class="collection-header">
                            <h3 style="margin: 0; color: {collection_color};">{collection_name}</h3>
                        </div>
                        <div class="collection-body">
                            <div class="stats-grid">
                                <div class="stat-item">
                                    <div class="stat-value">{total_supply:,}</div>
                                    <div class="stat-label">Total Supply</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">{unique_holders:,}</div>
                                    <div class="stat-label">Unique Holders</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">{floor_price:.4f} ETH</div>
                                    <div class="stat-label">Floor Price</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${floor_usd:,.0f}</div>
                                    <div class="stat-label">Floor USD</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">{listings.get('total', 0)}</div>
                                    <div class="stat-label">Active Listings</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">{listings.get('floor_count', 0)}</div>
                                    <div class="stat-label">Floor Listings</div>
                                </div>
                            </div>
                        </div>
                    </div>
            """
        
        # Add insights section
        insights = summary.get('key_insights', [])
        insights_html = ""
        for insight in insights:
            insights_html += f'<div class="insight-item">{insight}</div>'
        
        html_content += f"""
                    <div class="insights-section">
                        <h3 style="margin-top: 0; color: #495057;">📈 Key Insights</h3>
                        {insights_html}
                    </div>
                </div>
                
                <div class="footer">
                    <p>Generated by GU Migration Tracker | {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p>Automated daily report for holder behavior analysis</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _generate_text_report(self, analysis_results: Dict, report_date: date) -> str:
        """Generate plain text version of the daily report"""
        
        collections = analysis_results.get('collections', {})
        summary = analysis_results.get('summary', {})
        eth_price_usd = self._get_current_eth_price()
        
        report_lines = [
            "=" * 60,
            "GU MIGRATION TRACKER - DAILY HOLDER ANALYSIS",
            f"Report Date: {report_date.strftime('%B %d, %Y')}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 60,
            "",
            "📊 SUMMARY METRICS",
            "-" * 30,
            f"Total Unique Holders: {summary.get('total_unique_holders', 0):,}",
            f"Estimated Holder Overlap: {summary.get('migration_holder_overlap', 0):,}",
            f"Listing Pressure: {summary.get('listing_pressure', 'N/A').title()}",
            f"Current ETH Price: ${eth_price_usd:,.0f}",
            ""
        ]
        
        # Add collection details
        for collection_key, collection_data in collections.items():
            if collection_key == 'origins':
                collection_name = "🎭 GU ORIGINS"
            else:
                collection_name = "🧟 GENUINE UNDEAD"
                
            floor_price = collection_data.get('floor_price', 0)
            floor_usd = floor_price * eth_price_usd
            total_supply = collection_data.get('total_supply', 0)
            unique_holders = collection_data.get('unique_holders', 0)
            listings = collection_data.get('listings', {})
            
            report_lines.extend([
                f"🔹 {collection_name}",
                "-" * 30,
                f"Total Supply: {total_supply:,}",
                f"Unique Holders: {unique_holders:,}",
                f"Floor Price: {floor_price:.4f} ETH (${floor_usd:,.0f})",
                f"Active Listings: {listings.get('total', 0)}",
                f"Floor Listings: {listings.get('floor_count', 0)}",
                f"Above Floor Listings: {listings.get('above_floor', 0)}",
                f"Average Listing Price: {listings.get('avg_price', 0):.4f} ETH",
                ""
            ])
        
        # Add insights
        insights = summary.get('key_insights', [])
        if insights:
            report_lines.extend([
                "📈 KEY INSIGHTS",
                "-" * 30
            ])
            for insight in insights:
                report_lines.append(f"• {insight}")
            report_lines.append("")
        
        # Add footer
        report_lines.extend([
            "=" * 60,
            "Automated report generated by GU Migration Tracker",
            "For questions contact: RRGU26@gmail.com",
            "=" * 60
        ])
        
        return "\n".join(report_lines)
    
    def _get_current_eth_price(self) -> float:
        """Get current ETH price from database or API"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT eth_price_usd FROM daily_eth_prices 
                    ORDER BY price_date DESC LIMIT 1
                """)
                result = cursor.fetchone()
                if result:
                    return float(result[0])
        except Exception as e:
            logger.warning(f"Could not get ETH price from database: {e}")
        
        # Fallback price if database lookup fails
        return 4200.0
    
    def _send_email_report(self, html_content: str, text_content: str, report_date: date) -> bool:
        """Send the email report using Gmail SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"GU Migration Tracker - Daily Holder Report ({report_date.strftime('%Y-%m-%d')})"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Add both text and HTML versions
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email report sent successfully to {self.recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email report: {e}")
            return False
    
    def test_email_configuration(self) -> bool:
        """Test email configuration by sending a simple test message"""
        try:
            msg = MIMEText("GU Migration Tracker email configuration test successful!")
            msg['Subject'] = "GU Migration Tracker - Email Test"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info("Email configuration test successful")
            return True
            
        except Exception as e:
            logger.error(f"Email configuration test failed: {e}")
            return False


async def main():
    """Main function to generate and send daily report"""
    print("=" * 60)
    print("GU MIGRATION TRACKER - DAILY HOLDER REPORT")
    print(f"Date: {date.today()}")
    print("=" * 60)
    
    report_generator = DailyHolderReportGenerator()
    
    # Test email configuration first
    print("Testing email configuration...")
    if not report_generator.test_email_configuration():
        print("[ERROR] Email configuration test failed")
        print("Please check your Gmail App Password and environment variables")
        return False
    
    print("[SUCCESS] Email configuration test passed")
    
    # Generate and send daily report
    print("Generating daily holder report...")
    success = await report_generator.generate_and_send_daily_report()
    
    if success:
        print("[SUCCESS] Daily holder report generated and sent successfully!")
        print(f"[EMAIL] Report sent to: {report_generator.recipient_email}")
    else:
        print("[ERROR] Failed to generate or send daily holder report")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())