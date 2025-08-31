import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from src.database.database import DatabaseManager

class DataVisualizer:
    """Create visualizations for GU migration data"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)
        
        # Set up styling
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        
        # Custom color palette
        self.colors = {
            'origins': '#FF6B6B',      # Red-ish for GU Origins
            'undead': '#4ECDC4',       # Teal for Genuine Undead  
            'migration': '#45B7D1',    # Blue for migration data
            'volume': '#96CEB4',       # Green for volume
            'price': '#FFEAA7',        # Yellow for price
            'negative': '#FF7675',     # Red for negative changes
            'positive': '#00B894'      # Green for positive changes
        }
    
    def create_migration_timeline(self, days: int = 30, save_path: str = None) -> str:
        """Create a timeline chart showing daily migrations"""
        migration_stats = self.db.get_migration_stats(days)
        daily_breakdown = migration_stats.get('daily_breakdown', [])
        
        if not daily_breakdown:
            self.logger.warning("No migration data available for timeline")
            return ""
        
        # Convert to DataFrame
        df = pd.DataFrame(daily_breakdown)
        df['migration_date'] = pd.to_datetime(df['migration_date'])
        df = df.sort_values('migration_date')
        
        # Fill missing dates with zero migrations
        date_range = pd.date_range(start=df['migration_date'].min(), 
                                 end=df['migration_date'].max(), 
                                 freq='D')
        df = df.set_index('migration_date').reindex(date_range, fill_value=0).reset_index()
        df.columns = ['migration_date', 'daily_count', 'from_collection_id', 'to_collection_id']
        
        # Create the plot
        plt.figure(figsize=(14, 8))
        
        # Daily migration bars
        bars = plt.bar(df['migration_date'], df['daily_count'], 
                      color=self.colors['migration'], alpha=0.7, label='Daily Migrations')
        
        # Cumulative line
        cumulative = df['daily_count'].cumsum()
        plt.plot(df['migration_date'], cumulative, 
                color=self.colors['origins'], linewidth=3, 
                marker='o', markersize=4, label='Cumulative Migrations')
        
        # Add trend line
        x_numeric = np.arange(len(df))
        z = np.polyfit(x_numeric, df['daily_count'], 1)
        p = np.poly1d(z)
        plt.plot(df['migration_date'], p(x_numeric), 
                linestyle='--', color='gray', alpha=0.8, label='Trend')
        
        plt.title('GU Origins → Genuine Undead Migration Timeline', 
                 fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Number of Migrations', fontsize=12)
        plt.legend(loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Add annotations for significant events
        max_day = df.loc[df['daily_count'].idxmax()]
        if max_day['daily_count'] > 0:
            plt.annotate(f'Peak: {int(max_day["daily_count"])} migrations',
                        xy=(max_day['migration_date'], max_day['daily_count']),
                        xytext=(10, 10), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Migration timeline saved to {save_path}")
        
        return save_path or "migration_timeline.png"
    
    def create_collection_comparison(self, save_path: str = None) -> str:
        """Create a comprehensive comparison of both collections"""
        # Get latest snapshots
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        origins_data = self.db.get_latest_snapshot(origins_id)
        undead_data = self.db.get_latest_snapshot(undead_id)
        
        if not origins_data or not undead_data:
            self.logger.warning("Missing collection data for comparison")
            return ""
        
        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('GU Collections Comparison Dashboard', fontsize=18, fontweight='bold')
        
        # 1. Floor Price Comparison
        collections = ['GU Origins', 'Genuine Undead']
        floor_prices = [origins_data.get('floor_price_eth', 0), undead_data.get('floor_price_eth', 0)]
        
        bars1 = ax1.bar(collections, floor_prices, 
                       color=[self.colors['origins'], self.colors['undead']], alpha=0.8)
        ax1.set_title('Floor Price Comparison', fontweight='bold')
        ax1.set_ylabel('Price (ETH)')
        
        # Add value labels
        for bar, price in zip(bars1, floor_prices):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{price:.3f} ETH', ha='center', va='bottom', fontweight='bold')
        
        # 2. Volume Comparison
        volumes_24h = [origins_data.get('volume_24h_eth', 0), undead_data.get('volume_24h_eth', 0)]
        
        bars2 = ax2.bar(collections, volumes_24h,
                       color=[self.colors['origins'], self.colors['undead']], alpha=0.8)
        ax2.set_title('24h Volume Comparison', fontweight='bold')
        ax2.set_ylabel('Volume (ETH)')
        
        for bar, volume in zip(bars2, volumes_24h):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{volume:.2f} ETH', ha='center', va='bottom', fontweight='bold')
        
        # 3. Market Cap Comparison
        market_caps = [origins_data.get('market_cap_eth', 0), undead_data.get('market_cap_eth', 0)]
        
        bars3 = ax3.bar(collections, market_caps,
                       color=[self.colors['origins'], self.colors['undead']], alpha=0.8)
        ax3.set_title('Market Cap Comparison', fontweight='bold')
        ax3.set_ylabel('Market Cap (ETH)')
        
        for bar, cap in zip(bars3, market_caps):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{cap:.1f} ETH', ha='center', va='bottom', fontweight='bold')
        
        # 4. Listing Percentage Pie Chart
        origins_listed = origins_data.get('listed_percentage', 0)
        undead_listed = undead_data.get('listed_percentage', 0)
        
        listing_data = [origins_listed, undead_listed]
        wedges, texts, autotexts = ax4.pie(listing_data, labels=collections,
                                          colors=[self.colors['origins'], self.colors['undead']],
                                          autopct='%1.1f%%', startangle=90)
        ax4.set_title('Listing Percentage Distribution', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Collection comparison saved to {save_path}")
        
        return save_path or "collection_comparison.png"
    
    def create_migration_velocity_chart(self, days: int = 14, save_path: str = None) -> str:
        """Create a chart showing migration velocity trends"""
        migration_stats = self.db.get_migration_stats(days)
        daily_breakdown = migration_stats.get('daily_breakdown', [])
        
        if not daily_breakdown:
            self.logger.warning("No migration data for velocity chart")
            return ""
        
        df = pd.DataFrame(daily_breakdown)
        df['migration_date'] = pd.to_datetime(df['migration_date'])
        df = df.sort_values('migration_date')
        
        # Calculate rolling averages
        df['3_day_avg'] = df['daily_count'].rolling(window=3, center=True).mean()
        df['7_day_avg'] = df['daily_count'].rolling(window=7, center=True).mean()
        
        plt.figure(figsize=(14, 8))
        
        # Daily migrations (bars)
        plt.bar(df['migration_date'], df['daily_count'], 
                alpha=0.6, color=self.colors['migration'], label='Daily Migrations')
        
        # Rolling averages (lines)
        plt.plot(df['migration_date'], df['3_day_avg'], 
                color=self.colors['origins'], linewidth=2, label='3-Day Average')
        plt.plot(df['migration_date'], df['7_day_avg'], 
                color=self.colors['undead'], linewidth=2, label='7-Day Average')
        
        plt.title('Migration Velocity Trends', fontsize=16, fontweight='bold')
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Migrations per Day', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Migration velocity chart saved to {save_path}")
        
        return save_path or "migration_velocity.png"
    
    def create_holder_distribution_chart(self, save_path: str = None) -> str:
        """Create a chart showing holder distribution between collections"""
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        origins_data = self.db.get_latest_snapshot(origins_id)
        undead_data = self.db.get_latest_snapshot(undead_id)
        
        if not origins_data or not undead_data:
            self.logger.warning("Missing data for holder distribution chart")
            return ""
        
        # Get holder counts
        origins_holders = origins_data.get('holders_count', 0)
        undead_holders = undead_data.get('holders_count', 0)
        
        # Estimate overlap (this would be more accurate with actual address data)
        total_unique = int(origins_holders + undead_holders * 0.8)  # Assume 20% overlap
        overlap_estimate = origins_holders + undead_holders - total_unique
        
        # Create Venn diagram style visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Pie chart of current holders
        holder_data = [origins_holders, undead_holders]
        labels = [f'GU Origins\n({origins_holders} holders)', 
                 f'Genuine Undead\n({undead_holders} holders)']
        
        ax1.pie(holder_data, labels=labels, 
               colors=[self.colors['origins'], self.colors['undead']],
               autopct='%1.1f%%', startangle=90, explode=(0.05, 0.05))
        ax1.set_title('Current Holder Distribution', fontweight='bold', pad=20)
        
        # Historical trend (if we have data)
        origins_history = self.db.get_historical_snapshots(origins_id, 30)
        undead_history = self.db.get_historical_snapshots(undead_id, 30)
        
        if origins_history and undead_history:
            origins_df = pd.DataFrame(origins_history)
            undead_df = pd.DataFrame(undead_history)
            
            origins_df['snapshot_date'] = pd.to_datetime(origins_df['snapshot_date'])
            undead_df['snapshot_date'] = pd.to_datetime(undead_df['snapshot_date'])
            
            ax2.plot(origins_df['snapshot_date'], origins_df['holders_count'],
                    color=self.colors['origins'], linewidth=2, marker='o', 
                    markersize=4, label='GU Origins')
            ax2.plot(undead_df['snapshot_date'], undead_df['holders_count'],
                    color=self.colors['undead'], linewidth=2, marker='s',
                    markersize=4, label='Genuine Undead')
            
            ax2.set_title('Holder Count Trend (30 Days)', fontweight='bold')
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Number of Holders')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.tick_params(axis='x', rotation=45)
        else:
            ax2.text(0.5, 0.5, 'Insufficient historical\ndata available', 
                    ha='center', va='center', fontsize=14,
                    bbox=dict(boxstyle='round', facecolor='lightgray'))
            ax2.set_title('Holder Trend (Insufficient Data)', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Holder distribution chart saved to {save_path}")
        
        return save_path or "holder_distribution.png"
    
    def create_ecosystem_health_dashboard(self, save_path: str = None) -> str:
        """Create a comprehensive ecosystem health dashboard"""
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
        
        # Title
        fig.suptitle('GU Ecosystem Health Dashboard', fontsize=20, fontweight='bold', y=0.95)
        
        # Get data
        origins_id = self.db.get_collection_id('gu-origins')
        undead_id = self.db.get_collection_id('genuine-undead')
        
        # 1. Migration Progress (top left, spans 2 columns)
        ax1 = fig.add_subplot(gs[0, :2])
        self._add_migration_progress_subplot(ax1)
        
        # 2. Volume Trends (top right, spans 2 columns)
        ax2 = fig.add_subplot(gs[0, 2:])
        self._add_volume_trends_subplot(ax2, origins_id, undead_id)
        
        # 3. Price Comparison (middle left)
        ax3 = fig.add_subplot(gs[1, 0])
        self._add_price_comparison_subplot(ax3, origins_id, undead_id)
        
        # 4. Market Cap (middle center)
        ax4 = fig.add_subplot(gs[1, 1])
        self._add_market_cap_subplot(ax4, origins_id, undead_id)
        
        # 5. Listing Activity (middle right)
        ax5 = fig.add_subplot(gs[1, 2])
        self._add_listing_activity_subplot(ax5, origins_id, undead_id)
        
        # 6. Ecosystem Metrics (middle far right)
        ax6 = fig.add_subplot(gs[1, 3])
        self._add_ecosystem_metrics_subplot(ax6, origins_id, undead_id)
        
        # 7. Migration Velocity (bottom, spans all columns)
        ax7 = fig.add_subplot(gs[2, :])
        self._add_velocity_analysis_subplot(ax7)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Ecosystem health dashboard saved to {save_path}")
        
        return save_path or "ecosystem_health_dashboard.png"
    
    def _add_migration_progress_subplot(self, ax):
        """Add migration progress to subplot"""
        migration_stats = self.db.get_migration_stats(30)
        daily_breakdown = migration_stats.get('daily_breakdown', [])
        
        if daily_breakdown:
            df = pd.DataFrame(daily_breakdown)
            df['migration_date'] = pd.to_datetime(df['migration_date'])
            df = df.sort_values('migration_date')
            df['cumulative'] = df['daily_count'].cumsum()
            
            ax.bar(df['migration_date'], df['daily_count'], 
                  alpha=0.6, color=self.colors['migration'], label='Daily')
            ax.plot(df['migration_date'], df['cumulative'], 
                   color=self.colors['origins'], linewidth=2, 
                   marker='o', markersize=3, label='Cumulative')
            
        ax.set_title('Migration Progress (30 Days)', fontweight='bold')
        ax.set_ylabel('Migrations')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _add_volume_trends_subplot(self, ax, origins_id, undead_id):
        """Add volume trends to subplot"""
        origins_history = self.db.get_historical_snapshots(origins_id, 14)
        undead_history = self.db.get_historical_snapshots(undead_id, 14)
        
        if origins_history:
            origins_df = pd.DataFrame(origins_history)
            origins_df['snapshot_date'] = pd.to_datetime(origins_df['snapshot_date'])
            ax.plot(origins_df['snapshot_date'], origins_df['volume_24h_eth'],
                   color=self.colors['origins'], linewidth=2, label='GU Origins')
        
        if undead_history:
            undead_df = pd.DataFrame(undead_history)
            undead_df['snapshot_date'] = pd.to_datetime(undead_df['snapshot_date'])
            ax.plot(undead_df['snapshot_date'], undead_df['volume_24h_eth'],
                   color=self.colors['undead'], linewidth=2, label='Genuine Undead')
        
        ax.set_title('24h Volume Trends', fontweight='bold')
        ax.set_ylabel('Volume (ETH)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _add_price_comparison_subplot(self, ax, origins_id, undead_id):
        """Add price comparison to subplot"""
        origins_data = self.db.get_latest_snapshot(origins_id)
        undead_data = self.db.get_latest_snapshot(undead_id)
        
        if origins_data and undead_data:
            prices = [origins_data.get('floor_price_eth', 0), undead_data.get('floor_price_eth', 0)]
            bars = ax.bar(['Origins', 'Undead'], prices,
                         color=[self.colors['origins'], self.colors['undead']], alpha=0.8)
            
            for bar, price in zip(bars, prices):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{price:.3f}', ha='center', va='bottom', fontsize=10)
        
        ax.set_title('Floor Prices', fontweight='bold')
        ax.set_ylabel('ETH')
    
    def _add_market_cap_subplot(self, ax, origins_id, undead_id):
        """Add market cap to subplot"""
        origins_data = self.db.get_latest_snapshot(origins_id)
        undead_data = self.db.get_latest_snapshot(undead_id)
        
        if origins_data and undead_data:
            caps = [origins_data.get('market_cap_eth', 0), undead_data.get('market_cap_eth', 0)]
            bars = ax.bar(['Origins', 'Undead'], caps,
                         color=[self.colors['origins'], self.colors['undead']], alpha=0.8)
            
            for bar, cap in zip(bars, caps):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{cap:.0f}', ha='center', va='bottom', fontsize=10)
        
        ax.set_title('Market Cap', fontweight='bold')
        ax.set_ylabel('ETH')
    
    def _add_listing_activity_subplot(self, ax, origins_id, undead_id):
        """Add listing activity to subplot"""
        origins_data = self.db.get_latest_snapshot(origins_id)
        undead_data = self.db.get_latest_snapshot(undead_id)
        
        if origins_data and undead_data:
            listing_pcts = [origins_data.get('listed_percentage', 0), 
                           undead_data.get('listed_percentage', 0)]
            bars = ax.bar(['Origins', 'Undead'], listing_pcts,
                         color=[self.colors['origins'], self.colors['undead']], alpha=0.8)
            
            for bar, pct in zip(bars, listing_pcts):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{pct:.1f}%', ha='center', va='bottom', fontsize=10)
        
        ax.set_title('Listed %', fontweight='bold')
        ax.set_ylabel('Percentage')
    
    def _add_ecosystem_metrics_subplot(self, ax, origins_id, undead_id):
        """Add ecosystem metrics to subplot"""
        total_migrations = self.db.get_total_migrations()
        
        # Create a simple metric display
        ax.text(0.5, 0.8, f'Total Migrations', ha='center', va='center', 
               fontsize=12, fontweight='bold', transform=ax.transAxes)
        ax.text(0.5, 0.6, f'{total_migrations}', ha='center', va='center', 
               fontsize=20, fontweight='bold', color=self.colors['migration'],
               transform=ax.transAxes)
        
        # Add migration rate if available
        origins_data = self.db.get_latest_snapshot(origins_id)
        if origins_data:
            total_supply = origins_data.get('total_supply', 1)
            migration_rate = (total_migrations / total_supply) * 100 if total_supply > 0 else 0
            ax.text(0.5, 0.4, f'Migration Rate', ha='center', va='center',
                   fontsize=10, transform=ax.transAxes)
            ax.text(0.5, 0.2, f'{migration_rate:.1f}%', ha='center', va='center',
                   fontsize=16, fontweight='bold', color=self.colors['undead'],
                   transform=ax.transAxes)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
    
    def _add_velocity_analysis_subplot(self, ax):
        """Add velocity analysis to subplot"""
        migration_stats = self.db.get_migration_stats(21)  # 3 weeks
        daily_breakdown = migration_stats.get('daily_breakdown', [])
        
        if daily_breakdown:
            df = pd.DataFrame(daily_breakdown)
            df['migration_date'] = pd.to_datetime(df['migration_date'])
            df = df.sort_values('migration_date')
            
            # Calculate moving averages
            df['7_day_avg'] = df['daily_count'].rolling(window=7, center=True).mean()
            df['3_day_avg'] = df['daily_count'].rolling(window=3, center=True).mean()
            
            # Plot daily migrations
            ax.bar(df['migration_date'], df['daily_count'], 
                  alpha=0.4, color=self.colors['migration'], label='Daily Migrations')
            
            # Plot moving averages
            ax.plot(df['migration_date'], df['3_day_avg'], 
                   color=self.colors['origins'], linewidth=2, label='3-Day Average')
            ax.plot(df['migration_date'], df['7_day_avg'], 
                   color=self.colors['undead'], linewidth=2, label='7-Day Average')
        
        ax.set_title('Migration Velocity Analysis (3 Weeks)', fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Migrations per Day')
        ax.legend()
        ax.grid(True, alpha=0.3)

# Convenience functions
def create_all_visualizations(output_dir: str = "reports/charts") -> Dict[str, str]:
    """Create all standard visualizations and return file paths"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    visualizer = DataVisualizer()
    today = date.today()
    
    chart_paths = {}
    
    try:
        chart_paths['timeline'] = visualizer.create_migration_timeline(
            30, f"{output_dir}/migration_timeline_{today}.png"
        )
        chart_paths['comparison'] = visualizer.create_collection_comparison(
            f"{output_dir}/collection_comparison_{today}.png"
        )
        chart_paths['velocity'] = visualizer.create_migration_velocity_chart(
            14, f"{output_dir}/migration_velocity_{today}.png"
        )
        chart_paths['holders'] = visualizer.create_holder_distribution_chart(
            f"{output_dir}/holder_distribution_{today}.png"
        )
        chart_paths['dashboard'] = visualizer.create_ecosystem_health_dashboard(
            f"{output_dir}/ecosystem_dashboard_{today}.png"
        )
    except Exception as e:
        logging.error(f"Failed to create visualizations: {e}")
    
    return chart_paths