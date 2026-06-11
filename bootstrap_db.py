#!/usr/bin/env python3
"""
Bootstrap the database on deploy.

Railway's filesystem is ephemeral, so on every deploy this script rebuilds the
DB from the committed seed file (data/history_seed.json), which the nightly
GitHub Action keeps up to date from the live app's /api/export-history.

Seeding uses INSERT OR IGNORE: it never overwrites rows that already exist.
"""
import json
import os
import sys

sys.path.append('src')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.database import DatabaseManager

SEED_PATH = os.path.join('data', 'history_seed.json')

ANALYTICS_COLUMNS = [
    'analytics_date', 'eth_price_usd',
    'origins_floor_eth', 'origins_supply', 'origins_market_cap_usd', 'origins_floor_change_24h',
    'undead_floor_eth', 'undead_supply', 'undead_market_cap_usd', 'undead_floor_change_24h',
    'undead_supply_change_24h', 'total_migrations', 'migration_percent', 'price_ratio',
    'combined_market_cap_usd', 'daily_new_migrations',
    'undead_holders', 'undead_volume_24h_eth', 'undead_listed',
    'undead_diamond_hands_pct', 'undead_sellers_30d', 'undead_sales_30d', 'snapshot_at',
]

EXTRA_ANALYTICS_COLUMNS = [
    ('undead_holders', 'INTEGER'),
    ('undead_volume_24h_eth', 'REAL'),
    ('undead_listed', 'INTEGER'),
    ('undead_diamond_hands_pct', 'REAL'),
    ('undead_sellers_30d', 'INTEGER'),
    ('undead_sales_30d', 'INTEGER'),
    ('snapshot_at', 'TEXT'),
]


def migrate(conn):
    for col, col_type in EXTRA_ANALYTICS_COLUMNS:
        try:
            conn.execute(f'ALTER TABLE daily_analytics ADD COLUMN {col} {col_type}')
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_sales (
            sale_date TEXT PRIMARY KEY,
            sales_count INTEGER NOT NULL DEFAULT 0,
            volume_eth REAL NOT NULL DEFAULT 0,
            avg_price_eth REAL,
            min_price_eth REAL,
            max_price_eth REAL,
            updated_at TEXT
        )
    """)


def insert_ignore(conn, table, row, allowed_columns, key_column):
    cols = [c for c in allowed_columns if c in row and row[c] is not None]
    if key_column not in cols:
        return
    placeholders = ', '.join('?' for _ in cols)
    conn.execute(
        f'INSERT OR IGNORE INTO {table} ({", ".join(cols)}) VALUES ({placeholders})',
        [row[c] for c in cols])


def seed(conn):
    if not os.path.exists(SEED_PATH):
        print(f'No seed file at {SEED_PATH} — starting with empty history')
        return
    with open(SEED_PATH) as f:
        seed_data = json.load(f)

    # Legacy seed format: a bare list of daily_analytics rows
    if isinstance(seed_data, list):
        seed_data = {'daily_analytics': seed_data}

    analytics = seed_data.get('daily_analytics', [])
    for row in analytics:
        row.setdefault('eth_price_usd', 0)
        insert_ignore(conn, 'daily_analytics', row, ANALYTICS_COLUMNS, 'analytics_date')

    sales_columns = ['sale_date', 'sales_count', 'volume_eth', 'avg_price_eth',
                     'min_price_eth', 'max_price_eth', 'updated_at']
    sales = seed_data.get('daily_sales', [])
    for row in sales:
        insert_ignore(conn, 'daily_sales', row, sales_columns, 'sale_date')

    gustr_columns = ['snapshot_date', 'holder_count', 'market_cap_usd',
                     'price_usd', 'volume_24h_usd']
    gustr = seed_data.get('gustr_daily_snapshots', [])
    for row in gustr:
        insert_ignore(conn, 'gustr_daily_snapshots', row, gustr_columns, 'snapshot_date')

    print(f'Seeded: {len(analytics)} analytics rows, {len(sales)} sales rows, '
          f'{len(gustr)} GUSTR rows (existing rows preserved)')


def main():
    os.makedirs('data', exist_ok=True)
    db = DatabaseManager('data/gu_migration.db')
    with db.get_connection() as conn:
        migrate(conn)
        seed(conn)
        conn.commit()
        count = conn.execute('SELECT COUNT(*) FROM daily_analytics').fetchone()[0]
        print(f'Database ready: {count} days of history')


if __name__ == '__main__':
    main()
