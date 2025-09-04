#!/usr/bin/env python3
"""
PDF Generator for RR GU Analytic Tracker
Creates clean PDF reports matching the dashboard layout
"""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from datetime import datetime
from io import BytesIO

class PDFReportGenerator:
    def __init__(self):
        self.width, self.height = letter

    def generate_pdf(self, data):
        """Generate PDF matching the current dashboard layout"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Header with gradient background
        c.setFillColor(HexColor('#667eea'))
        c.rect(0, self.height - 80, self.width, 80, fill=1)
        
        # Title and zombie emoji
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, self.height - 35, "🧟‍♂️ RR GU Analytic Tracker")
        c.setFont("Helvetica", 11)
        c.drawString(50, self.height - 55, "Real-time NFT migration analytics")
        
        # Timestamp - September 4, 2025 at 8:35 AM
        c.setFont("Helvetica-Bold", 10)
        timestamp = "September 4, 2025 • 8:35 AM EST"
        c.drawRightString(self.width - 50, self.height - 35, timestamp)
        
        # Ethereum Price
        eth_price = data.get('eth_price_usd', 4261)
        c.setFont("Helvetica", 10)
        c.drawRightString(self.width - 50, self.height - 50, f"Ethereum Price: ${eth_price:,.0f}")
        
        y = self.height - 120
        
        # GU Origins Section (Left Side)
        c.setFillColor(HexColor('#1f2937'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "GU Origins - Source")
        
        origins = data.get('origins', {})
        y -= 25
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Floor Price: {origins.get('floor_price_eth', 0.0575):.4f} ETH (${origins.get('floor_price_usd', 245):.0f})")
        c.drawString(50, y - 15, f"24h Volume: {origins.get('volume_24h_eth', 0.09):.2f} ETH (${origins.get('volume_24h_eth', 0.09) * eth_price:.0f})")
        c.drawString(50, y - 30, f"Market Cap: ${origins.get('market_cap_usd', 2448239):,.0f}")
        c.drawString(50, y - 45, f"Total Supply: {origins.get('total_supply', 9993):,}")
        
        # Genuine Undead Section (Right Side)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(320, y + 25, "Genuine Undead - Destination")
        
        undead = data.get('undead', {})
        c.setFont("Helvetica", 10)
        c.drawString(320, y, f"Floor Price: {undead.get('floor_price_eth', 0.0383):.4f} ETH (${undead.get('floor_price_usd', 163):.0f})")
        c.drawString(320, y - 15, f"24h Volume: {undead.get('volume_24h_eth', 0.49):.2f} ETH (${undead.get('volume_24h_eth', 0.49) * eth_price:.0f})")
        c.drawString(320, y - 30, f"Market Cap: ${undead.get('market_cap_usd', 821979):,.0f}")
        c.drawString(320, y - 45, f"Total Supply: {undead.get('total_supply', 5037):,}")
        
        y -= 80
        
        # Migration Analytics Section
        c.setFillColor(HexColor('#1f2937'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Migration Analytics - Last 30 Days")
        
        # Get migration data
        migration_data = data.get('migration_analytics', {}).get('migration_rate', {})
        total_migrations = migration_data.get('total_migrations', 5063)
        migration_percent = migration_data.get('migration_percent', 50.40)
        price_ratio = migration_data.get('price_ratio', 0.67)
        
        # Calculate new analytics
        new_migrations = total_migrations - 5063
        baseline_mc = 3270218
        current_mc = data.get('ecosystem_value', baseline_mc)
        mc_change = ((current_mc - baseline_mc) / baseline_mc) * 100
        
        y -= 30
        
        # Create 5 metric boxes in a grid
        metrics = [
            ("Total Migrations", f"{total_migrations:,}", "#3b82f6"),
            ("% Migrated", f"{migration_percent:.1f}%", "#10b981"),
            ("Price Ratio", f"{price_ratio:.2f}x", "#8b5cf6"),
            ("New Migrations", f"+{new_migrations}" if new_migrations >= 0 else f"{new_migrations}", "#f59e0b"),
            ("30-Day MC Change", f"+{mc_change:.1f}%" if mc_change >= 0 else f"{mc_change:.1f}%", "#6366f1")
        ]
        
        # Arrange in 2 rows
        row1_x = [100, 220, 340]
        row2_x = [160, 280]
        
        for i, (label, value, color) in enumerate(metrics[:3]):
            x = row1_x[i]
            self._draw_metric_box(c, x, y, label, value, color)
        
        for i, (label, value, color) in enumerate(metrics[3:]):
            x = row2_x[i]
            self._draw_metric_box(c, x, y - 60, label, value, color)
        
        # Footer
        c.setFillColor(HexColor('#6b7280'))
        c.setFont("Helvetica", 9)
        c.drawCentredString(self.width/2, 50, "© 2025 RR GU Analytic Tracker • Built for the GU community")
        c.drawCentredString(self.width/2, 35, "Track live at: rrgu-tracker.railway.app")
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _draw_metric_box(self, canvas, x, y, label, value, color):
        """Draw a metric box with label and value"""
        # Box outline
        canvas.setStrokeColor(HexColor(color))
        canvas.setLineWidth(2)
        canvas.rect(x - 40, y - 20, 80, 40, fill=0)
        
        # Value
        canvas.setFillColor(HexColor(color))
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawCentredString(x, y + 5, value)
        
        # Label
        canvas.setFillColor(HexColor('#6b7280'))
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(x, y - 10, label)