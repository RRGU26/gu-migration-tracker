#!/usr/bin/env python3
"""
GU Migration Tracker Dashboard — industrialized backend.

Key properties:
- Single collect_snapshot() writes today's row in daily_analytics (upsert, never
  destroys columns it didn't compute).
- Background collector thread refreshes data hourly; /api/current also kicks a
  throttled background collection whenever the latest snapshot is stale.
- Real sales history backfilled from OpenSea events into daily_sales.
- /api/charts serves raw date-aligned series for the frontend chart section.
- /api/export-history + /api/snapshot let a GitHub Action persist history across
  Railway's ephemeral filesystem.
"""
import os
import sys
import json
import time
import threading
from datetime import datetime, date, timedelta, timezone
from flask import Flask, render_template, jsonify, send_file, request
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.database.database import DatabaseManager
import requests

VERSION = '2026-06-11-v4-industrial'

UNDEAD_SLUG = 'genuine-undead'
ORIGINS_SLUG = 'gu-origins'
ORIGINS_MAX_SUPPLY = 9993
BURNED_GU = 26  # GU burned before migration started; counted as migrated
GUSTR_ADDRESS = '0x34a2f31ccfdc1e2e7753a1a28afe5feb190f7f00'
GUSTR_POOL = '0xe8d6ad309e597da6e05c225008e9518d4124806cf8fa52200469e3d8eb16d573'

STALE_AFTER_MINUTES = 90       # /api/current flags data older than this
COLLECT_MIN_INTERVAL = 600     # throttle: at most one collection per 10 min
COLLECTOR_PERIOD = 3600        # background collector cadence (1h)
DIAMOND_HANDS_PERIOD = 6 * 3600  # recompute expensive diamond-hands every 6h
SALES_BACKFILL_DAYS = 90

app = Flask(__name__)

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gu_migration.db')
db = DatabaseManager(db_path)


def opensea_headers():
    return {'X-API-KEY': os.environ.get('OPENSEA_API_KEY', '')}


# ---------------------------------------------------------------------------
# Tiny in-memory TTL cache (per worker process)
# ---------------------------------------------------------------------------
_cache = {}
_cache_lock = threading.Lock()


def cached(key, ttl_seconds, fn):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl_seconds:
            return hit[1]
    value = fn()
    if value is not None:
        with _cache_lock:
            _cache[key] = (time.time(), value)
    return value


# ---------------------------------------------------------------------------
# Schema migrations (idempotent, run at import)
# ---------------------------------------------------------------------------
EXTRA_ANALYTICS_COLUMNS = [
    ('undead_holders', 'INTEGER'),
    ('undead_volume_24h_eth', 'REAL'),
    ('undead_listed', 'INTEGER'),
    ('undead_diamond_hands_pct', 'REAL'),
    ('undead_sellers_30d', 'INTEGER'),
    ('undead_sales_30d', 'INTEGER'),
    ('snapshot_at', 'TEXT'),
    ('source', 'TEXT'),  # 'live' | 'sales_reconstruction' | NULL (legacy/unknown)
]


def migrate_schema():
    with db.get_connection() as conn:
        for col, col_type in EXTRA_ANALYTICS_COLUMNS:
            try:
                conn.execute(f'ALTER TABLE daily_analytics ADD COLUMN {col} {col_type}')
            except Exception:
                pass  # column already exists
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
        conn.commit()


migrate_schema()


# ---------------------------------------------------------------------------
# External data fetchers
# ---------------------------------------------------------------------------
def _fetch_eth_price():
    """ETH/USD with three independent fallbacks."""
    sources = [
        ('CoinGecko', 'https://api.coingecko.com/api/v3/simple/price',
         {'ids': 'ethereum', 'vs_currencies': 'usd'},
         lambda d: d.get('ethereum', {}).get('usd')),
        ('CryptoCompare', 'https://min-api.cryptocompare.com/data/price',
         {'fsym': 'ETH', 'tsyms': 'USD'},
         lambda d: d.get('USD')),
        ('Binance', 'https://api.binance.com/api/v3/ticker/price',
         {'symbol': 'ETHUSDT'},
         lambda d: d.get('price')),
    ]
    for name, url, params, extract in sources:
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                price = extract(response.json())
                if price:
                    return float(price)
            print(f'[ETH Price] {name} status: {response.status_code}')
        except Exception as e:
            print(f'[ETH Price] {name} failed: {e}')
    return None


def get_eth_price():
    """Cached ETH price; falls back to last DB price, then a constant."""
    price = cached('eth_price', 300, _fetch_eth_price)
    if price:
        return price
    try:
        with db.get_connection() as conn:
            row = conn.execute(
                'SELECT eth_price_usd FROM daily_eth_prices ORDER BY price_date DESC LIMIT 1'
            ).fetchone()
            if row and row['eth_price_usd']:
                return float(row['eth_price_usd'])
    except Exception:
        pass
    return 2000.0


