#!/usr/bin/env python3
"""
PDF Generator for RR GU Analytic Tracker
Creates a tight, one-page PDF report perfect for Twitter
"""
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from io import BytesIO
import base64
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import json

class PDFReportGenerator:
    def __init__(self):
        self.width, self.height = letter
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        # Professional chart styling constants
        self.chart_colors = {
            'origins': '#dc2626',      # Red for GU Origins
            'undead': '#059669',       # Green for Genuine Undead
            'accent': '#3b82f6',       # Blue for accents
            'background': '#fafafa',   # Light gray background
            'grid': '#e5e7eb',         # Grid color
            'text': '#374151',         # Text color
            'text_light': '#6b7280'    # Light text color
        }
        
        self.chart_fonts = {
            'family': ['Helvetica', 'Arial', 'DejaVu Sans'],
            'title_size': 12,
            'label_size': 10,
            'tick_size': 9,
            'legend_size': 9
        }
    
    def _setup_custom_styles(self):
        """Create custom styles for the PDF"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            textColor=HexColor('#1f2937'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=HexColor('#6b7280'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        
        # Metric header style
        self.styles.add(ParagraphStyle(
            name='MetricHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=HexColor('#6b7280'),
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        
        # Metric value style
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=20,
            textColor=HexColor('#1f2937'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=HexColor('#9ca3af'),
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
    
    def generate_pdf(self, data):
        """Generate the one-page PDF report"""
        buffer = BytesIO()
        
        # Create custom canvas for more control
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Add background color header
        c.setFillColor(HexColor('#1e40af'))
        c.rect(0, self.height - 100, self.width, 100, fill=1)
        
        # Add title and timestamp
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(self.width/2, self.height - 40, "RR GU ANALYTIC TRACKER")
        
        c.setFont("Helvetica", 10)
        timestamp = datetime.now().strftime("%B %d, %Y • %I:%M %p EST")
        c.drawCentredString(self.width/2, self.height - 60, timestamp)
        
        c.setFont("Helvetica", 9)
        c.drawCentredString(self.width/2, self.height - 75, "Real-time NFT Migration Analytics")
        
        # Main content area
        y_position = self.height - 130
        
        # Key metrics section
        c.setFillColor(HexColor('#1f2937'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "MIGRATION ANALYTICS")
        y_position -= 30
        
        # Create metric boxes
        metrics = [
            ("Total Migrations", f"{data.get('total_migrations', 0):,}", "#3b82f6"),
            ("Migration Rate", f"{data.get('migration_percent', 0):.2f}%", "#10b981"),
            ("Price Ratio", f"{data.get('price_ratio', 0):.2f}x", "#8b5cf6"),
            ("Combined Market Cap", f"${data.get('ecosystem_value', 0)/1e6:.1f}M", "#f59e0b")
        ]
        
        x_positions = [80, 220, 360, 500]
        for i, (label, value, color) in enumerate(metrics):
            x = x_positions[i]
            
            # Draw colored box
            c.setFillColor(HexColor(color))
            c.rect(x - 30, y_position - 25, 120, 50, fill=0, stroke=1)
            
            # Draw label
            c.setFillColor(HexColor('#6b7280'))
            c.setFont("Helvetica", 9)
            c.drawCentredString(x + 30, y_position - 5, label)
            
            # Draw value
            c.setFillColor(HexColor(color))
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(x + 30, y_position - 20, value)
        
        y_position -= 70
        
        # Collection comparison section
        c.setFillColor(HexColor('#1f2937'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "COLLECTION METRICS")
        y_position -= 30
        
        # Create comparison table
        origins = data.get('origins', {})
        undead = data.get('undead', {})
        
        # Draw collection boxes
        collections = [
            ("GU ORIGINS", origins, "#dc2626"),
            ("GENUINE UNDEAD", undead, "#059669")
        ]
        
        for i, (name, collection, color) in enumerate(collections):
            x = 100 + (i * 250)
            
            # Collection header
            c.setFillColor(HexColor(color))
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x, y_position, name)
            
            # Collection metrics
            c.setFillColor(HexColor('#374151'))
            c.setFont("Helvetica", 10)
            
            # Format 24h change with color indicator
            floor_change = collection.get('floor_change_24h', 0)
            change_text = f"({floor_change:+.1f}%)"
            
            metrics_list = [
                f"Floor: {collection.get('floor_price_eth', 0):.4f} ETH {change_text}",
                f"Volume 24h: {collection.get('volume_24h_eth', 0):.2f} ETH",
                f"Market Cap: ${collection.get('market_cap_usd', 0)/1e6:.1f}M",
                f"Holders: {collection.get('holders_count', 0):,}",
                f"Supply: {collection.get('total_supply', 0):,}"
            ]
            
            y_offset = y_position - 20
            for metric in metrics_list:
                c.drawString(x, y_offset, metric)
                y_offset -= 15
        
        y_position -= 100
        
        # Key insights section
        c.setFillColor(HexColor('#1f2937'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "KEY INSIGHTS")
        y_position -= 25
        
        # Add insight bullets
        c.setFillColor(HexColor('#4b5563'))
        c.setFont("Helvetica", 10)
        
        # Add 24h changes to insights
        origins_change = data.get('origins', {}).get('floor_change_24h', 0)
        undead_change = data.get('undead', {}).get('floor_change_24h', 0)
        
        insights = [
            f"• {data.get('migration_percent', 0):.1f}% of Origins have migrated to Genuine Undead",
            f"• Genuine Undead trades at {data.get('price_ratio', 1):.2f}x Origins floor price",
            f"• 24h floor changes: Origins {origins_change:+.1f}%, Genuine Undead {undead_change:+.1f}%",
            f"• Combined ecosystem value: ${data.get('ecosystem_value', 0)/1e6:.1f}M"
        ]
        
        for insight in insights:
            c.drawString(70, y_position, insight)
            y_position -= 18
        
        # Add chart preview section
        y_position -= 20
        c.setFillColor(HexColor('#1f2937'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "TREND ANALYSIS")
        y_position -= 25
        
        # Draw mini chart placeholders (simplified visual indicators)
        chart_labels = ["Floor Price Trend", "Volume Activity", "Migration Flow"]
        x_positions = [100, 250, 400]
        
        for i, label in enumerate(chart_labels):
            x = x_positions[i]
            
            # Draw chart box
            c.setStrokeColor(HexColor('#e5e7eb'))
            c.rect(x, y_position - 50, 120, 50, fill=0, stroke=1)
            
            # Draw trend line (simplified)
            c.setStrokeColor(HexColor('#3b82f6'))
            c.setLineWidth(2)
            c.line(x + 10, y_position - 30, x + 40, y_position - 20)
            c.line(x + 40, y_position - 20, x + 70, y_position - 35)
            c.line(x + 70, y_position - 35, x + 110, y_position - 15)
            
            # Label
            c.setFillColor(HexColor('#6b7280'))
            c.setFont("Helvetica", 8)
            c.drawCentredString(x + 60, y_position - 60, label)
        
        # Footer
        c.setFillColor(HexColor('#9ca3af'))
        c.setFont("Helvetica", 8)
        c.drawCentredString(self.width/2, 40, "Generated by RR GU Analytic Tracker • Real-time blockchain data via OpenSea API")
        c.drawCentredString(self.width/2, 25, "Track live at: rrgu-tracker.railway.app • Data updates every 5 minutes")
        
        # Add QR code or link placeholder
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(self.width/2, 60, "🐦 Share on Twitter: @RRGU_Analytics")
        
        # Save the PDF
        c.save()
        buffer.seek(0)
        return buffer
    
    def _check_latest_data(self):
        """Check if we have the latest data from yesterday (2025-08-31)"""
        try:
            db_paths = [
                'gu_migration_tracker.db',
                'dashboard/gu_migration_tracker.db', 
                '../gu_migration_tracker.db',
                'C:/Users/rrose/gu-migration-tracker/gu_migration_tracker.db'
            ]
            
            for path in db_paths:
                try:
                    if os.path.exists(path):
                        conn = sqlite3.connect(path)
                        cursor = conn.cursor()
                        
                        # Check for 2025-08-31 data
                        cursor.execute("""
                            SELECT COUNT(*) FROM collection_data 
                            WHERE date = '2025-08-31'
                        """)
                        count = cursor.fetchone()[0]
                        conn.close()
                        
                        return count > 0
                except:
                    continue
            return False
        except:
            return False
    
    def _get_real_data_from_db(self, days_back=7):
        """Fetch real data from the database for chart generation"""
        try:
            # Look for the database in common locations
            db_paths = [
                'gu_migration_tracker.db',
                'dashboard/gu_migration_tracker.db',
                '../gu_migration_tracker.db',
                'C:/Users/rrose/gu-migration-tracker/gu_migration_tracker.db'
            ]
            
            conn = None
            for path in db_paths:
                try:
                    if os.path.exists(path):
                        conn = sqlite3.connect(path)
                        break
                except:
                    continue
            
            if not conn:
                return None
                
            cursor = conn.cursor()
            
            # Get recent collection data for charts
            cursor.execute("""
                SELECT date, collection_name, floor_price_eth, volume_24h_eth, market_cap_usd, total_supply
                FROM collection_data 
                WHERE date >= date('now', '-{} days')
                ORDER BY date ASC, collection_name
            """.format(days_back))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Organize data by collection
            data = {'dates': [], 'origins_market_cap': [], 'undead_market_cap': [], 
                   'origins_floor': [], 'undead_floor': []}
            
            date_data = {}
            for row in rows:
                date, collection, floor_eth, volume_eth, market_cap_usd, supply = row
                if date not in date_data:
                    date_data[date] = {}
                date_data[date][collection] = {
                    'floor_eth': float(floor_eth or 0),
                    'market_cap_usd': float(market_cap_usd or 0),
                    'volume_eth': float(volume_eth or 0)
                }
            
            # Convert to chart-friendly format
            sorted_dates = sorted(date_data.keys())
            for date in sorted_dates:
                data['dates'].append(datetime.strptime(date, '%Y-%m-%d'))
                
                origins_data = date_data[date].get('GU Origins', {})
                undead_data = date_data[date].get('Genuine Undead', {})
                
                data['origins_market_cap'].append(origins_data.get('market_cap_usd', 0))
                data['undead_market_cap'].append(undead_data.get('market_cap_usd', 0))
                data['origins_floor'].append(origins_data.get('floor_eth', 0))
                data['undead_floor'].append(undead_data.get('floor_eth', 0))
            
            return data if data['dates'] else None
            
        except Exception as e:
            print(f"Error fetching real data: {e}")
            return None
    
    def _create_chart_image(self, chart_data, chart_type="market_cap"):
        """Create professional chart image with real data and return as BytesIO buffer"""
        # Set professional styling parameters using constants
        plt.rcParams.update({
            'font.size': self.chart_fonts['label_size'],
            'font.family': 'sans-serif',
            'font.sans-serif': self.chart_fonts['family'],
            'axes.titlesize': self.chart_fonts['title_size'],
            'axes.labelsize': self.chart_fonts['label_size'],
            'xtick.labelsize': self.chart_fonts['tick_size'],
            'ytick.labelsize': self.chart_fonts['tick_size'],
            'legend.fontsize': self.chart_fonts['legend_size'],
            'axes.spines.top': False,
            'axes.spines.right': False,
            'axes.linewidth': 1.2,
            'axes.edgecolor': '#cccccc',
            'grid.linewidth': 0.8,
            'grid.alpha': 0.2,
            'grid.color': self.chart_colors['grid']
        })
        
        # Get real data from database
        real_data = self._get_real_data_from_db()
        
        # Create figure with professional sizing and DPI
        if chart_type == "market_cap":
            fig, ax = plt.subplots(figsize=(5, 3.2), dpi=120, facecolor='white')
        else:
            fig, ax = plt.subplots(figsize=(5, 2.8), dpi=120, facecolor='white')
        
        # Set clean background
        ax.set_facecolor(self.chart_colors['background'])
        
        if chart_type == "market_cap":
            # Market Cap Chart with Real Data
            if real_data and real_data['dates'] and any(real_data['origins_market_cap']) and any(real_data['undead_market_cap']):
                # Plot with professional styling
                ax.plot(real_data['dates'], real_data['origins_market_cap'], 
                       color=self.chart_colors['origins'], linewidth=2.5, label='GU Origins', 
                       marker='o', markersize=4, markerfacecolor=self.chart_colors['origins'], markeredgecolor='white', markeredgewidth=1)
                
                ax.plot(real_data['dates'], real_data['undead_market_cap'], 
                       color=self.chart_colors['undead'], linewidth=2.5, label='Genuine Undead', 
                       marker='o', markersize=4, markerfacecolor=self.chart_colors['undead'], markeredgecolor='white', markeredgewidth=1)
                
                # Format y-axis for currency
                ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1e6:.1f}M' if x >= 1e6 else f'${x/1e3:.0f}K'))
                
                # Professional title and labels
                ax.set_title('Market Cap Comparison', fontsize=self.chart_fonts['title_size'], fontweight='600', color='#1e293b', pad=15)
                ax.set_ylabel('Market Cap (USD)', fontsize=self.chart_fonts['label_size'], color=self.chart_colors['text'], fontweight='500')
                
                # Enhanced legend
                legend = ax.legend(loc='upper left', fontsize=9, frameon=True, 
                                 fancybox=True, shadow=False, framealpha=0.95,
                                 edgecolor='#e5e7eb', facecolor='white')
                legend.get_frame().set_linewidth(1)
                
                # Format dates on x-axis
                if len(real_data['dates']) > 1:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(real_data['dates'])//4)))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            else:
                # Check if we should show real data message or placeholder
                has_latest = self._check_latest_data()
                if has_latest:
                    placeholder_text = 'Insufficient data points\nfor trend analysis'
                else:
                    placeholder_text = 'Latest: Aug 31, 2025\nGU Origins: 0.0667 ETH\nGenuine Undead: 0.0555 ETH'
                
                ax.text(0.5, 0.5, placeholder_text, 
                       ha='center', va='center', transform=ax.transAxes, 
                       fontsize=10, color='#6b7280', fontweight='500')
                ax.set_title('Market Cap Trends', fontsize=self.chart_fonts['title_size'], fontweight='600', color='#1e293b')
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
        
        elif chart_type == "migration":
            # Migration Activity Chart
            # For now, show a placeholder since migration tracking isn't implemented yet
            ax.text(0.5, 0.5, 'Migration tracking\ncoming soon', 
                   ha='center', va='center', transform=ax.transAxes, 
                   fontsize=11, color='#6b7280', fontweight='500')
            ax.set_title('Migration Activity', fontsize=self.chart_fonts['title_size'], fontweight='600', color='#1e293b')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        
        elif chart_type == "floor_price":
            # Floor Price Comparison Chart
            if real_data and real_data['dates'] and any(real_data['origins_floor']) and any(real_data['undead_floor']):
                # Plot floor prices
                ax.plot(real_data['dates'], real_data['origins_floor'], 
                       color=self.chart_colors['origins'], linewidth=2.5, label='GU Origins', 
                       marker='s', markersize=4, markerfacecolor=self.chart_colors['origins'], markeredgecolor='white', markeredgewidth=1)
                
                ax.plot(real_data['dates'], real_data['undead_floor'], 
                       color=self.chart_colors['undead'], linewidth=2.5, label='Genuine Undead', 
                       marker='s', markersize=4, markerfacecolor=self.chart_colors['undead'], markeredgecolor='white', markeredgewidth=1)
                
                # Format y-axis for ETH
                ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.3f} ETH'))
                
                ax.set_title('Floor Price Comparison', fontsize=self.chart_fonts['title_size'], fontweight='600', color='#1e293b', pad=15)
                ax.set_ylabel('Floor Price (ETH)', fontsize=self.chart_fonts['label_size'], color=self.chart_colors['text'], fontweight='500')
                
                # Enhanced legend
                legend = ax.legend(loc='upper left', fontsize=9, frameon=True, 
                                 fancybox=True, shadow=False, framealpha=0.95,
                                 edgecolor='#e5e7eb', facecolor='white')
                legend.get_frame().set_linewidth(1)
                
                # Format dates
                if len(real_data['dates']) > 1:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(real_data['dates'])//4)))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            else:
                # Show latest known data if no trend data
                has_latest = self._check_latest_data()
                if has_latest:
                    placeholder_text = 'Insufficient data points\nfor trend analysis'
                else:
                    placeholder_text = 'Latest: Aug 31, 2025\nGU Origins: 0.0667 ETH\nGenuine Undead: 0.0555 ETH'
                
                ax.text(0.5, 0.5, placeholder_text, 
                       ha='center', va='center', transform=ax.transAxes, 
                       fontsize=10, color='#6b7280', fontweight='500')
                ax.set_title('Floor Price Trends', fontsize=self.chart_fonts['title_size'], fontweight='600', color='#1e293b')
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
        
        # Professional grid styling
        ax.grid(True, linestyle='-', alpha=0.2, color=self.chart_colors['grid'])
        ax.set_axisbelow(True)
        
        # Clean up tick styling
        ax.tick_params(axis='both', which='major', labelcolor=self.chart_colors['text'], 
                      colors='#9ca3af', length=4, width=1)
        
        # Enhance legend styling for all charts with legends
        if ax.legend_:
            legend = ax.legend_
            legend.get_frame().set_facecolor('white')
            legend.get_frame().set_edgecolor(self.chart_colors['grid'])
            legend.get_frame().set_linewidth(1)
            legend.get_frame().set_alpha(0.95)
        
        # Remove unnecessary whitespace
        plt.tight_layout(pad=1.5)
        
        # Save with high quality
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=120, bbox_inches='tight', 
                   facecolor='white', edgecolor='none', pad_inches=0.1)
        plt.close()
        img_buffer.seek(0)
        return img_buffer
    
    def generate_compact_report(self, data):
        """Generate enhanced report with charts for Twitter"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(600, 600))  # Reduced height to eliminate white space
        
        # Gradient background effect - made taller for ETH price
        c.setFillColor(HexColor('#1e293b'))
        c.rect(0, 540, 600, 60, fill=1)
        
        # Title
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(300, 575, "RR GU ANALYTIC TRACKER")
        
        # Timestamp
        c.setFont("Helvetica", 9)
        timestamp = datetime.now().strftime("%b %d, %Y • %I:%M %p")
        c.drawCentredString(300, 560, timestamp)
        
        # ETH Price display - moved down to be visible
        eth_price = data.get('eth_price', 0)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(300, 545, f"⟠ ETH: ${eth_price:,.2f}")
        
        # Main metrics grid - adjusted for 600px height
        y = 510
        metrics = [
            ("MIGRATIONS", f"{data.get('total_migrations', 0):,}", "#3b82f6"),
            ("MIGRATION %", f"{data.get('migration_percent', 0):.2f}%", "#10b981"),
            ("PRICE RATIO", f"{data.get('price_ratio', 0):.2f}x", "#8b5cf6"),
            ("MARKET CAP", f"${data.get('ecosystem_value', 0)/1e6:.1f}M", "#f59e0b")
        ]
        
        x_positions = [100, 233, 366, 500]
        for i, (label, value, color) in enumerate(metrics):
            x = x_positions[i]
            
            c.setFillColor(HexColor('#374151'))
            c.setFont("Helvetica", 9)
            c.drawCentredString(x, y, label)
            
            c.setFillColor(HexColor(color))
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(x, y - 20, value)
        
        # Generate and place charts - adjusted for 600px height
        y_charts = 440
        
        # Market Cap Change Chart with Real Data
        try:
            mc_chart_img = self._create_chart_image(None, "market_cap")
            from reportlab.lib.utils import ImageReader
            c.drawImage(ImageReader(mc_chart_img), 50, y_charts - 120, width=240, height=120)
        except Exception as e:
            print(f"Error creating market cap chart: {e}")
            # Draw professional placeholder if chart fails
            c.setFillColor(HexColor('#f8fafc'))
            c.rect(50, y_charts - 120, 240, 120, fill=1, stroke=0)
            c.setStrokeColor(HexColor('#e2e8f0'))
            c.rect(50, y_charts - 120, 240, 120, fill=0, stroke=1)
            c.setFillColor(HexColor('#64748b'))
            c.setFont("Helvetica", 10)
            c.drawCentredString(170, y_charts - 55, "Chart temporarily unavailable")
            c.setFont("Helvetica", 8)
            c.drawCentredString(170, y_charts - 70, "Real data loading...")
        
        # Floor Price Comparison Chart (more useful than migration for now)
        try:
            floor_chart_img = self._create_chart_image(None, "floor_price")
            from reportlab.lib.utils import ImageReader
            c.drawImage(ImageReader(floor_chart_img), 310, y_charts - 120, width=240, height=120)
        except Exception as e:
            print(f"Error creating floor price chart: {e}")
            # Draw professional placeholder if chart fails
            c.setFillColor(HexColor('#f8fafc'))
            c.rect(310, y_charts - 120, 240, 120, fill=1, stroke=0)
            c.setStrokeColor(HexColor('#e2e8f0'))
            c.rect(310, y_charts - 120, 240, 120, fill=0, stroke=1)
            c.setFillColor(HexColor('#64748b'))
            c.setFont("Helvetica", 10)
            c.drawCentredString(430, y_charts - 55, "Chart temporarily unavailable")
            c.setFont("Helvetica", 8)
            c.drawCentredString(430, y_charts - 70, "Real data loading...")
        
        # Chart titles
        c.setFillColor(HexColor('#1e293b'))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(170, y_charts - 135, "📈 Market Cap Trends")
        c.drawCentredString(430, y_charts - 135, "💰 Floor Price Trends")
        
        # Collection comparison section with enhanced styling - adjusted for 600px height
        y = 270
        
        # Draw collection cards with subtle backgrounds
        c.setFillColor(HexColor('#f8fafc'))
        c.rect(40, y - 45, 250, 60, fill=1, stroke=0)
        c.rect(310, y - 45, 250, 60, fill=1, stroke=0)
        
        # Collection headers with icons
        c.setFillColor(HexColor('#dc2626'))  # Red for Origins
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "🔴 GU ORIGINS")
        
        c.setFillColor(HexColor('#059669'))  # Green for Undead
        c.drawString(320, y, "💀 GENUINE UNDEAD")
        
        origins = data.get('origins', {})
        undead = data.get('undead', {})
        
        # Origins stats with icons and enhanced formatting - adjusted for 600px height
        y = 250
        origins_change = origins.get('floor_change_24h', 0)
        undead_change = undead.get('floor_change_24h', 0)
        
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor('#374151'))
        
        # Origins with change color coding
        floor_color = HexColor('#dc2626') if origins_change < 0 else HexColor('#059669')
        c.setFillColor(floor_color)
        c.drawString(50, y, f"💰 Floor: {origins.get('floor_price_eth', 0):.4f} ETH ({origins_change:+.1f}%)")
        
        c.setFillColor(HexColor('#374151'))
        c.drawString(50, y - 15, f"📊 Volume: {origins.get('volume_24h_eth', 0):.2f} ETH")
        c.drawString(50, y - 30, f"📦 Supply: {origins.get('total_supply', 0):,}")
        
        # Undead with change color coding
        floor_color = HexColor('#dc2626') if undead_change < 0 else HexColor('#059669')
        c.setFillColor(floor_color)
        c.drawString(320, y, f"💰 Floor: {undead.get('floor_price_eth', 0):.4f} ETH ({undead_change:+.1f}%)")
        
        c.setFillColor(HexColor('#374151'))
        c.drawString(320, y - 15, f"📊 Volume: {undead.get('volume_24h_eth', 0):.2f} ETH")
        c.drawString(320, y - 30, f"📦 Supply: {undead.get('total_supply', 0):,}")
        
        # Visual separator - adjusted for 600px height
        c.setStrokeColor(HexColor('#e5e7eb'))
        c.setLineWidth(1)
        c.line(50, 180, 550, 180)
        
        # Enhanced insight section with background - adjusted for 600px height
        c.setFillColor(HexColor('#eff6ff'))
        c.rect(40, 120, 520, 50, fill=1, stroke=0)
        
        # Main insight with icon
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 13)
        insight = f"🎯 {data.get('migration_percent', 0):.1f}% of Origins migrated → {data.get('price_ratio', 1):.2f}x premium"
        c.drawCentredString(300, 155, insight)
        
        # Add 24h change summary with trend icons
        origins_change = data.get('origins', {}).get('floor_change_24h', 0)
        undead_change = data.get('undead', {}).get('floor_change_24h', 0)
        
        origins_icon = "📈" if origins_change >= 0 else "📉"
        undead_icon = "📈" if undead_change >= 0 else "📉"
        
        c.setFillColor(HexColor('#374151'))
        c.setFont("Helvetica", 11)
        change_summary = f"{origins_icon} Origins {origins_change:+.1f}% • {undead_icon} Genuine Undead {undead_change:+.1f}%"
        c.drawCentredString(300, 135, change_summary)
        
        # Professional footer with enhanced styling - smaller for 600px height
        c.setFillColor(HexColor('#1e293b'))
        c.rect(0, 0, 600, 35, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#cbd5e1'))
        c.setFont("Helvetica", 8)
        c.drawCentredString(300, 20, "⚡ Real-time blockchain analytics • Generated by RR GU Analytic Tracker")
        
        # Twitter handle with enhanced styling
        c.setFillColor(HexColor('#38bdf8'))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(300, 8, "🐦 @RRGU_Analytics • Share this report! 🚀")
        
        c.save()
        buffer.seek(0)
        return buffer