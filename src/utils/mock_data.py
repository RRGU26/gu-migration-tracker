import random
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
import logging

class MockDataGenerator:
    """Generate mock data for testing the system without API access"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Base data for realistic generation
        self.base_origins_supply = 10000
        self.base_undead_supply = 3000  # Starts lower, grows with migrations
        self.base_floor_price = 0.05  # ETH
        
        # Migration simulation
        self.daily_migration_range = (5, 25)  # migrations per day
        self.total_migrations = 0
    
    def generate_collection_data(self, collection_slug: str, target_date: date = None) -> Dict[str, Any]:
        """Generate mock collection data that mimics OpenSea API response"""
        if target_date is None:
            target_date = date.today()
        
        # Generate consistent but evolving data based on date
        days_since_start = (target_date - date(2024, 9, 1)).days  # Assume migration started Sept 1, 2024
        random.seed(hash(f"{collection_slug}_{target_date}"))  # Consistent data for same date
        
        if collection_slug == 'gu-origins':
            return self._generate_origins_data(days_since_start)
        elif collection_slug == 'genuine-undead':
            return self._generate_undead_data(days_since_start)
        else:
            return {}
    
    def _generate_origins_data(self, days_since_start: int) -> Dict[str, Any]:
        """Generate GU Origins mock data"""
        # Simulate gradual decline as tokens migrate
        migration_rate = min(0.3, days_since_start * 0.002)  # Max 30% migration
        current_supply = int(self.base_origins_supply * (1 - migration_rate))
        
        # Floor price with some volatility
        price_volatility = random.uniform(0.8, 1.3)
        floor_price = self.base_floor_price * price_volatility
        
        # Volume decreases as migration progresses
        volume_multiplier = max(0.1, 1 - migration_rate * 0.5)
        volume_24h = random.uniform(2, 15) * volume_multiplier
        
        # Listing percentage varies
        listed_percentage = random.uniform(8, 18)
        listed_count = int((listed_percentage / 100) * current_supply)
        
        # Generate mock owners
        owners = []
        for i in range(min(50, current_supply)):  # Sample of owners
            owners.append({
                'token_id': str(random.randint(1, self.base_origins_supply)),
                'holder_address': self._generate_mock_address(),
                'contract_address': '0x209e639a0EC166Ac7a1A4bA41968fa967dB30221'
            })
        
        return {
            'slug': 'gu-origins',
            'stats': {
                'total_supply': current_supply,
                'floor_price': floor_price,
                'one_day_volume': volume_24h,
                'seven_day_volume': volume_24h * random.uniform(6, 8),
                'average_price': floor_price * random.uniform(1.1, 1.8),
                'num_owners': int(current_supply * random.uniform(0.4, 0.7))  # Some wallets hold multiple
            },
            'details': {
                'name': 'GU Origins',
                'total_supply': current_supply
            },
            'listings': self._generate_mock_listings(listed_count, floor_price),
            'sales': self._generate_mock_sales(int(volume_24h / floor_price)),
            'owners': owners,
            'fetched_at': datetime.now().isoformat()
        }
    
    def _generate_undead_data(self, days_since_start: int) -> Dict[str, Any]:
        """Generate Genuine Undead mock data"""
        # Supply grows with migrations
        migration_rate = min(0.3, days_since_start * 0.002)
        migrated_tokens = int(self.base_origins_supply * migration_rate)
        current_supply = self.base_undead_supply + migrated_tokens
        
        # Floor price potentially higher due to scarcity/community value
        price_premium = random.uniform(1.0, 1.4)
        floor_price = self.base_floor_price * price_premium
        
        # Volume grows with migration and community activity
        volume_multiplier = max(0.5, migration_rate * 2 + 0.3)
        volume_24h = random.uniform(1, 8) * volume_multiplier
        
        # Listing percentage - often lower for community collections
        listed_percentage = random.uniform(5, 12)
        listed_count = int((listed_percentage / 100) * current_supply)
        
        # Generate mock owners (including migrated tokens)
        owners = []
        for i in range(min(50, current_supply)):
            owners.append({
                'token_id': str(random.randint(1, current_supply)),
                'holder_address': self._generate_mock_address(),
                'contract_address': '0x39509d8e1dd96cc8bad301ea65c75c7deb52374c'
            })
        
        return {
            'slug': 'genuine-undead',
            'stats': {
                'total_supply': current_supply,
                'floor_price': floor_price,
                'one_day_volume': volume_24h,
                'seven_day_volume': volume_24h * random.uniform(6, 9),
                'average_price': floor_price * random.uniform(1.2, 2.0),
                'num_owners': int(current_supply * random.uniform(0.5, 0.8))
            },
            'details': {
                'name': 'Genuine Undead',
                'total_supply': current_supply
            },
            'listings': self._generate_mock_listings(listed_count, floor_price),
            'sales': self._generate_mock_sales(int(volume_24h / floor_price)),
            'owners': owners,
            'fetched_at': datetime.now().isoformat()
        }
    
    def _generate_mock_listings(self, count: int, floor_price: float) -> List[Dict]:
        """Generate mock NFT listings"""
        listings = []
        for i in range(count):
            price_multiplier = random.uniform(1.0, 3.0)  # Some listed above floor
            listings.append({
                'identifier': str(random.randint(1, 10000)),
                'price_info': {
                    'amount': int((floor_price * price_multiplier) * 1e18),  # Wei format
                    'currency': 'ETH'
                }
            })
        return listings
    
    def _generate_mock_sales(self, count: int) -> List[Dict]:
        """Generate mock recent sales"""
        sales = []
        for i in range(count):
            sale_time = datetime.now() - timedelta(hours=random.randint(0, 24))
            sales.append({
                'created_date': sale_time.isoformat(),
                'price': random.uniform(0.03, 0.2),
                'event_type': 'sale'
            })
        return sales
    
    def _generate_mock_address(self) -> str:
        """Generate a mock Ethereum address"""
        return '0x' + ''.join([random.choice('0123456789abcdef') for _ in range(40)])
    
    def generate_daily_migrations(self, target_date: date = None) -> List[Dict]:
        """Generate mock daily migrations"""
        if target_date is None:
            target_date = date.today()
        
        # Consistent random seed for date
        random.seed(hash(f"migrations_{target_date}"))
        
        # Number of migrations varies by day
        num_migrations = random.randint(*self.daily_migration_range)
        
        migrations = []
        for i in range(num_migrations):
            migrations.append({
                'token_id': str(random.randint(1, self.base_origins_supply)),
                'from_collection': 'gu-origins',
                'to_collection': 'genuine-undead',
                'migration_date': target_date,
                'previous_holder': self._generate_mock_address(),
                'current_holder': self._generate_mock_address(),
                'same_holder': random.choice([True, False])  # Sometimes same holder migrates
            })
        
        return migrations
    
    def generate_historical_data(self, days: int = 30) -> Dict[str, List[Dict]]:
        """Generate historical data for multiple days"""
        historical_data = {
            'origins': [],
            'undead': [],
            'migrations': []
        }
        
        start_date = date.today() - timedelta(days=days)
        
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            
            # Generate collection data
            origins_data = self.generate_collection_data('gu-origins', current_date)
            undead_data = self.generate_collection_data('genuine-undead', current_date)
            
            historical_data['origins'].append({
                'date': current_date.isoformat(),
                'data': origins_data
            })
            historical_data['undead'].append({
                'date': current_date.isoformat(),
                'data': undead_data
            })
            
            # Generate migrations
            daily_migrations = self.generate_daily_migrations(current_date)
            if daily_migrations:
                historical_data['migrations'].append({
                    'date': current_date.isoformat(),
                    'migrations': daily_migrations
                })
        
        return historical_data
    
    def save_mock_data_file(self, filepath: str, days: int = 30):
        """Save generated mock data to JSON file for testing"""
        try:
            historical_data = self.generate_historical_data(days)
            
            with open(filepath, 'w') as f:
                json.dump(historical_data, f, indent=2, default=str)
            
            self.logger.info(f"Mock data saved to {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save mock data: {e}")
            raise

# Convenience functions for testing
def generate_mock_collections_data() -> Dict[str, Dict]:
    """Generate mock data for both collections"""
    generator = MockDataGenerator()
    return {
        'gu_origins': generator.generate_collection_data('gu-origins'),
        'genuine_undead': generator.generate_collection_data('genuine-undead')
    }

def create_test_data_file(filepath: str = "data/mock_data.json", days: int = 30):
    """Create a test data file with historical mock data"""
    generator = MockDataGenerator()
    return generator.save_mock_data_file(filepath, days)

# Mock API client for testing without OpenSea API
class MockOpenSeaClient:
    """Mock OpenSea client that returns generated data instead of API calls"""
    
    def __init__(self):
        self.generator = MockDataGenerator()
        self.logger = logging.getLogger(__name__)
    
    async def get_comprehensive_collection_data(self, collection_slug: str) -> Dict[str, Any]:
        """Return mock comprehensive collection data"""
        self.logger.info(f"Returning mock data for {collection_slug}")
        return self.generator.generate_collection_data(collection_slug)
    
    def extract_key_metrics(self, collection_data: Dict) -> Dict[str, Any]:
        """Extract key metrics from mock collection data"""
        stats = collection_data.get('stats', {})
        owners = collection_data.get('owners', [])
        listings = collection_data.get('listings', [])
        
        # Calculate listing percentage
        total_supply = stats.get('total_supply', 0)
        listed_count = len([l for l in listings if l.get('price_info')])
        listed_percentage = (listed_count / max(total_supply, 1)) * 100 if total_supply > 0 else 0
        
        # ETH to USD conversion (mock)
        eth_to_usd = 2000
        
        floor_price_eth = float(stats.get('floor_price', 0))
        volume_24h_eth = float(stats.get('one_day_volume', 0))
        volume_7d_eth = float(stats.get('seven_day_volume', 0))
        
        return {
            'total_supply': int(total_supply),
            'holders_count': len(set(o.get('holder_address', '') for o in owners)),
            'floor_price_eth': floor_price_eth,
            'floor_price_usd': floor_price_eth * eth_to_usd,
            'market_cap_eth': floor_price_eth * total_supply,
            'market_cap_usd': floor_price_eth * total_supply * eth_to_usd,
            'volume_24h_eth': volume_24h_eth,
            'volume_24h_usd': volume_24h_eth * eth_to_usd,
            'volume_7d_eth': volume_7d_eth,
            'volume_7d_usd': volume_7d_eth * eth_to_usd,
            'listed_count': listed_count,
            'listed_percentage': round(listed_percentage, 2),
            'average_price_eth': float(stats.get('average_price', 0)),
            'average_price_usd': float(stats.get('average_price', 0)) * eth_to_usd,
            'num_sales_24h': len(collection_data.get('sales', []))
        }