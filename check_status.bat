@echo off
echo ========================================
echo GU Daily Collection Status Check
echo ========================================
echo.
cd /d "C:\Users\rrose\gu-migration-tracker"
python -c "
import sqlite3
from datetime import date, timedelta

try:
    conn = sqlite3.connect('data/gu_migration.db')
    cursor = conn.cursor()
    
    # Check last few days
    cursor.execute('''
        SELECT analytics_date, origins_floor_eth, undead_floor_eth 
        FROM daily_analytics 
        ORDER BY analytics_date DESC 
        LIMIT 3
    ''')
    
    rows = cursor.fetchall()
    print('Recent data in database:')
    for row in rows:
        print(f'  {row[0]}: Origins={row[1]:.4f} ETH, Undead={row[2]:.4f} ETH')
    
    # Check if today exists
    today = date.today().isoformat()
    cursor.execute('SELECT COUNT(*) FROM daily_analytics WHERE analytics_date = ?', (today,))
    count = cursor.fetchone()[0]
    
    print(f'\nToday ({today}): {\"Data exists\" if count > 0 else \"No data - need to run collection\"}')
    
    conn.close()
except Exception as e:
    print(f'Error: {e}')
"
echo.
pause