def fetch_collection_stats(slug):
    """OpenSea stats: floor, owners, one-day volume/sales. Returns dict or None."""
    try:
        response = requests.get(
            f'https://api.opensea.io/api/v2/collections/{slug}/stats',
            headers=opensea_headers(), timeout=10)
        if response.status_code != 200:
            print(f'[OpenSea] {slug} stats error {response.status_code}: {response.text[:150]}')
            return None
        data = response.json()
        total = data.get('total', {})
        result = {
            'floor_price_eth': float(total.get('floor_price') or 0),
            'num_owners': int(total.get('num_owners') or 0),
            'volume_24h_eth': 0.0,
            'sales_24h': 0,
        }
        for interval in data.get('intervals', []):
            if interval.get('interval') == 'one_day':
                result['volume_24h_eth'] = float(interval.get('volume') or 0)
                result['sales_24h'] = int(interval.get('sales') or 0)
        return result
    except Exception as e:
        print(f'[OpenSea] {slug} stats exception: {e}')
        return None


def fetch_collection_supply(slug):
    try:
        response = requests.get(
            f'https://api.opensea.io/api/v2/collections/{slug}',
            headers=opensea_headers(), timeout=10)
        if response.status_code == 200:
            supply = response.json().get('total_supply')
            if supply:
                return int(supply)
    except Exception as e:
        print(f'[OpenSea] {slug} supply exception: {e}')
    return None


def fetch_listings_count(slug=UNDEAD_SLUG, max_pages=5):
    try:
        total = 0
        next_cursor = None
        for _ in range(max_pages):
            params = {'limit': 100}
            if next_cursor:
                params['next'] = next_cursor
            response = requests.get(
                f'https://api.opensea.io/api/v2/listings/collection/{slug}/all',
                headers=opensea_headers(), params=params, timeout=10)
            if response.status_code != 200:
                break
            data = response.json()
            total += len(data.get('listings', []))
            next_cursor = data.get('next')
            if not next_cursor:
                break
        return total
    except Exception as e:
        print(f'[OpenSea] listings exception: {e}')
        return None


def _iter_sale_events(slug=UNDEAD_SLUG, oldest_timestamp=0, max_pages=120):
    """Yield sale events newest-first until older than oldest_timestamp."""
    next_cursor = None
    for _ in range(max_pages):
        params = {'event_type': 'sale', 'limit': 50}
        if next_cursor:
            params['next'] = next_cursor
        response = requests.get(
            f'https://api.opensea.io/api/v2/events/collection/{slug}',
            headers=opensea_headers(), params=params, timeout=15)
        if response.status_code != 200:
            print(f'[OpenSea] events error {response.status_code}')
            return
        data = response.json()
        events = data.get('asset_events', [])
        if not events:
            return
        done = False
        for event in events:
            if (event.get('event_timestamp') or 0) < oldest_timestamp:
                done = True
                continue
            yield event
        if done:
            return
        next_cursor = data.get('next')
        if not next_cursor:
            return
        time.sleep(0.3)  # stay under OpenSea rate limits


def _sale_price_eth(event):
    """Sale price in ETH; None for non-ETH/WETH payments and dust/private
    transfers (near-zero prices are not market trades)."""
    payment = event.get('payment') or {}
    symbol = (payment.get('symbol') or '').upper()
    if symbol not in ('ETH', 'WETH'):
        return None
    try:
        quantity = int(payment.get('quantity') or 0)
        decimals = int(payment.get('decimals') or 18)
        price = quantity / (10 ** decimals)
        return price if price >= 0.001 else None
    except Exception:
        return None


def update_sales_history(days):
    """Aggregate OpenSea sale events into per-day rows in daily_sales."""
    cutoff_ts = int(time.time()) - days * 86400
    daily = {}
    count = 0
    for event in _iter_sale_events(oldest_timestamp=cutoff_ts):
        price = _sale_price_eth(event)
        if price is None:
            continue
        day = datetime.fromtimestamp(event['event_timestamp'], tz=timezone.utc).date().isoformat()
        bucket = daily.setdefault(day, [])
        bucket.append(price)
        count += 1
    now_iso = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        for day, prices in daily.items():
            conn.execute("""
                INSERT INTO daily_sales
                    (sale_date, sales_count, volume_eth, avg_price_eth,
                     min_price_eth, max_price_eth, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sale_date) DO UPDATE SET
                    sales_count=excluded.sales_count,
                    volume_eth=excluded.volume_eth,
                    avg_price_eth=excluded.avg_price_eth,
                    min_price_eth=excluded.min_price_eth,
                    max_price_eth=excluded.max_price_eth,
                    updated_at=excluded.updated_at
            """, (day, len(prices), sum(prices), sum(prices) / len(prices),
                  min(prices), max(prices), now_iso))
        conn.commit()
    print(f'[Sales] Updated {len(daily)} days from {count} sales (window={days}d)')
    return len(daily)


def fetch_eth_price_history(days=365):
    """Real daily ETH/USD closes from CoinGecko; upserts daily_eth_prices."""
    try:
        response = requests.get(
            'https://api.coingecko.com/api/v3/coins/ethereum/market_chart',
            params={'vs_currency': 'usd', 'days': days, 'interval': 'daily'},
            timeout=20)
        if response.status_code != 200:
            print(f'[ETH History] CoinGecko error {response.status_code}')
            return 0
        prices = response.json().get('prices', [])
        with db.get_connection() as conn:
            for ts_ms, price in prices:
                day = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
                conn.execute("""
                    INSERT OR REPLACE INTO daily_eth_prices (price_date, eth_price_usd)
                    VALUES (?, ?)
                """, (day, round(float(price), 2)))
            conn.commit()
        print(f'[ETH History] Stored {len(prices)} daily prices')
        return len(prices)
    except Exception as e:
        print(f'[ETH History] failed: {e}')
        return 0


