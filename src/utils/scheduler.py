import asyncio
import schedule
import time
import logging
from datetime import datetime, date, time as dt_time
from typing import Optional, Dict, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import json

from src.reports.report_generator import generate_daily_report
from src.utils.migration_detector import run_daily_migration_detection
from src.database.database import DatabaseManager
from config.config import Config

class TaskScheduler:
    """Handles automated scheduling of migration tracking tasks"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, Config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(Config.LOG_FILE),
                logging.StreamHandler()
            ]
        )
    
    def setup_daily_schedule(self):
        """Set up the daily report generation schedule"""
        # Schedule data collection at 8 AM EST
        schedule.every().day.at("08:00").do(self._run_daily_data_collection)
        
        # Schedule report generation at 9 AM EST
        schedule.every().day.at("09:00").do(self._run_daily_report_generation)
        
        # Schedule weekly summary on Sundays at 10 AM
        schedule.every().sunday.at("10:00").do(self._run_weekly_summary)
        
        # Schedule data cleanup monthly (first day of month at midnight)
        schedule.every().day.at("00:01").do(self._check_monthly_cleanup)
        
        self.logger.info("Daily schedule configured successfully")
    
    def _run_daily_data_collection(self):
        """Run daily data collection and migration detection"""
        try:
            self.logger.info("Starting daily data collection...")
            
            # Run migration detection
            result = asyncio.run(run_daily_migration_detection())
            
            self.logger.info(f"Data collection completed: {result.get('migrations_detected', 0)} migrations detected")
            
            # Create success alert
            self.db.create_alert(
                'daily_data_collection_success',
                'INFO',
                f"Daily data collection completed successfully on {date.today()}",
                result
            )
            
        except Exception as e:
            self.logger.error(f"Daily data collection failed: {e}")
            self.db.create_alert(
                'daily_data_collection_failed',
                'ERROR',
                f"Daily data collection failed: {str(e)}"
            )
    
    def _run_daily_report_generation(self):
        """Run daily report generation and distribution"""
        try:
            self.logger.info("Starting daily report generation...")
            
            # Generate reports
            report_paths = asyncio.run(generate_daily_report())
            
            # Send email reports if configured
            if Config.EMAIL_TO and Config.EMAIL_FROM:
                self._send_email_reports(report_paths)
            
            self.logger.info("Daily report generation completed successfully")
            
            # Create success alert
            self.db.create_alert(
                'daily_report_success',
                'INFO',
                f"Daily report generated successfully on {date.today()}",
                report_paths
            )
            
        except Exception as e:
            self.logger.error(f"Daily report generation failed: {e}")
            self.db.create_alert(
                'daily_report_failed',
                'ERROR',
                f"Daily report generation failed: {str(e)}"
            )
    
    def _run_weekly_summary(self):
        """Generate and send weekly summary report"""
        try:
            self.logger.info("Starting weekly summary generation...")
            
            # Generate weekly summary data
            summary_data = self._generate_weekly_summary()
            
            # Send weekly email if configured
            if Config.EMAIL_TO and Config.EMAIL_FROM:
                self._send_weekly_summary_email(summary_data)
            
            self.logger.info("Weekly summary completed successfully")
            
        except Exception as e:
            self.logger.error(f"Weekly summary failed: {e}")
            self.db.create_alert(
                'weekly_summary_failed',
                'ERROR',
                f"Weekly summary generation failed: {str(e)}"
            )
    
    def _check_monthly_cleanup(self):
        """Check if monthly data cleanup is needed"""
        today = date.today()
        if today.day == 1:  # First day of month
            self._run_monthly_cleanup()
    
    def _run_monthly_cleanup(self):
        """Run monthly data cleanup and archival"""
        try:
            self.logger.info("Starting monthly data cleanup...")
            
            # Archive old API logs (keep last 90 days)
            with self.db.get_connection() as conn:
                conn.execute("""
                    DELETE FROM api_logs 
                    WHERE called_at < date('now', '-90 days')
                """)
                
                # Archive resolved alerts older than 30 days
                conn.execute("""
                    DELETE FROM alerts 
                    WHERE resolved = TRUE AND created_at < date('now', '-30 days')
                """)
                
                conn.commit()
            
            self.logger.info("Monthly cleanup completed successfully")
            
            # Create success alert
            self.db.create_alert(
                'monthly_cleanup_success',
                'INFO',
                f"Monthly data cleanup completed on {date.today()}"
            )
            
        except Exception as e:
            self.logger.error(f"Monthly cleanup failed: {e}")
            self.db.create_alert(
                'monthly_cleanup_failed',
                'ERROR',
                f"Monthly cleanup failed: {str(e)}"
            )
    
    def _generate_weekly_summary(self) -> Dict:
        """Generate weekly summary data"""
        from src.utils.migration_detector import get_migration_analytics
        
        # Get migration analytics
        analytics = get_migration_analytics()
        
        # Get weekly collection performance
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        origins_history = self.db.get_historical_snapshots(origins_id, 7)
        undead_history = self.db.get_historical_snapshots(undead_id, 7)
        
        # Calculate weekly changes
        weekly_summary = {
            'week_ending': date.today().isoformat(),
            'migration_analytics': analytics,
            'origins_performance': self._calculate_weekly_performance(origins_history),
            'undead_performance': self._calculate_weekly_performance(undead_history),
            'total_migrations_week': self.db.get_migration_stats(7).get('total_migrations', 0),
            'alerts_summary': self._get_weekly_alerts_summary()
        }
        
        return weekly_summary
    
    def _calculate_weekly_performance(self, history: List[Dict]) -> Dict:
        """Calculate weekly performance metrics for a collection"""
        if not history or len(history) < 2:
            return {'error': 'Insufficient data'}
        
        latest = history[0]  # Most recent
        oldest = history[-1]  # Week ago
        
        def calc_change(current, previous):
            if previous and previous > 0:
                return ((current - previous) / previous) * 100
            return 0
        
        return {
            'floor_price_change': calc_change(
                latest.get('floor_price_eth', 0), 
                oldest.get('floor_price_eth', 0)
            ),
            'volume_change': calc_change(
                latest.get('volume_24h_eth', 0),
                oldest.get('volume_24h_eth', 0)
            ),
            'market_cap_change': calc_change(
                latest.get('market_cap_eth', 0),
                oldest.get('market_cap_eth', 0)
            ),
            'listing_percentage_change': calc_change(
                latest.get('listed_percentage', 0),
                oldest.get('listed_percentage', 0)
            )
        }
    
    def _get_weekly_alerts_summary(self) -> Dict:
        """Get summary of alerts from the past week"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT severity, COUNT(*) as count
                FROM alerts 
                WHERE created_at >= date('now', '-7 days')
                GROUP BY severity
            """)
            
            alerts_by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM alerts 
                WHERE created_at >= date('now', '-7 days') AND resolved = FALSE
            """)
            
            unresolved_count = cursor.fetchone()['count']
            
            return {
                'by_severity': alerts_by_severity,
                'unresolved': unresolved_count
            }
    
    def _send_email_reports(self, report_paths: Dict[str, str]):
        """Send daily reports via email"""
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_FROM
            msg['To'] = ', '.join(Config.EMAIL_TO)
            msg['Subject'] = f"GU Migration Daily Report - {date.today().strftime('%B %d, %Y')}"
            
            # Email body
            body = self._create_daily_email_body(report_paths)
            msg.attach(MIMEText(body, 'html'))
            
            # Attach PDF report if available
            if report_paths.get('pdf') and os.path.exists(report_paths['pdf']):
                with open(report_paths['pdf'], 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= daily_report_{date.today()}.pdf'
                    )
                    msg.attach(part)
            
            # Send email
            with smtplib.SMTP(Config.EMAIL_SMTP_SERVER, Config.EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_FROM, Config.EMAIL_PASSWORD)
                server.send_message(msg)
            
            self.logger.info(f"Daily report email sent to {len(Config.EMAIL_TO)} recipients")
            
        except Exception as e:
            self.logger.error(f"Failed to send email report: {e}")
            self.db.create_alert(
                'email_send_failed',
                'WARNING',
                f"Failed to send email report: {str(e)}"
            )
    
    def _create_daily_email_body(self, report_paths: Dict[str, str]) -> str:
        """Create HTML email body for daily report"""
        # Load report data for email summary
        json_path = report_paths.get('json', '')
        if json_path and os.path.exists(json_path):
            with open(json_path, 'r') as f:
                report_data = json.load(f)
        else:
            report_data = {}
        
        # Extract key metrics
        migration_data = report_data.get('report_data', {}).get('migration_data', {})
        migration_analytics = report_data.get('report_data', {}).get('migration_analytics', {})
        origins_data = report_data.get('report_data', {}).get('origins', {})
        undead_data = report_data.get('report_data', {}).get('undead', {})
        
        html_body = f"""
        <html>
        <body>
            <h2>GU Migration Daily Report - {date.today().strftime('%B %d, %Y')}</h2>
            
            <h3>🚀 Migration Summary</h3>
            <ul>
                <li><strong>New Migrations:</strong> {migration_data.get('migrations_detected', 0)}</li>
                <li><strong>Total Migrations:</strong> {migration_analytics.get('migration_rate', {}).get('total_migrations', 0)}</li>
                <li><strong>Migration Rate:</strong> {migration_analytics.get('migration_rate', {}).get('migration_rate_percent', 0)}%</li>
                <li><strong>Weekly Average:</strong> {migration_analytics.get('migration_rate', {}).get('weekly_average_daily', 0)} per day</li>
            </ul>
            
            <h3>📊 Market Performance</h3>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr>
                    <th>Collection</th>
                    <th>Floor Price (ETH)</th>
                    <th>24h Volume (ETH)</th>
                    <th>Listed %</th>
                </tr>
                <tr>
                    <td>GU Origins</td>
                    <td>{origins_data.get('current', {}).get('floor_price_eth', 0):.3f}</td>
                    <td>{origins_data.get('current', {}).get('volume_24h_eth', 0):.2f}</td>
                    <td>{origins_data.get('current', {}).get('listed_percentage', 0):.1f}%</td>
                </tr>
                <tr>
                    <td>Genuine Undead</td>
                    <td>{undead_data.get('current', {}).get('floor_price_eth', 0):.3f}</td>
                    <td>{undead_data.get('current', {}).get('volume_24h_eth', 0):.2f}</td>
                    <td>{undead_data.get('current', {}).get('listed_percentage', 0):.1f}%</td>
                </tr>
            </table>
            
            <h3>📎 Attachments</h3>
            <p>The complete daily report is attached as a PDF.</p>
            
            <p><em>Report generated by GU Migration Tracker</em></p>
        </body>
        </html>
        """
        
        return html_body
    
    def _send_weekly_summary_email(self, summary_data: Dict):
        """Send weekly summary email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_FROM
            msg['To'] = ', '.join(Config.EMAIL_TO)
            msg['Subject'] = f"GU Migration Weekly Summary - Week Ending {date.today().strftime('%B %d, %Y')}"
            
            body = self._create_weekly_email_body(summary_data)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(Config.EMAIL_SMTP_SERVER, Config.EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_FROM, Config.EMAIL_PASSWORD)
                server.send_message(msg)
            
            self.logger.info("Weekly summary email sent successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to send weekly summary email: {e}")
    
    def _create_weekly_email_body(self, summary_data: Dict) -> str:
        """Create HTML email body for weekly summary"""
        migration_analytics = summary_data.get('migration_analytics', {})
        origins_perf = summary_data.get('origins_performance', {})
        undead_perf = summary_data.get('undead_performance', {})
        alerts_summary = summary_data.get('alerts_summary', {})
        
        html_body = f"""
        <html>
        <body>
            <h2>🗓️ GU Migration Weekly Summary</h2>
            <h3>Week Ending: {summary_data.get('week_ending', '')}</h3>
            
            <h3>📈 Migration Progress</h3>
            <ul>
                <li><strong>Total Migrations:</strong> {migration_analytics.get('migration_rate', {}).get('total_migrations', 0)}</li>
                <li><strong>This Week:</strong> {summary_data.get('total_migrations_week', 0)} migrations</li>
                <li><strong>Migration Rate:</strong> {migration_analytics.get('migration_rate', {}).get('migration_rate_percent', 0)}%</li>
                <li><strong>Trend:</strong> {migration_analytics.get('migration_rate', {}).get('migration_velocity_trend', 'Unknown')}</li>
            </ul>
            
            <h3>💰 Performance Summary</h3>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr>
                    <th>Collection</th>
                    <th>Floor Price Δ</th>
                    <th>Volume Δ</th>
                    <th>Market Cap Δ</th>
                    <th>Listings Δ</th>
                </tr>
                <tr>
                    <td>GU Origins</td>
                    <td>{origins_perf.get('floor_price_change', 0):+.2f}%</td>
                    <td>{origins_perf.get('volume_change', 0):+.2f}%</td>
                    <td>{origins_perf.get('market_cap_change', 0):+.2f}%</td>
                    <td>{origins_perf.get('listing_percentage_change', 0):+.2f}%</td>
                </tr>
                <tr>
                    <td>Genuine Undead</td>
                    <td>{undead_perf.get('floor_price_change', 0):+.2f}%</td>
                    <td>{undead_perf.get('volume_change', 0):+.2f}%</td>
                    <td>{undead_perf.get('market_cap_change', 0):+.2f}%</td>
                    <td>{undead_perf.get('listing_percentage_change', 0):+.2f}%</td>
                </tr>
            </table>
            
            <h3>⚠️ System Alerts</h3>
            <ul>
                <li><strong>Unresolved Alerts:</strong> {alerts_summary.get('unresolved', 0)}</li>
                <li><strong>Critical:</strong> {alerts_summary.get('by_severity', {}).get('CRITICAL', 0)}</li>
                <li><strong>Error:</strong> {alerts_summary.get('by_severity', {}).get('ERROR', 0)}</li>
                <li><strong>Warning:</strong> {alerts_summary.get('by_severity', {}).get('WARNING', 0)}</li>
            </ul>
            
            <p><em>Weekly summary generated by GU Migration Tracker</em></p>
        </body>
        </html>
        """
        
        return html_body
    
    def start_scheduler(self):
        """Start the task scheduler"""
        self.logger.info("Starting GU Migration Tracker scheduler...")
        self.is_running = True
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def stop_scheduler(self):
        """Stop the task scheduler"""
        self.logger.info("Stopping scheduler...")
        self.is_running = False
    
    def run_manual_report(self, target_date: date = None):
        """Run report generation manually for testing"""
        try:
            self.logger.info(f"Running manual report for {target_date or date.today()}")
            
            # Run data collection first
            result = asyncio.run(run_daily_migration_detection(target_date))
            
            # Generate report
            report_paths = asyncio.run(generate_daily_report(target_date))
            
            self.logger.info(f"Manual report completed: {report_paths}")
            
            return report_paths
            
        except Exception as e:
            self.logger.error(f"Manual report failed: {e}")
            raise

# Convenience functions
def start_daily_scheduler():
    """Start the daily task scheduler"""
    scheduler = TaskScheduler()
    scheduler.setup_daily_schedule()
    scheduler.start_scheduler()

def run_manual_daily_report(target_date: date = None) -> Dict[str, str]:
    """Run daily report manually"""
    scheduler = TaskScheduler()
    return scheduler.run_manual_report(target_date)