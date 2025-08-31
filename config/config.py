import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Configuration
    OPENSEA_API_KEY = os.getenv('OPENSEA_API_KEY', '')
    ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY', '')
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/gu_migration.db')
    
    # Collections Configuration
    COLLECTIONS = {
        'gu_origins': {
            'slug': 'gu-origins',
            'name': 'GU Origins',
            'contract_address': '0x209e639a0EC166Ac7a1A4bA41968fa967dB30221',
            'opensea_url': 'https://opensea.io/collection/gu-origins'
        },
        'genuine_undead': {
            'slug': 'genuine-undead',
            'name': 'Genuine Undead',
            'contract_address': '0x39509d8e1dd96cc8bad301ea65c75c7deb52374c',
            'opensea_url': 'https://opensea.io/collection/genuine-undead'
        }
    }
    
    # API Configuration
    OPENSEA_BASE_URL = 'https://api.opensea.io/api/v2'
    ETHERSCAN_BASE_URL = 'https://api.etherscan.io/api'
    
    # Rate Limiting
    API_RATE_LIMIT = 4  # requests per second for OpenSea
    REQUEST_TIMEOUT = 30  # seconds
    
    # Reporting Configuration
    REPORT_OUTPUT_DIR = os.getenv('REPORT_OUTPUT_DIR', './reports')
    REPORT_TIME = '09:00'  # Daily report generation time (EST)
    
    # Email Configuration
    EMAIL_SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', '587'))
    EMAIL_FROM = os.getenv('EMAIL_FROM', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    EMAIL_TO = os.getenv('EMAIL_TO', '').split(',')
    
    # Monitoring Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/gu_migration.log')
    
    # Data Validation
    MAX_DATA_AGE_HOURS = 2
    MIN_FLOOR_PRICE = 0.001  # ETH
    MAX_FLOOR_PRICE = 100.0  # ETH
    
    # Alert Thresholds
    MIGRATION_SPIKE_THRESHOLD = 0.5  # 50% increase day-over-day
    VOLUME_ANOMALY_THRESHOLD = 2.0   # 200% increase day-over-day
    API_FAILURE_ALERT_MINUTES = 60