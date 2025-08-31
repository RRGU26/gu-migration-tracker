import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import json
from jinja2 import Template
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from src.database.database import DatabaseManager
from src.api.opensea_client import fetch_all_collections_data
from src.api.price_client import get_current_eth_price
from src.utils.migration_detector import MigrationDetector, get_migration_analytics
from config.config import Config

class ReportGenerator:
    """Generates daily migration tracking reports in multiple formats"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.migration_detector = MigrationDetector()
        self.logger = logging.getLogger(__name__)
        
        # Ensure reports directory exists
        os.makedirs(Config.REPORT_OUTPUT_DIR, exist_ok=True)
        os.makedirs(f"{Config.REPORT_OUTPUT_DIR}/daily", exist_ok=True)
        os.makedirs(f"{Config.REPORT_OUTPUT_DIR}/charts", exist_ok=True)
        
        # Set up matplotlib style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    async def generate_daily_report(self, target_date: date = None) -> Dict[str, str]:
        """Generate comprehensive daily report in all formats"""
        if target_date is None:
            target_date = date.today()
        
        self.logger.info(f"Generating daily report for {target_date}")
        
        try:
            # Collect all data needed for the report
            report_data = await self._collect_report_data(target_date)
            
            # Generate charts first (needed for other formats)
            chart_paths = await self._generate_charts(report_data, target_date)
            
            # Generate reports in different formats
            markdown_path = await self._generate_markdown_report(report_data, target_date)
            json_path = await self._generate_json_report(report_data, target_date)
            pdf_path = await self._generate_pdf_report(report_data, chart_paths, target_date)
            
            self.logger.info(f"Daily report generated successfully for {target_date}")
            
            return {
                'markdown': markdown_path,
                'json': json_path,
                'pdf': pdf_path,
                'charts': chart_paths,
                'date': target_date.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate daily report for {target_date}: {e}")
            self.db.create_alert(
                'report_generation_failed',
                'ERROR',
                f"Daily report generation failed for {target_date}: {str(e)}"
            )
            raise
    
    async def _collect_report_data(self, target_date: date) -> Dict:
        """Collect all data needed for the report"""
        self.logger.info("Collecting report data...")
        
        # Get collections data
        collections_data = await fetch_all_collections_data()
        
        # Get migration data
        migration_result = await self.migration_detector.detect_daily_migrations(target_date)
        migration_analytics = get_migration_analytics()
        
        # Get daily snapshots for both collections
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        current_origins_snapshot = self.db.get_latest_snapshot(origins_id)
        current_undead_snapshot = self.db.get_latest_snapshot(undead_id)
        
        # Get previous day snapshots for comparison
        previous_date = target_date - timedelta(days=1)
        previous_origins_snapshot = self.db.get_snapshot_by_date(origins_id, previous_date)
        previous_undead_snapshot = self.db.get_snapshot_by_date(undead_id, previous_date)
        
        # Get current ETH price
        eth_price = await get_current_eth_price()
        
        # Process collections data and save snapshots
        origins_metrics = {}
        undead_metrics = {}
        
        if collections_data.get('gu_origins'):
            origins_client_data = collections_data['gu_origins']
            from src.api.opensea_client import OpenSeaClient
            client = OpenSeaClient()
            origins_metrics = client.extract_key_metrics(origins_client_data)
            origins_metrics['snapshot_date'] = target_date
            self.db.save_daily_snapshot(origins_id, origins_metrics)
        
        if collections_data.get('genuine_undead'):
            undead_client_data = collections_data['genuine_undead']
            undead_metrics = client.extract_key_metrics(undead_client_data)
            undead_metrics['snapshot_date'] = target_date
            self.db.save_daily_snapshot(undead_id, undead_metrics)
        
        # Calculate percentage changes
        origins_changes = self._calculate_changes(current_origins_snapshot, previous_origins_snapshot)
        undead_changes = self._calculate_changes(current_undead_snapshot, previous_undead_snapshot)
        
        return {
            'date': target_date,
            'eth_price_usd': eth_price,
            'migration_data': migration_result,
            'migration_analytics': migration_analytics,
            'origins': {
                'current': origins_metrics or current_origins_snapshot,
                'previous': previous_origins_snapshot,
                'changes': origins_changes,
                'raw_data': collections_data.get('gu_origins', {})
            },
            'undead': {
                'current': undead_metrics or current_undead_snapshot,
                'previous': previous_undead_snapshot,
                'changes': undead_changes,
                'raw_data': collections_data.get('genuine_undead', {})
            },
            'ecosystem': {
                'total_market_cap_eth': (origins_metrics.get('market_cap_eth', 0) + 
                                       undead_metrics.get('market_cap_eth', 0)),
                'total_volume_24h_eth': (origins_metrics.get('volume_24h_eth', 0) + 
                                       undead_metrics.get('volume_24h_eth', 0)),
                'total_holders': (origins_metrics.get('holders_count', 0) + 
                                undead_metrics.get('holders_count', 0))
            }
        }
    
    def _calculate_changes(self, current: Dict, previous: Dict) -> Dict:
        """Calculate percentage changes between snapshots"""
        if not current or not previous:
            return {}
        
        changes = {}
        metrics = ['floor_price_eth', 'volume_24h_eth', 'listed_percentage', 'market_cap_eth']
        
        for metric in metrics:
            current_val = current.get(metric, 0) or 0
            previous_val = previous.get(metric, 0) or 0
            
            if previous_val > 0:
                change_pct = ((current_val - previous_val) / previous_val) * 100
                changes[f"{metric}_change"] = round(change_pct, 2)
            else:
                changes[f"{metric}_change"] = 0
        
        return changes
    
    async def _generate_charts(self, report_data: Dict, target_date: date) -> Dict[str, str]:
        """Generate charts for the report"""
        chart_paths = {}
        chart_dir = f"{Config.REPORT_OUTPUT_DIR}/charts"
        
        try:
            # Migration progress chart
            migration_chart_path = await self._create_migration_progress_chart(
                target_date, f"{chart_dir}/migration_progress_{target_date}.png"
            )
            chart_paths['migration_progress'] = migration_chart_path
            
            # Volume comparison chart
            volume_chart_path = await self._create_volume_comparison_chart(
                report_data, f"{chart_dir}/volume_comparison_{target_date}.png"
            )
            chart_paths['volume_comparison'] = volume_chart_path
            
            # Market cap trend chart
            market_cap_chart_path = await self._create_market_cap_trend_chart(
                target_date, f"{chart_dir}/market_cap_trend_{target_date}.png"
            )
            chart_paths['market_cap_trend'] = market_cap_chart_path
            
            # Listing percentage chart
            listing_chart_path = await self._create_listing_percentage_chart(
                target_date, f"{chart_dir}/listing_percentage_{target_date}.png"
            )
            chart_paths['listing_percentage'] = listing_chart_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate charts: {e}")
        
        return chart_paths
    
    async def _create_migration_progress_chart(self, target_date: date, output_path: str) -> str:
        """Create cumulative migration progress chart"""
        # Get historical migration data
        migration_stats = self.db.get_migration_stats(30)  # Last 30 days
        daily_breakdown = migration_stats.get('daily_breakdown', [])
        
        if not daily_breakdown:
            self.logger.warning("No migration data available for chart")
            return ""
        
        # Create DataFrame for plotting
        df = pd.DataFrame(daily_breakdown)
        df['migration_date'] = pd.to_datetime(df['migration_date'])
        df = df.sort_values('migration_date')
        df['cumulative_migrations'] = df['daily_count'].cumsum()
        
        # Create the plot
        plt.figure(figsize=(12, 6))
        plt.plot(df['migration_date'], df['cumulative_migrations'], 
                marker='o', linewidth=2, markersize=4)
        
        plt.title('GU Origins → Genuine Undead Migration Progress', fontsize=16, fontweight='bold')
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Cumulative Migrations', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    async def _create_volume_comparison_chart(self, report_data: Dict, output_path: str) -> str:
        """Create volume comparison chart"""
        origins_data = report_data.get('origins', {})
        undead_data = report_data.get('undead', {})
        
        origins_volume = origins_data.get('current', {}).get('volume_24h_eth', 0)
        undead_volume = undead_data.get('current', {}).get('volume_24h_eth', 0)
        
        # Create bar chart
        plt.figure(figsize=(10, 6))
        collections = ['GU Origins', 'Genuine Undead']
        volumes = [origins_volume, undead_volume]
        colors = ['#ff6b6b', '#4ecdc4']
        
        bars = plt.bar(collections, volumes, color=colors, alpha=0.8)
        
        # Add value labels on bars
        for bar, volume in zip(bars, volumes):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{volume:.2f} ETH', ha='center', va='bottom', fontweight='bold')
        
        plt.title('24-Hour Trading Volume Comparison', fontsize=16, fontweight='bold')
        plt.ylabel('Volume (ETH)', fontsize=12)
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    async def _create_market_cap_trend_chart(self, target_date: date, output_path: str) -> str:
        """Create market cap trend chart"""
        # Get historical data for both collections
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        origins_history = self.db.get_historical_snapshots(origins_id, 14)
        undead_history = self.db.get_historical_snapshots(undead_id, 14)
        
        if not origins_history and not undead_history:
            self.logger.warning("No historical data available for market cap chart")
            return ""
        
        # Create DataFrames
        origins_df = pd.DataFrame(origins_history)
        undead_df = pd.DataFrame(undead_history)
        
        if not origins_df.empty:
            origins_df['snapshot_date'] = pd.to_datetime(origins_df['snapshot_date'])
            origins_df = origins_df.sort_values('snapshot_date')
        
        if not undead_df.empty:
            undead_df['snapshot_date'] = pd.to_datetime(undead_df['snapshot_date'])
            undead_df = undead_df.sort_values('snapshot_date')
        
        # Create the plot
        plt.figure(figsize=(12, 6))
        
        if not origins_df.empty:
            plt.plot(origins_df['snapshot_date'], origins_df['market_cap_eth'], 
                    label='GU Origins', marker='o', linewidth=2)
        
        if not undead_df.empty:
            plt.plot(undead_df['snapshot_date'], undead_df['market_cap_eth'], 
                    label='Genuine Undead', marker='s', linewidth=2)
        
        plt.title('Market Cap Trend (14 Days)', fontsize=16, fontweight='bold')
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Market Cap (ETH)', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    async def _create_listing_percentage_chart(self, target_date: date, output_path: str) -> str:
        """Create listing percentage comparison chart"""
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        origins_snapshot = self.db.get_latest_snapshot(origins_id)
        undead_snapshot = self.db.get_latest_snapshot(undead_id)
        
        origins_listed = origins_snapshot.get('listed_percentage', 0) if origins_snapshot else 0
        undead_listed = undead_snapshot.get('listed_percentage', 0) if undead_snapshot else 0
        
        # Create pie charts side by side
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # GU Origins pie chart
        origins_listed_count = origins_snapshot.get('listed_count', 0) if origins_snapshot else 0
        origins_total = origins_snapshot.get('total_supply', 0) if origins_snapshot else 0
        origins_unlisted = origins_total - origins_listed_count
        
        if origins_total > 0:
            ax1.pie([origins_listed_count, origins_unlisted], 
                   labels=['Listed', 'Unlisted'],
                   colors=['#ff6b6b', '#ffe66d'],
                   autopct='%1.1f%%',
                   startangle=90)
            ax1.set_title(f'GU Origins Listings\n({origins_listed:.1f}% listed)', fontweight='bold')
        
        # Genuine Undead pie chart
        undead_listed_count = undead_snapshot.get('listed_count', 0) if undead_snapshot else 0
        undead_total = undead_snapshot.get('total_supply', 0) if undead_snapshot else 0
        undead_unlisted = undead_total - undead_listed_count
        
        if undead_total > 0:
            ax2.pie([undead_listed_count, undead_unlisted],
                   labels=['Listed', 'Unlisted'],
                   colors=['#4ecdc4', '#95e1d3'],
                   autopct='%1.1f%%',
                   startangle=90)
            ax2.set_title(f'Genuine Undead Listings\n({undead_listed:.1f}% listed)', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    async def _generate_markdown_report(self, report_data: Dict, target_date: date) -> str:
        """Generate markdown report"""
        template_str = '''# GU Migration Daily Report - {{ report_date }}

## Executive Summary

- **Total Migrations to Date**: {{ migration_analytics.migration_rate.total_migrations | default(0) }}
- **Yesterday's Migrations**: {{ migration_data.migrations_detected }}
- **Migration Rate**: {{ migration_analytics.migration_rate.migration_rate_percent | default(0) }}% of original supply
- **Migration Velocity**: {{ migration_analytics.migration_rate.weekly_average_daily | default(0) }} per day (7-day average)

{% if migration_analytics.migration_rate.migration_velocity_trend %}
**Migration Trend**: {{ migration_analytics.migration_rate.migration_velocity_trend | title }}
{% endif %}

---

## Migration Analysis

### Daily Migration Stats
- **New migrations detected**: {{ migration_data.migrations_detected }}
- **Remaining tokens to migrate**: {{ migration_analytics.migration_rate.remaining_tokens | default(0) }}
- **Estimated completion**: {{ migration_analytics.migration_rate.estimated_days_to_complete | default("Unknown") }} days at current rate

### Migration Velocity
- **7-day average**: {{ migration_analytics.migration_rate.weekly_average_daily | default(0) }} migrations/day
- **Trend**: {{ migration_analytics.migration_rate.migration_velocity_trend | default("Unknown") }}

---

## Market Performance

### GU Origins
- **Floor Price**: {{ origins.current.floor_price_eth | default(0) | round(3) }} ETH ({{ origins.changes.floor_price_eth_change | default(0) }}% change)
- **Market Cap**: {{ origins.current.market_cap_eth | default(0) | round(1) }} ETH
- **24h Volume**: {{ origins.current.volume_24h_eth | default(0) | round(2) }} ETH ({{ origins.changes.volume_24h_eth_change | default(0) }}% change)
- **Listed**: {{ origins.current.listed_percentage | default(0) }}% ({{ origins.changes.listed_percentage_change | default(0) }}% change)

### Genuine Undead
- **Floor Price**: {{ undead.current.floor_price_eth | default(0) | round(3) }} ETH ({{ undead.changes.floor_price_eth_change | default(0) }}% change)
- **Market Cap**: {{ undead.current.market_cap_eth | default(0) | round(1) }} ETH
- **24h Volume**: {{ undead.current.volume_24h_eth | default(0) | round(2) }} ETH ({{ undead.changes.volume_24h_eth_change | default(0) }}% change)
- **Listed**: {{ undead.current.listed_percentage | default(0) }}% ({{ undead.changes.listed_percentage_change | default(0) }}% change)

### Ecosystem Overview
- **Total Market Cap**: {{ ecosystem.total_market_cap_eth | round(1) }} ETH
- **Total 24h Volume**: {{ ecosystem.total_volume_24h_eth | round(2) }} ETH
- **Total Unique Holders**: {{ ecosystem.total_holders }}

---

## Key Metrics Comparison

| Metric | GU Origins | Genuine Undead | Change |
|--------|------------|----------------|--------|
| Floor Price (ETH) | {{ origins.current.floor_price_eth | default(0) | round(3) }} | {{ undead.current.floor_price_eth | default(0) | round(3) }} | {% if (undead.current.floor_price_eth | default(0)) > (origins.current.floor_price_eth | default(0)) %}+{% endif %}{{ ((undead.current.floor_price_eth | default(0)) - (origins.current.floor_price_eth | default(0))) | round(3) }} |
| 24h Volume (ETH) | {{ origins.current.volume_24h_eth | default(0) | round(2) }} | {{ undead.current.volume_24h_eth | default(0) | round(2) }} | {% if (undead.current.volume_24h_eth | default(0)) > (origins.current.volume_24h_eth | default(0)) %}+{% endif %}{{ ((undead.current.volume_24h_eth | default(0)) - (origins.current.volume_24h_eth | default(0))) | round(2) }} |
| Listed % | {{ origins.current.listed_percentage | default(0) }}% | {{ undead.current.listed_percentage | default(0) }}% | {% if (undead.current.listed_percentage | default(0)) > (origins.current.listed_percentage | default(0)) %}+{% endif %}{{ ((undead.current.listed_percentage | default(0)) - (origins.current.listed_percentage | default(0))) | round(1) }}% |

---

## Recommendations

{% if migration_data.migrations_detected == 0 %}
- **Low Migration Activity**: Consider incentives to encourage more migrations
- **Monitor Community Sentiment**: Check Discord/Twitter for migration blockers
{% elif migration_data.migrations_detected > 10 %}
- **High Migration Activity**: Migration momentum is strong
- **Monitor Liquidity**: Ensure adequate trading activity in Genuine Undead
{% else %}
- **Steady Migration**: Current migration pace is sustainable
- **Continue Monitoring**: Track weekly trends for changes
{% endif %}

{% if (undead.current.volume_24h_eth | default(0)) < (origins.current.volume_24h_eth | default(0)) %}
- **Volume Migration Opportunity**: Genuine Undead volume is still lower than Origins
- **Market Maker Support**: Consider supporting Genuine Undead liquidity
{% endif %}

{% if (undead.current.listed_percentage | default(0)) > 15 %}
- **High Listing Rate**: {{ undead.current.listed_percentage }}% listed may indicate selling pressure
- **Community Engagement**: Engage with holders about long-term value
{% endif %}

---

## Technical Notes

- **Data Source**: OpenSea API v2
- **ETH Price**: ${{ eth_price_usd | round(2) }} USD
- **Report Generated**: {{ report_date }}
- **Migration Detection Method**: Holder comparison between daily snapshots

---

*Report generated by GU Migration Tracker v1.0*
'''
        
        template = Template(template_str)
        markdown_content = template.render(
            report_date=target_date.strftime('%B %d, %Y'),
            **report_data
        )
        
        output_path = f"{Config.REPORT_OUTPUT_DIR}/daily/daily_report_{target_date}.md"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return output_path
    
    async def _generate_json_report(self, report_data: Dict, target_date: date) -> str:
        """Generate JSON report for machine consumption"""
        # Convert date objects to strings for JSON serialization
        def serialize_dates(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            return obj
        
        json_data = {
            'report_metadata': {
                'version': '1.0',
                'generated_at': datetime.now().isoformat(),
                'report_date': target_date.isoformat(),
                'data_sources': ['OpenSea API v2', 'Internal Database']
            },
            'report_data': report_data
        }
        
        output_path = f"{Config.REPORT_OUTPUT_DIR}/daily/daily_report_{target_date}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, default=serialize_dates)
        
        return output_path
    
    async def _generate_pdf_report(self, report_data: Dict, chart_paths: Dict, target_date: date) -> str:
        """Generate PDF report"""
        output_path = f"{Config.REPORT_OUTPUT_DIR}/daily/daily_report_{target_date}.pdf"
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        
        story = []
        
        # Title
        story.append(Paragraph(f"GU Migration Daily Report", title_style))
        story.append(Paragraph(f"{target_date.strftime('%B %d, %Y')}", styles['Heading2']))
        story.append(Spacer(1, 20))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", styles['Heading2']))
        migration_analytics = report_data.get('migration_analytics', {})
        migration_rate_data = migration_analytics.get('migration_rate', {})
        migration_data = report_data.get('migration_data', {})
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Migrations to Date', str(migration_rate_data.get('total_migrations', 0))],
            ['Yesterday\'s Migrations', str(migration_data.get('migrations_detected', 0))],
            ['Migration Rate', f"{migration_rate_data.get('migration_rate_percent', 0)}%"],
            ['Weekly Average', f"{migration_rate_data.get('weekly_average_daily', 0)} per day"],
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Add charts
        if chart_paths.get('migration_progress') and os.path.exists(chart_paths['migration_progress']):
            story.append(Paragraph("Migration Progress", styles['Heading2']))
            img = Image(chart_paths['migration_progress'], width=6*inch, height=3*inch)
            story.append(img)
            story.append(Spacer(1, 20))
        
        if chart_paths.get('volume_comparison') and os.path.exists(chart_paths['volume_comparison']):
            story.append(Paragraph("Volume Comparison", styles['Heading2']))
            img = Image(chart_paths['volume_comparison'], width=6*inch, height=3.6*inch)
            story.append(img)
        
        # Build PDF
        doc.build(story)
        
        return output_path

# Convenience function
async def generate_daily_report(target_date: date = None) -> Dict[str, str]:
    """Generate daily report for specified date"""
    generator = ReportGenerator()
    return await generator.generate_daily_report(target_date)