def rebuild_history(days=365):
    """Replace fabricated legacy history with real on-chain data.

    The pre-2026-06 daily_analytics rows came from flat backfills and hardcoded
    seeds — not real market history. This rebuilds the past from verifiable
    sources: lowest daily sale price (floor proxy) from OpenSea sale events,
    and real daily ETH/USD closes from CoinGecko. Supply is held at the
    current value (the collection is fully migrated). Today's live row is kept.
    """
    sales_days = update_sales_history(days=days)
    eth_days = fetch_eth_price_history(days=days)

    today = date.today().isoformat()
    with db.get_connection() as conn:
        latest = conn.execute("""
            SELECT undead_supply, eth_price_usd FROM daily_analytics
            WHERE source = 'live' ORDER BY analytics_date DESC LIMIT 1
        """).fetchone()
        if not latest:
            latest = conn.execute(
                'SELECT undead_supply, eth_price_usd FROM daily_analytics '
                'ORDER BY analytics_date DESC LIMIT 1').fetchone()
        supply = latest['undead_supply'] if latest else 0

        deleted = conn.execute(
            "DELETE FROM daily_analytics WHERE analytics_date < ? "
            "AND (source IS NULL OR source != 'live')", (today,)).rowcount

        eth_prices = {r['price_date']: r['eth_price_usd'] for r in conn.execute(
            'SELECT price_date, eth_price_usd FROM daily_eth_prices').fetchall()}

        sales_rows = conn.execute(
            'SELECT * FROM daily_sales WHERE sale_date < ? ORDER BY sale_date ASC',
            (today,)).fetchall()
        rebuilt = 0
        last_eth = None
        for row in sales_rows:
            day = row['sale_date']
            eth = eth_prices.get(day) or last_eth
            if not eth:
                continue
            last_eth = eth
            floor = row['min_price_eth']
            if not floor or floor <= 0:
                continue
            mcap = floor * supply * eth
            conn.execute("""
                INSERT INTO daily_analytics (
                    analytics_date, eth_price_usd,
                    undead_floor_eth, undead_supply, undead_market_cap_usd,
                    undead_volume_24h_eth, source
                ) VALUES (?, ?, ?, ?, ?, ?, 'sales_reconstruction')
                ON CONFLICT(analytics_date) DO UPDATE SET
                    eth_price_usd=excluded.eth_price_usd,
                    undead_floor_eth=excluded.undead_floor_eth,
                    undead_supply=excluded.undead_supply,
                    undead_market_cap_usd=excluded.undead_market_cap_usd,
                    undead_volume_24h_eth=excluded.undead_volume_24h_eth,
                    source='sales_reconstruction'
            """, (day, eth, floor, supply, mcap, row['volume_eth']))
            rebuilt += 1
        conn.commit()

    print(f'[Rebuild] deleted {deleted} fabricated rows, rebuilt {rebuilt} days '
          f'from sales ({sales_days} sales-days, {eth_days} ETH prices)')
    return {'deleted_legacy_rows': deleted, 'rebuilt_days': rebuilt,
            'sales_days': sales_days, 'eth_price_days': eth_days,
            'supply_used': supply}


def compute_diamond_hands(total_holders):
    """% of holders with no sale in the last 30 days. Expensive: paginated events."""
    if not total_holders:
        return None
    cutoff_ts = int(time.time()) - 30 * 86400
    sellers = set()
    sales = 0
    for event in _iter_sale_events(oldest_timestamp=cutoff_ts, max_pages=20):
        sales += 1
        seller = event.get('seller')
        if seller:
            sellers.add(seller.lower())
    pct = round((total_holders - len(sellers)) / total_holders * 100, 1)
    return {'diamond_hands_pct': pct, 'sellers_30d': len(sellers), 'sales_30d': sales}


# ---------------------------------------------------------------------------
# Snapshot collection — the single source of truth
# ---------------------------------------------------------------------------
_collect_lock = threading.Lock()
_last_collect_ts = 0.0
_last_diamond_ts = 0.0


