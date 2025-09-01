-- Enhanced GU Migration Tracking Database Schema
-- Add daily ETH prices and calculated analytics

-- Daily ETH prices table
CREATE TABLE IF NOT EXISTS daily_eth_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    price_date DATE UNIQUE NOT NULL,
    eth_price_usd DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily analytics table for calculated values
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_eth_prices_date ON daily_eth_prices(price_date);
CREATE INDEX IF NOT EXISTS idx_daily_analytics_date ON daily_analytics(analytics_date);