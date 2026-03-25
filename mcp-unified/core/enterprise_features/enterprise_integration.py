import logging
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
from mcp_unified.core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class EnterpriseIntegration:
    def __init__(self, semantic_analyzer: SemanticAnalyzer):
        self.semantic_analyzer = semantic_analyzer
        self.integration_config = {}
        self.connected_systems = {}

    def configure_integration(self, config: Dict) -> Dict:
        """
        Configure enterprise integration
        """
        try:
            # Validate config
            required_keys = ['systems', 'authentication', 'sync_settings']
            for key in required_keys:
                if key not in config:
                    return {'error': f'Missing required config key: {key}'}

            self.integration_config = config
            return {'success': True, 'config': config}
        except Exception as e:
            logger.error(f"Error configuring integration: {e}")
            return {'error': str(e)}

    async def connect_to_systems(self) -> Dict:
        """
        Connect to enterprise systems
        """
        try:
            results = {}
            for system_name, system_config in self.integration_config.get('systems', {}).items():
                try:
                    # Connect to each system
                    if system_config['type'] == 'database':
                        result = await self._connect_to_database(system_name, system_config)
                    elif system_config['type'] == 'api':
                        result = await self._connect_to_api(system_name, system_config)
                    elif system_config['type'] == 'file_system':
                        result = await self._connect_to_file_system(system_config)
                    else:
                        result = {'error': f'Unsupported system type: {system_config["type"]}'}

                    results[system_name] = result
                except Exception as e:
                    results[system_name] = {'error': str(e)}

            self.connected_systems = results
            return results
        except Exception as e:
            logger.error(f"Error connecting to systems: {e}")
            return {'error': str(e)}

    async def _connect_to_database(self, system_name: str, config: Dict) -> Dict:
        """
        Connect to database system
        """
        try:
            import asyncpg
            import sqlalchemy

            # Create database connection
            engine = sqlalchemy.create_engine(config['connection_string'])
            connection = engine.connect()

            # Test connection
            test_result = connection.execute("SELECT 1").fetchone()
            if test_result != (1,):
                return {'error': 'Database connection test failed'}

            return {
                'status': 'connected',
                'database': config['database'],
                'connection_string': config['connection_string'],
                'test_result': 'success'
            }
        except Exception as e:
            return {'error': str(e)}

    async def _connect_to_api(self, system_name: str, config: Dict) -> Dict:
        """
        Connect to API system
        """
        try:
            import requests

            # Test API connection
            response = requests.get(config['base_url'], timeout=10)

            if response.status_code != 200:
                return {'error': f'API connection failed with status {response.status_code}'}

            return {
                'status': 'connected',
                'api_url': config['base_url'],
                'response_time': response.elapsed.total_seconds(),
                'test_result': 'success'
            }
        except Exception as e:
            return {'error': str(e)}

    async def _connect_to_file_system(self, config: Dict) -> Dict:
        """
        Connect to file system
        """
        try:
            # Check if directory exists
            directory = Path(config['path'])
            if not directory.exists():
                return {'error': f'Directory does not exist: {config["path"]}'}

            # Get directory info
            files = list(directory.glob('*'))
            return {
                'status': 'connected',
                'path': config['path'],
                'total_files': len(files),
                'total_size': sum(f.stat().st_size for f in files if f.is_file()),
                'test_result': 'success'
            }
        except Exception as e:
            return {'error': str(e)}

    async def sync_data(self, source_system: str, target_system: str) -> Dict:
        """
        Sync data between systems
        """
        try:
            if source_system not in self.connected_systems:
                return {'error': f'Source system not connected: {source_system}'}
            if target_system not in self.connected_systems:
                return {'error': f'Target system not connected: {target_system}'}

            # Get data from source
            source_data = await self._get_data_from_system(source_system)

            # Transform data
            transformed_data = await self._transform_data(source_data, source_system, target_system)

            # Send data to target
            result = await self._send_data_to_system(target_system, transformed_data)

            return {
                'status': 'synced',
                'source': source_system,
                'target': target_system,
                'records_processed': len(transformed_data),
                'result': result
            }
        except Exception as e:
            logger.error(f"Error syncing data: {e}")
            return {'error': str(e)}

    async def _get_data_from_system(self, system_name: str) -> List[Dict]:
        """
        Get data from connected system
        """
        try:
            system = self.connected_systems[system_name]

            if system['status'] == 'connected':
                if 'database' in system:
                    # Get data from database
                    import sqlalchemy
                    engine = sqlalchemy.create_engine(system['connection_string'])
                    with engine.connect() as connection:
                        result = connection.execute("SELECT * FROM data").fetchall()
                        return [dict(row) for row in result]
                elif 'api_url' in system:
                    # Get data from API
                    import requests
                    response = requests.get(f"{system['api_url']}/data")
                    return response.json()
                elif 'path' in system:
                    # Get data from file system
                    import json
                    directory = Path(system['path'])
                    data_files = directory.glob('*.json')
                    data = []
                    for file in data_files:
                        with open(file, 'r') as f:
                            data.append(json.load(f))
                    return data
            else:
                return {'error': 'System not connected'}
        except Exception as e:
            return {'error': str(e)}

    async def _transform_data(self, data: List[Dict], source_system: str, target_system: str) -> List[Dict]:
        """
        Transform data for target system
        """
        try:
            # Simple transformation example
            transformed = []
            for item in data:
                transformed_item = {
                    'id': item.get('id'),
                    'source': source_system,
                    'target': target_system,
                    'data': item,
                    'timestamp': item.get('timestamp', time.time())
                }
                transformed.append(transformed_item)

            return transformed
        except Exception as e:
            return {'error': str(e)}

    async def _send_data_to_system(self, system_name: str, data: List[Dict]) -> Dict:
        """
        Send data to connected system
        """
        try:
            system = self.connected_systems[system_name]

            if system['status'] == 'connected':
                if 'database' in system:
                    # Insert data into database
                    import sqlalchemy
                    engine = sqlalchemy.create_engine(system['connection_string'])
                    with engine.connect() as connection:
                        for item in data:
                            connection.execute(
                                "INSERT INTO data (id, source, target, data, timestamp) VALUES (%s, %s, %s, %s, %s)",
                                (item['id'], item['source'], item['target'], json.dumps(item['data']), item['timestamp'])
                            )
                        return {'status': 'inserted', 'count': len(data)}
                elif 'api_url' in system:
                    # Send data to API
                    import requests
                    response = requests.post(f"{system['api_url']}/data", json=data)
                    return {'status': 'sent', 'response': response.status_code}
                elif 'path' in system:
                    # Save data to file system
                    import json
                    directory = Path(system['path'])
                    for i, item in enumerate(data):
                        with open(directory / f"data_{i}.json", 'w') as f:
                            json.dump(item, f)
                    return {'status': 'saved', 'count': len(data)}
            else:
                return {'error': 'System not connected'}
        except Exception as e:
            return {'error': str(e)}

    async def run_automation(self, automation_config: Dict) -> Dict:
        """
        Run enterprise automation
        """
        try:
            automation_results = {}

            for automation_name, automation in automation_config.items():
                try:
                    # Execute automation
                    if automation['type'] == 'data_sync':
                        result = await self.sync_data(automation['source'], automation['target'])
                    elif automation['type'] == 'data_analysis':
                        result = await self._analyze_data(automation['source'], automation['parameters'])
                    elif automation['type'] == 'report_generation':
                        result = await self._generate_report(automation['source'], automation['format'])
                    else:
                        result = {'error': f'Unsupported automation type: {automation["type"]}'}

                    automation_results[automation_name] = result
                except Exception as e:
                    automation_results[automation_name] = {'error': str(e)}

            return automation_results
        except Exception as e:
            logger.error(f"Error running automation: {e}")
            return {'error': str(e)}

    async def _analyze_data(self, system_name: str, parameters: Dict) -> Dict:
        """
        Analyze data from system
        """
        try:
            data = await self._get_data_from_system(system_name)

            if 'error' in data:
                return data

            # Simple analysis
            analysis = {
                'total_records': len(data),
                'unique_keys': len(set(item.get('id') for item in data)),
                'avg_record_size': sum(len(json.dumps(item)) for item in data) / len(data) if data else 0,
                'analysis_time': time.time()
            }

            return analysis
        except Exception as e:
            return {'error': str(e)}

    async def _generate_report(self, system_name: str, format: str) -> Dict:
        """
        Generate report from system data
        """
        try:
            data = await self._get_data_from_system(system_name)

            if 'error' in data:
                return data

            # Generate report based on format
            if format == 'json':
                import json
                report = {
                    'generated_at': time.time(),
                    'total_records': len(data),
                    'sample_data': data[:10]
                }
                return {'status': 'generated', 'format': 'json', 'report': report}
            elif format == 'csv':
                import csv
                import io
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(data[0].keys())
                for item in data:
                    writer.writerow(item.values())
                return {'status': 'generated', 'format': 'csv', 'report': output.getvalue()}
            else:
                return {'error': f'Unsupported report format: {format}'}
        except Exception as e:
            return {'error': str(e)}

    async def get_system_status(self) -> Dict:
        """
        Get status of all connected systems
        """
        try:
            status = {}
            for system_name, system_info in self.connected_systems.items():
                status[system_name] = {
                    'connected': system_info['status'] == 'connected',
                    'type': system_info.get('type', 'unknown'),
                    'last_heartbeat': time.time(),
                    'performance': await self._check_system_performance(system_name)
                }
            return status
        except Exception as e:
            return {'error': str(e)}

    async def _check_system_performance(self, system_name: str) -> Dict:
        """
        Check system performance
        """
        try:
            system = self.connected_systems[system_name]

            if system['status'] == 'connected':
                if 'database' in system:
                    # Check database performance
                    import sqlalchemy
                    engine = sqlalchemy.create_engine(system['connection_string'])
                    with engine.connect() as connection:
                        start_time = time.time()
                        connection.execute("SELECT 1").fetchone()
                        end_time = time.time()
                        return {'query_time': end_time - start_time}
                elif 'api_url' in system:
                    # Check API performance
                    import requests
                    start_time = time.time()
                    response = requests.get(f"{system['api_url']}/status", timeout=5)
                    end_time = time.time()
                    return {'response_time': end_time - start_time, 'status_code': response.status_code}
                elif 'path' in system:
                    # Check file system performance
                    directory = Path(system['path'])
                    start_time = time.time()
                    list(directory.glob('*'))
                    end_time = time.time()
                    return {'listing_time': end_time - start_time}
            else:
                return {'error': 'System not connected'}
        except Exception as e:
            return {'error': str(e)}

    async def monitor_systems(self, interval: int = 60) -> None:
        """
        Monitor systems continuously
        """
        try:
            while True:
                status = await self.get_system_status()
                logger.info(f"System status: {status}")
                await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Error in system monitoring: {e}")