def collect_snapshot(force=False):
    """Fetch live data and upsert today's daily_analytics row.

    Returns the collected summary dict, or None if skipped (throttled or
    already in progress).
    """
    global _last_collect_ts, _last_diamond_ts
    if not _collect_lock.acquire(blocking=False):
        return None
    try:
        if not force and time.time() - _last_collect_ts < COLLECT_MIN_INTERVAL:
            return None

        eth_price = get_eth_price()
        undead = fetch_collection_stats(UNDEAD_SLUG)
        if not undead or undead['floor_price_eth'] <= 0:
            print('[Collect] Undead stats unavailable — skipping snapshot write')
            return None
        origins = fetch_collection_stats(ORIGINS_SLUG) or {}
        undead_supply = fetch_collection_supply(UNDEAD_SLUG)
        listed = fetch_listings_count()

        diamond = None
        if time.time() - _last_diamond_ts > DIAMOND_HANDS_PERIOD:
            diamond = compute_diamond_hands(undead['num_owners'])
            if diamond:
                _last_diamond_ts = time.time()

        today = date.today().isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()
        undead_floor = undead['floor_price_eth']
        origins_floor = origins.get('floor_price_eth') or 0
        with db.get_connection() as conn:
            if undead_supply is None:
                row = conn.execute(
                    'SELECT undead_supply FROM daily_analytics ORDER BY analytics_date DESC LIMIT 1'
                ).fetchone()
                undead_supply = row['undead_supply'] if row else 0
            undead_mc = undead_floor * undead_supply * eth_price
            origins_mc = origins_floor * ORIGINS_MAX_SUPPLY * eth_price
            conn.execute("""
                INSERT INTO daily_analytics (
                    analytics_date, eth_price_usd,
                    origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                    undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                    total_migrations, migration_percent, price_ratio, combined_market_cap_usd,
                    undead_holders, undead_volume_24h_eth, undead_listed, snapshot_at, source
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'live')
                ON CONFLICT(analytics_date) DO UPDATE SET
                    eth_price_usd=excluded.eth_price_usd,
                    origins_floor_eth=excluded.origins_floor_eth,
                    origins_supply=excluded.origins_supply,
                    origins_market_cap_usd=excluded.origins_market_cap_usd,
                    undead_floor_eth=excluded.undead_floor_eth,
                    undead_supply=excluded.undead_supply,
                    undead_market_cap_usd=excluded.undead_market_cap_usd,
                    total_migrations=excluded.total_migrations,
                    migration_percent=excluded.migration_percent,
                    price_ratio=excluded.price_ratio,
                    combined_market_cap_usd=excluded.combined_market_cap_usd,
                    undead_holders=excluded.undead_holders,
                    undead_volume_24h_eth=excluded.undead_volume_24h_eth,
                    undead_listed=excluded.undead_listed,
                    snapshot_at=excluded.snapshot_at,
                    source='live'
            """, (
                today, eth_price,
                origins_floor, ORIGINS_MAX_SUPPLY, origins_mc,
                undead_floor, undead_supply, undead_mc,
                undead_supply + BURNED_GU,
                (undead_supply / ORIGINS_MAX_SUPPLY) * 100,
                (undead_floor / origins_floor) if origins_floor > 0 else 0,
                origins_mc + undead_mc,
                undead['num_owners'] or None,
                undead['volume_24h_eth'],
                listed,
                now_iso,
            ))
            if diamond:
                conn.execute("""
                    UPDATE daily_analytics SET
                        undead_diamond_hands_pct = ?,
                        undead_sellers_30d = ?,
                        undead_sales_30d = ?
                    WHERE analytics_date = ?
                """, (diamond['diamond_hands_pct'], diamond['sellers_30d'],
                      diamond['sales_30d'], today))
            conn.execute("""
                INSERT OR REPLACE INTO daily_eth_prices (price_date, eth_price_usd)
                VALUES (?, ?)
            """, (today, eth_price))
            conn.commit()

        _last_collect_ts = time.time()
        print(f'[Collect] Snapshot {today}: floor={undead_floor} ETH, '
              f'supply={undead_supply}, holders={undead["num_owners"]}, listed={listed}')
        # Keep today's/yesterday's sales rows current (cheap: stops at 2-day cutoff)
        try:
            update_sales_history(days=2)
        except Exception as e:
            print(f'[Collect] sales update failed: {e}')
        return {
            'analytics_date': today,
            'eth_price_usd': eth_price,
            'undead_floor_eth': undead_floor,
            'undead_supply': undead_supply,
            'undead_holders': undead['num_owners'],
            'undead_listed': listed,
        }
    finally:
        _collect_lock.release()


def kick_background_collection():
    """Fire-and-forget collection (throttled inside collect_snapshot)."""
    threading.Thread(target=collect_snapshot, kwargs={'force': False}, daemon=True).start()


