-- GU Migration Tracking Database Schema

-- Collections table
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    contract_address VARCHAR(42) UNIQUE NOT NULL,
    opensea_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily snapshots table  
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    total_supply INTEGER,
    holders_count INTEGER,
    floor_price_eth DECIMAL(18,6),
    floor_price_usd DECIMAL(10,2),
    market_cap_eth DECIMAL(18,6), 
    market_cap_usd DECIMAL(10,2),
    volume_24h_eth DECIMAL(18,6),
    volume_24h_usd DECIMAL(10,2),
    volume_7d_eth DECIMAL(18,6),
    volume_7d_usd DECIMAL(10,2),
    listed_count INTEGER,
    listed_percentage DECIMAL(5,2),
    average_price_eth DECIMAL(18,6),
    average_price_usd DECIMAL(10,2),
    num_sales_24h INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    UNIQUE(collection_id, snapshot_date)
);

-- Migration tracking table
CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id VARCHAR(100) NOT NULL,
    from_collection_id INTEGER NOT NULL,
    to_collection_id INTEGER NOT NULL,
    migration_date DATE NOT NULL,
    transaction_hash VARCHAR(66),
    block_number INTEGER,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_collection_id) REFERENCES collections(id),
    FOREIGN KEY (to_collection_id) REFERENCES collections(id),
    UNIQUE(token_id, from_collection_id, to_collection_id)
);

-- Token holders tracking (for migration detection)
CREATE TABLE IF NOT EXISTS token_holders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    token_id VARCHAR(100) NOT NULL,
    holder_address VARCHAR(42) NOT NULL,
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    UNIQUE(collection_id, token_id, snapshot_date)
);

-- API call logs for monitoring
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint VARCHAR(500) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System alerts and notifications
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR, CRITICAL
    message TEXT NOT NULL,
    data JSON,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily ETH prices table
CREATE TABLE IF NOT EXISTS daily_eth_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    price_date DATE UNIQUE NOT NULL,
    eth_price_usd DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily analytics table (stores all calculated metrics)
CREATE TABLE IF NOT EXISTS daily_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analytics_date DATE UNIQUE NOT NULL,
    eth_price_usd DECIMAL(10,2) NOT NULL,
    
    -- Origins data
    origins_floor_eth DECIMAL(18,6),
    origins_supply INTEGER,
    origins_market_cap_usd DECIMAL(15,2),
    origins_floor_change_24h DECIMAL(8,4),
    
    -- Genuine Undead data  
    undead_floor_eth DECIMAL(18,6),
    undead_supply INTEGER,
    undead_market_cap_usd DECIMAL(15,2),
    undead_floor_change_24h DECIMAL(8,4),
    undead_supply_change_24h INTEGER,
    
    -- Migration calculations (includes +26 burned GU)
    total_migrations INTEGER DEFAULT 26, -- Start with 26 burned
    migration_percent DECIMAL(8,4),
    price_ratio DECIMAL(8,4),
    combined_market_cap_usd DECIMAL(15,2),
    
    -- Daily migration activity  
    daily_new_migrations INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON daily_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_collection ON daily_snapshots(collection_id);
CREATE INDEX IF NOT EXISTS idx_migrations_date ON migrations(migration_date);
CREATE INDEX IF NOT EXISTS idx_migrations_token ON migrations(token_id);
CREATE INDEX IF NOT EXISTS idx_token_holders_date ON token_holders(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_token_holders_token ON token_holders(collection_id, token_id);
CREATE INDEX IF NOT EXISTS idx_api_logs_date ON api_logs(called_at);
CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_daily_eth_prices_date ON daily_eth_prices(price_date);
CREATE INDEX IF NOT EXISTS idx_daily_analytics_date ON daily_analytics(analytics_date);

-- Insert initial collection data
INSERT OR IGNORE INTO collections (slug, name, contract_address, opensea_url) VALUES 
('gu-origins', 'GU Origins', '0x209e639a0EC166Ac7a1A4bA41968fa967dB30221', 'https://opensea.io/collection/gu-origins'),
('genuine-undead', 'Genuine Undead', '0x39509d8e1dd96cc8bad301ea65c75c7deb52374c', 'https://opensea.io/collection/genuine-undead');