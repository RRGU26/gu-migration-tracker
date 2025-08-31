import logging
import time
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Callable
import functools
import traceback
import smtplib
from email.mime.text import MIMEText
import json

from src.database.database import DatabaseManager
from config.config import Config

class SystemMonitor:
    """Comprehensive system monitoring and alerting"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)
        self.alert_thresholds = {
            'api_failure_rate': 0.3,  # 30% failure rate
            'migration_spike': Config.MIGRATION_SPIKE_THRESHOLD,
            'volume_anomaly': Config.VOLUME_ANOMALY_THRESHOLD,
            'consecutive_failures': 5,
            'low_data_quality': 0.8  # 80% minimum data quality
        }
    
    def check_system_health(self) -> Dict[str, Any]:
        """Perform comprehensive system health check"""
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'components': {},
            'alerts': [],
            'recommendations': []
        }
        
        try:
            # Check API health
            api_health = self._check_api_health()
            health_report['components']['api'] = api_health
            
            # Check database health
            db_health = self._check_database_health()
            health_report['components']['database'] = db_health
            
            # Check data freshness
            data_freshness = self._check_data_freshness()
            health_report['components']['data_freshness'] = data_freshness
            
            # Check for anomalies
            anomalies = self._check_for_anomalies()
            health_report['components']['anomalies'] = anomalies
            
            # Check unresolved alerts
            unresolved_alerts = self.db.get_unresolved_alerts()
            health_report['components']['alerts'] = {
                'status': 'warning' if unresolved_alerts else 'healthy',
                'unresolved_count': len(unresolved_alerts),
                'critical_count': len([a for a in unresolved_alerts if a['severity'] == 'CRITICAL']),
                'details': unresolved_alerts[:5]  # Last 5 for brevity
            }
            
            # Determine overall status
            component_statuses = [comp.get('status', 'unknown') for comp in health_report['components'].values()]
            if 'critical' in component_statuses:
                health_report['overall_status'] = 'critical'
            elif 'warning' in component_statuses:
                health_report['overall_status'] = 'warning'
            
            # Generate recommendations
            health_report['recommendations'] = self._generate_recommendations(health_report['components'])
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            health_report['overall_status'] = 'critical'
            health_report['error'] = str(e)
        
        return health_report
    
    def _check_api_health(self) -> Dict[str, Any]:
        """Check API health based on recent call logs"""
        try:
            # Get API logs from last 24 hours
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_calls,
                        COUNT(CASE WHEN status_code >= 400 THEN 1 END) as failed_calls,
                        AVG(response_time_ms) as avg_response_time,
                        MAX(called_at) as last_call
                    FROM api_logs 
                    WHERE called_at >= datetime('now', '-24 hours')
                """)
                
                stats = cursor.fetchone()
                
                if not stats or stats['total_calls'] == 0:
                    return {
                        'status': 'warning',
                        'message': 'No API calls in last 24 hours',
                        'total_calls': 0
                    }
                
                failure_rate = (stats['failed_calls'] or 0) / stats['total_calls']
                
                # Determine status
                if failure_rate > self.alert_thresholds['api_failure_rate']:
                    status = 'critical'
                    message = f"High API failure rate: {failure_rate:.2%}"
                elif stats['avg_response_time'] > 10000:  # 10 seconds
                    status = 'warning'
                    message = f"Slow API response time: {stats['avg_response_time']:.0f}ms"
                else:
                    status = 'healthy'
                    message = "API performance normal"
                
                return {
                    'status': status,
                    'message': message,
                    'total_calls': stats['total_calls'],
                    'failed_calls': stats['failed_calls'] or 0,
                    'failure_rate': failure_rate,
                    'avg_response_time_ms': stats['avg_response_time'] or 0,
                    'last_call': stats['last_call']
                }
        
        except Exception as e:
            return {
                'status': 'critical',
                'message': f"API health check failed: {str(e)}",
                'error': str(e)
            }
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database health and integrity"""
        try:
            # Test database connectivity and basic operations
            with self.db.get_connection() as conn:
                # Check if we can read from main tables
                collections_count = conn.execute("SELECT COUNT(*) as count FROM collections").fetchone()['count']
                snapshots_count = conn.execute("SELECT COUNT(*) as count FROM daily_snapshots").fetchone()['count']
                migrations_count = conn.execute("SELECT COUNT(*) as count FROM migrations").fetchone()['count']
                
                # Check for recent data
                cursor = conn.execute("""
                    SELECT MAX(snapshot_date) as latest_snapshot 
                    FROM daily_snapshots
                """)
                latest_snapshot = cursor.fetchone()['latest_snapshot']
                
                # Determine status
                if not latest_snapshot:
                    status = 'warning'
                    message = "No snapshot data found"
                elif latest_snapshot < (date.today() - timedelta(days=2)).isoformat():
                    status = 'warning'
                    message = f"Latest snapshot is old: {latest_snapshot}"
                else:
                    status = 'healthy'
                    message = "Database operating normally"
                
                return {
                    'status': status,
                    'message': message,
                    'collections_count': collections_count,
                    'snapshots_count': snapshots_count,
                    'migrations_count': migrations_count,
                    'latest_snapshot': latest_snapshot
                }
        
        except Exception as e:
            return {
                'status': 'critical',
                'message': f"Database health check failed: {str(e)}",
                'error': str(e)
            }
    
    def _check_data_freshness(self) -> Dict[str, Any]:
        """Check if data is fresh and up to date"""
        try:
            origins_id = self.db.get_collection_id('gu-origins')
            undead_id = self.db.get_collection_id('genuine-undead')
            
            if not origins_id or not undead_id:
                return {
                    'status': 'critical',
                    'message': 'Collection IDs not found'
                }
            
            origins_snapshot = self.db.get_latest_snapshot(origins_id)
            undead_snapshot = self.db.get_latest_snapshot(undead_id)
            
            issues = []
            
            # Check if we have recent snapshots
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            if not origins_snapshot or origins_snapshot.get('snapshot_date') < yesterday.isoformat():
                issues.append('GU Origins data is stale')
            
            if not undead_snapshot or undead_snapshot.get('snapshot_date') < yesterday.isoformat():
                issues.append('Genuine Undead data is stale')
            
            # Check data quality (non-zero values for key metrics)
            if origins_snapshot:
                if not origins_snapshot.get('floor_price_eth') or origins_snapshot.get('floor_price_eth') <= 0:
                    issues.append('GU Origins floor price missing/invalid')
                if not origins_snapshot.get('total_supply') or origins_snapshot.get('total_supply') <= 0:
                    issues.append('GU Origins supply data missing')
            
            if undead_snapshot:
                if not undead_snapshot.get('floor_price_eth') or undead_snapshot.get('floor_price_eth') <= 0:
                    issues.append('Genuine Undead floor price missing/invalid')
                if not undead_snapshot.get('total_supply') or undead_snapshot.get('total_supply') <= 0:
                    issues.append('Genuine Undead supply data missing')
            
            # Determine status
            if not issues:
                status = 'healthy'
                message = 'All data is fresh and valid'
            elif len(issues) <= 2:
                status = 'warning'
                message = f'Some data issues: {"; ".join(issues[:2])}'
            else:
                status = 'critical'
                message = f'Multiple data issues: {"; ".join(issues[:3])}'
            
            return {
                'status': status,
                'message': message,
                'issues': issues,
                'origins_last_update': origins_snapshot.get('snapshot_date') if origins_snapshot else None,
                'undead_last_update': undead_snapshot.get('snapshot_date') if undead_snapshot else None
            }
        
        except Exception as e:
            return {
                'status': 'critical',
                'message': f"Data freshness check failed: {str(e)}",
                'error': str(e)
            }
    
    def _check_for_anomalies(self) -> Dict[str, Any]:
        """Check for data anomalies and unusual patterns"""
        try:
            anomalies = []
            
            # Check for migration spikes
            migration_stats = self.db.get_migration_stats(7)
            daily_breakdown = migration_stats.get('daily_breakdown', [])
            
            if len(daily_breakdown) >= 2:
                today_migrations = daily_breakdown[0].get('daily_count', 0)
                yesterday_migrations = daily_breakdown[1].get('daily_count', 0)
                
                if yesterday_migrations > 0:
                    spike_ratio = today_migrations / yesterday_migrations
                    if spike_ratio > self.alert_thresholds['migration_spike']:
                        anomalies.append(f"Migration spike detected: {spike_ratio:.1f}x increase")
            
            # Check for volume anomalies
            origins_id = self.db.get_collection_id('gu-origins')
            undead_id = self.db.get_collection_id('genuine-undead')
            
            origins_history = self.db.get_historical_snapshots(origins_id, 3)
            undead_history = self.db.get_historical_snapshots(undead_id, 3)
            
            if len(origins_history) >= 2:
                latest_volume = origins_history[0].get('volume_24h_eth', 0)
                previous_volume = origins_history[1].get('volume_24h_eth', 0)
                
                if previous_volume > 0:
                    volume_ratio = latest_volume / previous_volume
                    if volume_ratio > self.alert_thresholds['volume_anomaly']:
                        anomalies.append(f"GU Origins volume spike: {volume_ratio:.1f}x increase")
            
            if len(undead_history) >= 2:
                latest_volume = undead_history[0].get('volume_24h_eth', 0)
                previous_volume = undead_history[1].get('volume_24h_eth', 0)
                
                if previous_volume > 0:
                    volume_ratio = latest_volume / previous_volume
                    if volume_ratio > self.alert_thresholds['volume_anomaly']:
                        anomalies.append(f"Genuine Undead volume spike: {volume_ratio:.1f}x increase")
            
            # Check for price anomalies (floor price drops > 50%)
            for collection_name, history in [('GU Origins', origins_history), ('Genuine Undead', undead_history)]:
                if len(history) >= 2:
                    current_price = history[0].get('floor_price_eth', 0)
                    previous_price = history[1].get('floor_price_eth', 0)
                    
                    if previous_price > 0 and current_price > 0:
                        price_change = (current_price - previous_price) / previous_price
                        if price_change < -0.5:  # 50% drop
                            anomalies.append(f"{collection_name} floor price dropped {abs(price_change):.1%}")
            
            # Determine status
            if not anomalies:
                status = 'healthy'
                message = 'No anomalies detected'
            elif len(anomalies) == 1:
                status = 'warning'
                message = f'Anomaly detected: {anomalies[0]}'
            else:
                status = 'critical'
                message = f'Multiple anomalies: {"; ".join(anomalies[:2])}'
            
            return {
                'status': status,
                'message': message,
                'anomalies': anomalies
            }
        
        except Exception as e:
            return {
                'status': 'critical',
                'message': f"Anomaly detection failed: {str(e)}",
                'error': str(e)
            }
    
    def _generate_recommendations(self, components: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on health check results"""
        recommendations = []
        
        # API recommendations
        api_status = components.get('api', {})
        if api_status.get('status') == 'critical':
            if api_status.get('failure_rate', 0) > 0.3:
                recommendations.append("Check OpenSea API key validity and rate limits")
            recommendations.append("Consider implementing circuit breaker pattern for API calls")
        
        # Database recommendations
        db_status = components.get('database', {})
        if db_status.get('status') in ['warning', 'critical']:
            recommendations.append("Check database connectivity and disk space")
            if db_status.get('latest_snapshot'):
                recommendations.append("Run manual data collection to update snapshots")
        
        # Data freshness recommendations
        freshness_status = components.get('data_freshness', {})
        if freshness_status.get('status') != 'healthy':
            recommendations.append("Verify scheduled tasks are running correctly")
            recommendations.append("Check collection data sources for availability")
        
        # Anomaly recommendations
        anomalies = components.get('anomalies', {})
        if anomalies.get('status') != 'healthy':
            recommendations.append("Investigate market events that may explain anomalies")
            recommendations.append("Consider adjusting alert thresholds if appropriate")
        
        # Alert recommendations
        alert_status = components.get('alerts', {})
        if alert_status.get('critical_count', 0) > 0:
            recommendations.append("Address critical alerts immediately")
        if alert_status.get('unresolved_count', 0) > 10:
            recommendations.append("Review and resolve old alerts to maintain clean monitoring")
        
        return recommendations
    
    def create_system_alert(self, alert_type: str, severity: str, message: str, 
                          data: Dict = None, send_notification: bool = True):
        """Create system alert with optional notification"""
        # Save to database
        self.db.create_alert(alert_type, severity, message, data)
        
        # Send notification for critical alerts
        if send_notification and severity == 'CRITICAL' and Config.EMAIL_TO and Config.EMAIL_FROM:
            self._send_alert_notification(alert_type, severity, message, data)
        
        # Log alert
        log_level = {
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }.get(severity, logging.INFO)
        
        self.logger.log(log_level, f"[{alert_type}] {message}")
    
    def _send_alert_notification(self, alert_type: str, severity: str, 
                               message: str, data: Dict = None):
        """Send email notification for critical alerts"""
        try:
            subject = f"🚨 GU Migration Tracker Alert: {alert_type}"
            
            body = f"""
            CRITICAL ALERT NOTIFICATION
            
            Alert Type: {alert_type}
            Severity: {severity}
            Time: {datetime.now().isoformat()}
            
            Message: {message}
            
            Additional Data: {json.dumps(data, indent=2) if data else 'None'}
            
            Please check the system immediately.
            
            ---
            GU Migration Tracker Monitoring System
            """
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = Config.EMAIL_FROM
            msg['To'] = ', '.join(Config.EMAIL_TO)
            
            with smtplib.SMTP(Config.EMAIL_SMTP_SERVER, Config.EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_FROM, Config.EMAIL_PASSWORD)
                server.send_message(msg)
            
            self.logger.info(f"Alert notification sent for {alert_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to send alert notification: {e}")