# ---------------------------------------------------------------------------
# GUSTR token data
# ---------------------------------------------------------------------------
def get_gustr_token_data():
    """GUSTR data: TokenStrategy (primary), GeckoTerminal (backup), DexScreener (activity)."""
    try:
        price_usd = price_eth = market_cap = liquidity = volume_24h = 0
        eth_price = get_eth_price()

        try:
            ts_response = requests.get(
                f'https://www.tokenstrategy.com/api/strategies/{GUSTR_ADDRESS}', timeout=10)
            if ts_response.status_code == 200:
                ts_data = ts_response.json().get('data', {})
                price_usd = float(ts_data.get('priceUsd', 0) or 0)
                market_cap = float(ts_data.get('marketCap', 0) or 0)
                liquidity = float(ts_data.get('liquidity', 0) or 0)
                volume_24h = float(ts_data.get('volume24h', 0) or 0)
                price_eth = price_usd / eth_price if eth_price > 0 else 0
        except Exception as ts_err:
            print(f'TokenStrategy API error: {ts_err}')

        if price_usd == 0:
            try:
                gecko_response = requests.get(
                    f'https://api.geckoterminal.com/api/v2/networks/eth/pools/{GUSTR_POOL}',
                    timeout=10)
                if gecko_response.status_code == 200:
                    pool = gecko_response.json().get('data', {}).get('attributes', {})
                    price_usd = float(pool.get('base_token_price_usd', 0) or 0)
                    price_eth = float(pool.get('base_token_price_native_currency', 0) or 0)
                    market_cap = float(pool.get('fdv_usd', 0) or 0)
                    liquidity = float(pool.get('reserve_in_usd', 0) or 0)
                    volume_24h = float(pool.get('volume_usd', {}).get('h24', 0) or 0)
            except Exception as gecko_err:
                print(f'GeckoTerminal API error: {gecko_err}')

        if price_usd == 0:
            return None

        result = {
            'price_usd': price_usd, 'price_eth': price_eth, 'market_cap': market_cap,
            'liquidity_usd': liquidity, 'volume_24h': volume_24h,
            'volume_6h': 0, 'volume_1h': 0, 'volume_5m': 0,
            'price_change_24h': 0, 'price_change_6h': 0, 'price_change_1h': 0, 'price_change_5m': 0,
            'buys_24h': 0, 'sells_24h': 0, 'buys_6h': 0, 'sells_6h': 0,
            'buys_1h': 0, 'sells_1h': 0, 'buys_5m': 0, 'sells_5m': 0,
        }

        try:
            dex_response = requests.get(
                f'https://api.dexscreener.com/latest/dex/tokens/{GUSTR_ADDRESS}', timeout=5)
            if dex_response.status_code == 200:
                pairs = dex_response.json().get('pairs') or []
                if pairs:
                    pair = pairs[0]
                    txns = pair.get('txns', {})
                    volume = pair.get('volume', {})
                    price_change = pair.get('priceChange', {})
                    result.update({
                        'volume_6h': float(volume.get('h6', 0) or 0),
                        'volume_1h': float(volume.get('h1', 0) or 0),
                        'volume_5m': float(volume.get('m5', 0) or 0),
                        'price_change_24h': float(price_change.get('h24', 0) or 0),
                        'price_change_6h': float(price_change.get('h6', 0) or 0),
                        'price_change_1h': float(price_change.get('h1', 0) or 0),
                        'price_change_5m': float(price_change.get('m5', 0) or 0),
                        'buys_24h': int(txns.get('h24', {}).get('buys', 0) or 0),
                        'sells_24h': int(txns.get('h24', {}).get('sells', 0) or 0),
                        'buys_6h': int(txns.get('h6', {}).get('buys', 0) or 0),
                        'sells_6h': int(txns.get('h6', {}).get('sells', 0) or 0),
                        'buys_1h': int(txns.get('h1', {}).get('buys', 0) or 0),
                        'sells_1h': int(txns.get('h1', {}).get('sells', 0) or 0),
                        'buys_5m': int(txns.get('m5', {}).get('buys', 0) or 0),
                        'sells_5m': int(txns.get('m5', {}).get('sells', 0) or 0),
                    })
        except Exception as dex_err:
            print(f'DexScreener unavailable: {dex_err}')

        return result
    except Exception as e:
        print(f'Error fetching GUSTR data: {e}')
        return None


def get_strategy_nft_holdings():
    try:
        response = requests.get(
            f'https://api.opensea.io/api/v2/chain/ethereum/account/{GUSTR_ADDRESS}/nfts',
            headers=opensea_headers(), timeout=10)
        if response.status_code == 200:
            nfts = response.json().get('nfts', [])
            gu_nfts = [n for n in nfts
                       if 'genuine' in (n.get('collection') or '').lower()
                       or 'undead' in (n.get('collection') or '').lower()]
            return len(gu_nfts) if gu_nfts else len(nfts)
        return 0
    except Exception as e:
        print(f'Error fetching strategy NFT holdings: {e}')
        return 0


def get_gustr_burn_amount():
    try:
        response = requests.get(
            f'https://www.tokenstrategy.com/api/strategies/{GUSTR_ADDRESS}', timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {})
            burned_tokens = int(data.get('burnedAmount', 0) or 0) / (10 ** 18)
            return {'burned_tokens': burned_tokens,
                    'burn_percent': (burned_tokens / 1_000_000_000) * 100}
        return {'burned_tokens': 0, 'burn_percent': 0}
    except Exception as e:
        print(f'Error fetching GUSTR burn amount: {e}')
        return {'burned_tokens': 0, 'burn_percent': 0}


def get_gustr_holder_count():
    """Holder count scraped from Etherscan's token page meta description."""
    try:
        import re
        response = requests.get(
            f'https://etherscan.io/token/{GUSTR_ADDRESS}',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=15)
        if response.status_code == 200:
            match = re.search(r'Holders:\s*([\d,]+)', response.text)
            if match:
                return int(match.group(1).replace(',', ''))
        return None
    except Exception as e:
        print(f'Error fetching GUSTR holder count: {e}')
        return None


