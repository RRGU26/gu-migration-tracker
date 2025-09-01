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

class PDFReportGenerator:
    def __init__(self):
        self.width, self.height = letter
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
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
    
    def generate_compact_report(self, data):
        """Generate ultra-compact version for Twitter"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(600, 400))  # Twitter-optimized size
        
        # Gradient background effect
        c.setFillColor(HexColor('#1e293b'))
        c.rect(0, 350, 600, 50, fill=1)
        
        # Title
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(300, 370, "RR GU ANALYTIC TRACKER")
        
        # Timestamp
        c.setFont("Helvetica", 10)
        timestamp = datetime.now().strftime("%b %d, %Y • %I:%M %p")
        c.drawCentredString(300, 355, timestamp)
        
        # Main metrics grid
        y = 300
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
        
        # Collection comparison section with enhanced styling
        y = 210
        
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
        
        # Origins stats with icons and enhanced formatting
        y = 190
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
        
        # Visual separator
        c.setStrokeColor(HexColor('#e5e7eb'))
        c.setLineWidth(1)
        c.line(50, 120, 550, 120)
        
        # Enhanced insight section with background
        c.setFillColor(HexColor('#eff6ff'))
        c.rect(40, 60, 520, 50, fill=1, stroke=0)
        
        # Main insight with icon
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 13)
        insight = f"🎯 {data.get('migration_percent', 0):.1f}% of Origins migrated → {data.get('price_ratio', 1):.2f}x premium"
        c.drawCentredString(300, 95, insight)
        
        # Add 24h change summary with trend icons
        origins_change = data.get('origins', {}).get('floor_change_24h', 0)
        undead_change = data.get('undead', {}).get('floor_change_24h', 0)
        
        origins_icon = "📈" if origins_change >= 0 else "📉"
        undead_icon = "📈" if undead_change >= 0 else "📉"
        
        c.setFillColor(HexColor('#374151'))
        c.setFont("Helvetica", 11)
        change_summary = f"{origins_icon} Origins {origins_change:+.1f}% • {undead_icon} Genuine Undead {undead_change:+.1f}%"
        c.drawCentredString(300, 75, change_summary)
        
        # Professional footer with enhanced styling
        c.setFillColor(HexColor('#1e293b'))
        c.rect(0, 0, 600, 45, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#cbd5e1'))
        c.setFont("Helvetica", 9)
        c.drawCentredString(300, 30, "⚡ Real-time blockchain analytics • Generated by RR GU Analytic Tracker")
        
        # Twitter handle with enhanced styling
        c.setFillColor(HexColor('#38bdf8'))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(300, 15, "🐦 @RRGU_Analytics • Share this report! 🚀")
        
        c.save()
        buffer.seek(0)
        return buffer