def monitor_function(func: Callable) -> Callable:
    """Decorator to monitor function execution and create alerts on failures"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        monitor = SystemMonitor()
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # ms
            
            # Log successful execution
            monitor.logger.debug(f"Function {func.__name__} completed in {execution_time:.0f}ms")
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000  # ms
            error_details = {
                'function': func.__name__,
                'execution_time_ms': execution_time,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Create alert for function failure
            monitor.create_system_alert(
                f'function_failure_{func.__name__}',
                'ERROR',
                f"Function {func.__name__} failed: {str(e)}",
                error_details
            )
            
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        monitor = SystemMonitor()
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # ms
            
            # Log successful execution
            monitor.logger.debug(f"Function {func.__name__} completed in {execution_time:.0f}ms")
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000  # ms
            error_details = {
                'function': func.__name__,
                'execution_time_ms': execution_time,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Create alert for function failure
            monitor.create_system_alert(
                f'function_failure_{func.__name__}',
                'ERROR',
                f"Function {func.__name__} failed: {str(e)}",
                error_details
            )
            
            raise
    
    # Return appropriate wrapper based on whether function is async
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# Convenience functions
def run_health_check() -> Dict[str, Any]:
    """Run system health check"""
    monitor = SystemMonitor()
    return monitor.check_system_health()

def create_alert(alert_type: str, severity: str, message: str, data: Dict = None):
    """Create system alert"""
    monitor = SystemMonitor()
    monitor.create_system_alert(alert_type, severity, message, data)