#!/usr/bin/env python3
"""
GU Migration Tracker - Main Application Entry Point

This is the main entry point for the GU Migration Tracking System.
It provides multiple modes of operation:
1. Daily report generation
2. Background scheduler
3. System health checks
4. Testing mode with mock data

Usage:
    python main.py --mode daily                    # Run daily report once
    python main.py --mode scheduler                # Run background scheduler  
    python main.py --mode health                   # Check system health
    python main.py --mode test                     # Run with test data
    python main.py --mode setup                    # Initialize database
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import date, datetime
from typing import Dict, Any
import json

# Add src to path
sys.path.append('src')

from src.database.database import DatabaseManager
from src.utils.scheduler import TaskScheduler, run_manual_daily_report
from src.utils.monitoring import SystemMonitor, run_health_check
from src.utils.mock_data import MockDataGenerator, create_test_data_file
from src.reports.report_generator import generate_daily_report
from src.utils.migration_detector import run_daily_migration_detection
from config.config import Config

# Set up logging
def setup_logging():
    """Configure logging for the application"""
    os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

async def run_daily_mode(target_date: str = None):
    """Run daily report generation once"""
    logger = logging.getLogger(__name__)
    logger.info("Starting daily report generation...")
    
    try:
        # Parse target date if provided
        report_date = date.fromisoformat(target_date) if target_date else date.today()
        
        # Run migration detection first
        logger.info(f"Detecting migrations for {report_date}")
        migration_result = await run_daily_migration_detection(report_date)
        
        logger.info(f"Migration detection completed: {migration_result.get('migrations_detected', 0)} migrations found")
        
        # Generate comprehensive report
        logger.info("Generating daily report...")
        report_paths = await generate_daily_report(report_date)
        
        logger.info(f"Daily report completed successfully!")
        logger.info(f"Report files generated:")
        for format_type, path in report_paths.items():
            if isinstance(path, str) and os.path.exists(path):
                logger.info(f"  {format_type}: {path}")
        
        return {
            'success': True,
            'migration_result': migration_result,
            'report_paths': report_paths
        }
        
    except Exception as e:
        logger.error(f"Daily mode failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def run_scheduler_mode():
    """Run background scheduler for automated daily reports"""
    logger = logging.getLogger(__name__)
    logger.info("Starting GU Migration Tracker scheduler...")
    
    try:
        scheduler = TaskScheduler()
        scheduler.setup_daily_schedule()
        
        logger.info("Scheduler configured. Daily reports will run automatically.")
        logger.info("Schedule:")
        logger.info("  8:00 AM EST - Data Collection")
        logger.info("  9:00 AM EST - Report Generation") 
        logger.info("  10:00 AM EST Sunday - Weekly Summary")
        logger.info("Press Ctrl+C to stop the scheduler")
        
        scheduler.start_scheduler()
        
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler failed: {e}")
        sys.exit(1)

def run_health_mode():
    """Run system health check"""
    logger = logging.getLogger(__name__)
    logger.info("Running system health check...")
    
    try:
        health_report = run_health_check()
        
        # Print health report
        print("\n" + "="*60)
        print("GU MIGRATION TRACKER - SYSTEM HEALTH REPORT")
        print("="*60)
        print(f"Overall Status: {health_report['overall_status'].upper()}")
        print(f"Checked at: {health_report['timestamp']}")
        
        print("\nCOMPONENT STATUS:")
        for component, status in health_report['components'].items():
            status_indicator = "✅" if status.get('status') == 'healthy' else "⚠️" if status.get('status') == 'warning' else "❌"
            print(f"  {status_indicator} {component.title()}: {status.get('message', 'Unknown')}")
        
        if health_report.get('recommendations'):
            print(f"\nRECOMMENDATIONS:")
            for i, rec in enumerate(health_report['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "="*60)
        
        # Save detailed report
        health_file = f"reports/health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(health_file), exist_ok=True)
        
        with open(health_file, 'w') as f:
            json.dump(health_report, f, indent=2, default=str)
        
        print(f"Detailed health report saved to: {health_file}")
        
        return health_report
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        print(f"❌ Health check failed: {e}")
        sys.exit(1)

async def run_test_mode():
    """Run system in test mode with mock data"""
    logger = logging.getLogger(__name__)
    logger.info("Running in test mode with mock data...")
    
    try:
        # Generate mock data
        logger.info("Generating mock historical data...")
        mock_generator = MockDataGenerator()
        mock_file = "data/test_mock_data.json"
        os.makedirs("data", exist_ok=True)
        
        mock_generator.save_mock_data_file(mock_file, days=14)
        logger.info(f"Mock data generated: {mock_file}")
        
        # Test database operations
        logger.info("Testing database operations...")
        db = DatabaseManager()
        collections = db.get_collections()
        logger.info(f"Found {len(collections)} collections in database")
        
        # Generate test report using mock data
        logger.info("Generating test report...")
        
        # Patch the API client to use mock data for testing
        import src.api.opensea_client as opensea_module
        from src.utils.mock_data import MockOpenSeaClient
        
        # Temporarily replace the real client with mock
        original_fetch = opensea_module.fetch_all_collections_data
        
        async def mock_fetch_all():
            mock_client = MockOpenSeaClient()
            return {
                'gu_origins': await mock_client.get_comprehensive_collection_data('gu-origins'),
                'genuine_undead': await mock_client.get_comprehensive_collection_data('genuine-undead')
            }
        
        opensea_module.fetch_all_collections_data = mock_fetch_all
        
        try:
            # Run test report generation
            test_date = date.today()
            report_result = await run_daily_mode()
            
            if report_result['success']:
                logger.info("✅ Test mode completed successfully!")
                logger.info("Test report files:")
                for format_type, path in report_result['report_paths'].items():
                    if isinstance(path, str):
                        logger.info(f"  {format_type}: {path}")
            else:
                logger.error(f"❌ Test mode failed: {report_result.get('error')}")
                
        finally:
            # Restore original function
            opensea_module.fetch_all_collections_data = original_fetch
        
        return report_result
        
    except Exception as e:
        logger.error(f"Test mode failed: {e}")
        return {'success': False, 'error': str(e)}

def run_setup_mode():
    """Initialize database and create necessary directories"""
    logger = logging.getLogger(__name__)
    logger.info("Setting up GU Migration Tracker...")
    
    try:
        # Create directories
        directories = [
            "data",
            "reports/daily", 
            "reports/charts",
            "logs"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        
        # Initialize database
        logger.info("Initializing database...")
        db = DatabaseManager()
        
        # Verify collections are inserted
        collections = db.get_collections()
        logger.info(f"Database initialized with {len(collections)} collections:")
        for collection in collections:
            logger.info(f"  - {collection['name']} ({collection['slug']})")
        
        # Create .env file if it doesn't exist
        if not os.path.exists('.env'):
            logger.info("Creating .env file from template...")
            with open('.env.example', 'r') as template:
                with open('.env', 'w') as env_file:
                    env_file.write(template.read())
            logger.info("✅ .env file created. Please edit it with your API keys.")
        else:
            logger.info("✅ .env file already exists")
        
        logger.info("✅ Setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Edit .env file with your OpenSea API key")
        logger.info("2. Run: python main.py --mode test (to test with mock data)")
        logger.info("3. Run: python main.py --mode daily (to generate real report)")
        logger.info("4. Run: python main.py --mode scheduler (for automated daily reports)")
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='GU Migration Tracking System')
    parser.add_argument(
        '--mode',
        choices=['daily', 'scheduler', 'health', 'test', 'setup'],
        required=True,
        help='Operation mode'
    )
    parser.add_argument(
        '--date',
        help='Target date for daily report (YYYY-MM-DD format)',
        default=None
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Override log level if verbose
    if args.verbose:
        Config.LOG_LEVEL = 'DEBUG'
    
    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting GU Migration Tracker in {args.mode} mode")
    
    # Route to appropriate mode
    if args.mode == 'daily':
        result = asyncio.run(run_daily_mode(args.date))
        sys.exit(0 if result['success'] else 1)
        
    elif args.mode == 'scheduler':
        run_scheduler_mode()
        
    elif args.mode == 'health':
        health_report = run_health_mode()
        status = health_report['overall_status']
        sys.exit(0 if status == 'healthy' else 1 if status == 'warning' else 2)
        
    elif args.mode == 'test':
        result = asyncio.run(run_test_mode())
        sys.exit(0 if result['success'] else 1)
        
    elif args.mode == 'setup':
        run_setup_mode()
        
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()