def save_gustr_snapshot(holder_count, market_cap, price_usd, volume_24h):
    try:
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO gustr_daily_snapshots
                (snapshot_date, holder_count, market_cap_usd, price_usd, volume_24h_usd)
                VALUES (date('now'), ?, ?, ?, ?)
            """, (holder_count, market_cap, price_usd, volume_24h))
            conn.commit()
    except Exception as e:
        print(f'Error saving GUSTR snapshot: {e}')


def _build_gustr_payload():
    token_data = get_gustr_token_data()
    if not token_data:
        return None
    nft_holdings = get_strategy_nft_holdings()
    burn_data = get_gustr_burn_amount()
    holder_count = get_gustr_holder_count()

    holder_change_pct = None
    try:
        with db.get_connection() as conn:
            row = conn.execute("""
                SELECT holder_count FROM gustr_daily_snapshots
                WHERE snapshot_date = date('now', '-1 day') LIMIT 1
            """).fetchone()
            if holder_count and row and row['holder_count']:
                holder_change_pct = ((holder_count - row['holder_count'])
                                     / row['holder_count']) * 100
    except Exception:
        pass

    if holder_count:
        save_gustr_snapshot(holder_count, token_data.get('market_cap', 0),
                            token_data.get('price_usd', 0), token_data.get('volume_24h', 0))

    return {
        'timestamp': datetime.now().isoformat(),
        'token': {
            'name': 'GenuineUndeadStrategy', 'symbol': 'GUSTR', 'address': GUSTR_ADDRESS,
            **token_data,
            'holder_count': holder_count,
            'holder_change_24h': holder_change_pct,
        },
        'strategy': {
            'nft_holdings': nft_holdings,
            'burned_tokens': burn_data['burned_tokens'],
            'burn_percent': burn_data['burn_percent'],
        },
    }


# ---------------------------------------------------------------------------
# Trend helpers
# ---------------------------------------------------------------------------
def _row_at_or_before(conn, days_ago):
    """Closest daily_analytics row at/before N days ago (skips gaps honestly)."""
    target = (date.today() - timedelta(days=days_ago)).isoformat()
    return conn.execute("""
        SELECT * FROM daily_analytics
        WHERE analytics_date <= ?
        ORDER BY analytics_date DESC LIMIT 1
    """, (target,)).fetchone()


def _pct(new, old):
    if old and old > 0:
        return ((new - old) / old) * 100
    return None


def build_trends(conn, latest):
    """Date-windowed 1d/7d/30d changes with the actual window length reported."""
    trends = {
        'floor_price_change_1d': None,
        'floor_price_change_7d': None,
        'floor_price_change_30d': None,
        'market_cap_change_30d': None,
        'supply_growth_30d': None,
        'holders_change_30d': None,
        'window_actual_days_30d': None,
    }
    current_floor = latest['undead_floor_eth']
    current_supply = latest['undead_supply']

    # max_age: don't report a "1d change" computed against a weeks-old row
    for days, max_age, key in ((1, 3, 'floor_price_change_1d'),
                               (7, 14, 'floor_price_change_7d')):
        ref = _row_at_or_before(conn, days)
        if ref and ref['analytics_date'] != latest['analytics_date']:
            ref_age = (date.today() - date.fromisoformat(ref['analytics_date'])).days
            if ref_age <= max_age:
                trends[key] = _pct(current_floor, ref['undead_floor_eth'])

    ref30 = _row_at_or_before(conn, 30)
    if not ref30:
        # History shorter than 30 days: compare against the oldest snapshot
        # (window_actual_days_30d reports the true span)
        oldest = conn.execute(
            'SELECT * FROM daily_analytics ORDER BY analytics_date ASC LIMIT 1').fetchone()
        if oldest and (date.today() - date.fromisoformat(oldest['analytics_date'])).days >= 7:
            ref30 = oldest
    if ref30 and ref30['analytics_date'] != latest['analytics_date']:
        trends['floor_price_change_30d'] = _pct(current_floor, ref30['undead_floor_eth'])
        trends['supply_growth_30d'] = current_supply - ref30['undead_supply']
        # market cap change in ETH terms to strip out ETH/USD volatility
        trends['market_cap_change_30d'] = _pct(
            current_floor * current_supply,
            ref30['undead_floor_eth'] * ref30['undead_supply'])
        try:
            if ref30['undead_holders'] and latest['undead_holders']:
                trends['holders_change_30d'] = latest['undead_holders'] - ref30['undead_holders']
        except (KeyError, IndexError):
            pass
        trends['window_actual_days_30d'] = (
            date.today() - date.fromisoformat(ref30['analytics_date'])).days

    # 30d average daily sale volume from real sales history
    vol_row = conn.execute("""
        SELECT AVG(volume_eth) AS avg_vol, SUM(sales_count) AS sales
        FROM daily_sales WHERE sale_date >= date('now', '-30 day')
    """).fetchone()
    trends['avg_daily_volume_30d'] = round(vol_row['avg_vol'], 4) if vol_row and vol_row['avg_vol'] else 0
    trends['sales_30d_total'] = vol_row['sales'] if vol_row and vol_row['sales'] else 0
    return trends


def build_current_payload(latest, conn):
    eth_price = get_eth_price()
    floor = latest['undead_floor_eth']
    supply = latest['undead_supply']
    holders = None
    listed = None
    diamond = None
    snapshot_at = None
    try:
        holders = latest['undead_holders']
        listed = latest['undead_listed']
        diamond = latest['undead_diamond_hands_pct']
        snapshot_at = latest['snapshot_at']
    except (KeyError, IndexError):
        pass

    age_minutes = None
    if snapshot_at:
        try:
            snap_dt = datetime.fromisoformat(snapshot_at)
            if snap_dt.tzinfo is None:
                snap_dt = snap_dt.replace(tzinfo=timezone.utc)
            age_minutes = round((datetime.now(timezone.utc) - snap_dt).total_seconds() / 60)
        except Exception:
            pass

    is_today = latest['analytics_date'] == date.today().isoformat()
    stale = (not is_today) or age_minutes is None or age_minutes > STALE_AFTER_MINUTES

    trends = build_trends(conn, latest)
    return {
        'timestamp': datetime.now().isoformat(),
        'analytics_date': latest['analytics_date'],
        'eth_price_usd': eth_price,
        'freshness': {
            'snapshot_at': snapshot_at,
            'age_minutes': age_minutes,
            'stale': stale,
            'stale_after_minutes': STALE_AFTER_MINUTES,
        },
        'undead': {
            'floor_price_eth': floor,
            'floor_price_usd': floor * eth_price,
            'total_supply': supply,
            'market_cap_usd': floor * eth_price * supply,
            'floor_change_24h': trends['floor_price_change_1d'] or 0.0,
            'volume_24h_eth': (latest['undead_volume_24h_eth']
                               if 'undead_volume_24h_eth' in latest.keys()
                               and latest['undead_volume_24h_eth'] is not None else 0),
            'holders_count': holders,
            'num_listed': listed,
            'listing_percent': (listed / supply * 100) if listed and supply else None,
            'diamond_hands_pct': diamond,
        },
        'trends': trends,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/current')
def get_current_data():
    """Latest snapshot from DB + freshness metadata. Kicks a background
    collection when stale so the next poll is fresh."""
    try:
        with db.get_connection() as conn:
            latest = conn.execute(
                'SELECT * FROM daily_analytics ORDER BY analytics_date DESC LIMIT 1'
            ).fetchone()
            if not latest:
                kick_background_collection()
                return jsonify({'error': 'No data available yet — collection started',
                                'timestamp': datetime.now().isoformat()})
            payload = build_current_payload(latest, conn)
        if payload['freshness']['stale']:
            kick_background_collection()
        return jsonify(payload)
    except Exception as e:
        return jsonify({'error': str(e), 'timestamp': datetime.now().isoformat()}), 500


@app.route('/api/refresh')
def refresh_data():
    """Force a synchronous collection, then return the fresh payload."""
    try:
        collect_snapshot(force=True)
        with db.get_connection() as conn:
            latest = conn.execute(
                'SELECT * FROM daily_analytics ORDER BY analytics_date DESC LIMIT 1'
            ).fetchone()
            if not latest:
                return jsonify({'error': 'Collection failed — no data'}), 502
            return jsonify(build_current_payload(latest, conn))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshot')
def snapshot():
    """Force collection (used by the GitHub Action and manual ops)."""
    try:
        result = collect_snapshot(force=True)
        if result:
            return jsonify({'status': 'collected', **result,
                            'timestamp': datetime.now().isoformat()})
        return jsonify({'status': 'skipped',
                        'reason': 'collection already in progress or source unavailable',
                        'timestamp': datetime.now().isoformat()}), 202
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/rebuild-history')
def rebuild_history_endpoint():
    """One-time admin op: replace fabricated legacy history with real
    sales-reconstructed history. Requires ?confirm=1."""
    if request.args.get('confirm') != '1':
        return jsonify({'error': 'Pass ?confirm=1 to rebuild history. This deletes '
                                 'legacy (non-live) rows and rebuilds from real sales '
                                 'and ETH price data.'}), 400
    try:
        result = rebuild_history(days=365)
        return jsonify({'status': 'rebuilt', **result,
                        'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/charts')
def get_chart_data():
    """Raw date-aligned series for the chart section. ?days=30|90|180|all"""
    try:
        days_param = request.args.get('days', '90')
        with db.get_connection() as conn:
            if days_param == 'all':
                rows = conn.execute(
                    'SELECT * FROM daily_analytics ORDER BY analytics_date ASC').fetchall()
                sales = conn.execute(
                    'SELECT * FROM daily_sales ORDER BY sale_date ASC').fetchall()
            else:
                days = max(2, min(int(days_param), 3650))
                cutoff = (date.today() - timedelta(days=days)).isoformat()
                rows = conn.execute("""
                    SELECT * FROM daily_analytics
                    WHERE analytics_date >= ? ORDER BY analytics_date ASC
                """, (cutoff,)).fetchall()
                sales = conn.execute("""
                    SELECT * FROM daily_sales
                    WHERE sale_date >= ? ORDER BY sale_date ASC
                """, (cutoff,)).fetchall()

        def col(row, name):
            try:
                return row[name]
            except (KeyError, IndexError):
                return None

        series = {
            'dates': [r['analytics_date'] for r in rows],
            'floor_eth': [r['undead_floor_eth'] for r in rows],
            'floor_usd': [(r['undead_floor_eth'] or 0) * (r['eth_price_usd'] or 0) for r in rows],
            'market_cap_usd': [r['undead_market_cap_usd'] for r in rows],
            'supply': [r['undead_supply'] for r in rows],
            'holders': [col(r, 'undead_holders') for r in rows],
            'eth_price_usd': [r['eth_price_usd'] for r in rows],
            'source': [col(r, 'source') for r in rows],
        }
        sales_series = {
            'dates': [s['sale_date'] for s in sales],
            'volume_eth': [s['volume_eth'] for s in sales],
            'sales_count': [s['sales_count'] for s in sales],
            'avg_price_eth': [s['avg_price_eth'] for s in sales],
        }
        return jsonify({
            'series': series,
            'sales': sales_series,
            'meta': {
                'requested_days': days_param,
                'data_points': len(rows),
                'first_date': series['dates'][0] if series['dates'] else None,
                'last_date': series['dates'][-1] if series['dates'] else None,
                'origins_max_supply': ORIGINS_MAX_SUPPLY,
                'live_since': next((series['dates'][i] for i, src in enumerate(series['source'])
                                    if src == 'live'), None),
                'generated_at': datetime.now().isoformat(),
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gustr')
def get_gustr_data():
    """GUSTR token metrics (cached 5 min — backed by 4-5 external calls)."""
    try:
        payload = cached('gustr_payload', 300, _build_gustr_payload)
        if payload:
            return jsonify(payload)
        return jsonify({'error': 'Unable to fetch GUSTR data',
                        'timestamp': datetime.now().isoformat()}), 502
    except Exception as e:
        return jsonify({'error': str(e), 'timestamp': datetime.now().isoformat()}), 500


@app.route('/api/export-history')
def export_history():
    """Full history dump — committed back to the repo by the nightly GitHub
    Action so history survives Railway redeploys."""
    try:
        with db.get_connection() as conn:
            analytics = [dict(r) for r in conn.execute(
                'SELECT * FROM daily_analytics ORDER BY analytics_date ASC').fetchall()]
            sales = [dict(r) for r in conn.execute(
                'SELECT * FROM daily_sales ORDER BY sale_date ASC').fetchall()]
            gustr = [dict(r) for r in conn.execute(
                'SELECT * FROM gustr_daily_snapshots ORDER BY snapshot_date ASC').fetchall()]
        for row in analytics + sales + gustr:
            row.pop('id', None)
        return jsonify({
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'version': VERSION,
            'daily_analytics': analytics,
            'daily_sales': sales,
            'gustr_daily_snapshots': gustr,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    info = {'status': 'healthy', 'timestamp': datetime.now().isoformat(),
            'version': VERSION}
    try:
        with db.get_connection() as conn:
            latest = conn.execute(
                'SELECT analytics_date, snapshot_at FROM daily_analytics '
                'ORDER BY analytics_date DESC LIMIT 1').fetchone()
            count = conn.execute('SELECT COUNT(*) AS c FROM daily_analytics').fetchone()['c']
            sales_count = conn.execute('SELECT COUNT(*) AS c FROM daily_sales').fetchone()['c']
        info.update({
            'database': 'connected',
            'history_days': count,
            'sales_history_days': sales_count,
            'latest_snapshot_date': latest['analytics_date'] if latest else None,
            'latest_snapshot_at': latest['snapshot_at'] if latest else None,
        })
    except Exception as e:
        info.update({'status': 'degraded', 'database': f'error: {e}'})
    return jsonify(info)


@app.route('/api/export-pdf')
def export_pdf():
    try:
        with db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM daily_analytics ORDER BY analytics_date DESC LIMIT 1
            """).fetchone()
            if not row:
                return jsonify({'error': 'No data available'}), 404
            pdf_data = {
                'eth_price_usd': row['eth_price_usd'],
                'origins': {
                    'floor_price_eth': row['origins_floor_eth'],
                    'floor_price_usd': (row['origins_floor_eth'] or 0) * row['eth_price_usd'],
                    'volume_24h_eth': 0,
                    'market_cap_usd': row['origins_market_cap_usd'],
                    'total_supply': row['origins_supply'],
                },
                'undead': {
                    'floor_price_eth': row['undead_floor_eth'],
                    'floor_price_usd': (row['undead_floor_eth'] or 0) * row['eth_price_usd'],
                    'volume_24h_eth': (row['undead_volume_24h_eth']
                                       if 'undead_volume_24h_eth' in row.keys()
                                       and row['undead_volume_24h_eth'] is not None else 0),
                    'market_cap_usd': row['undead_market_cap_usd'],
                    'total_supply': row['undead_supply'],
                },
                'migration_analytics': {
                    'migration_rate': {
                        'total_migrations': row['total_migrations'],
                        'migration_percent': row['migration_percent'],
                        'price_ratio': row['price_ratio'],
                    }
                },
                'ecosystem_value': row['combined_market_cap_usd'],
            }
        from pdf_generator import PDFReportGenerator
        pdf_buffer = PDFReportGenerator().generate_pdf(pdf_data)
        return send_file(
            pdf_buffer, mimetype='application/pdf', as_attachment=True,
            download_name=f'GU_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Background collector
# ---------------------------------------------------------------------------
_collector_started = False
_collector_guard = threading.Lock()


def _collector_loop():
    time.sleep(15)  # let the web server come up first
    # One-time: backfill real sales history if the table is empty
    try:
        with db.get_connection() as conn:
            empty = conn.execute('SELECT COUNT(*) AS c FROM daily_sales').fetchone()['c'] == 0
        if empty:
            print(f'[Collector] Backfilling {SALES_BACKFILL_DAYS}d of sales history...')
            update_sales_history(days=SALES_BACKFILL_DAYS)
    except Exception as e:
        print(f'[Collector] sales backfill failed: {e}')

    while True:
        try:
            collect_snapshot(force=True)
        except Exception as e:
            print(f'[Collector] snapshot failed: {e}')
        try:
            cached('gustr_payload', 300, _build_gustr_payload)
        except Exception as e:
            print(f'[Collector] GUSTR refresh failed: {e}')
        time.sleep(COLLECTOR_PERIOD)


def start_collector():
    global _collector_started
    if os.environ.get('DISABLE_COLLECTOR') == '1':
        return
    with _collector_guard:
        if _collector_started:
            return
        threading.Thread(target=_collector_loop, daemon=True,
                         name='snapshot-collector').start()
        _collector_started = True
        print('[Collector] Background collector started (hourly)')


start_collector()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
