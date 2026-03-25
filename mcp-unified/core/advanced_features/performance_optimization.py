import logging
import asyncio
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    def __init__(self, semantic_analyzer: SemanticAnalyzer):
        self.semantic_analyzer = semantic_analyzer
        self.cache = {}
        self.metrics = {}
        self.profiling_enabled = False

    def enable_profiling(self):
        """
        Enable performance profiling
        """
        self.profiling_enabled = True
        self.metrics = {
            'analysis_times': [],
            'memory_usage': [],
            'cache_hits': 0,
            'cache_misses': 0
        }

    def disable_profiling(self):
        """
        Disable performance profiling
        """
        self.profiling_enabled = False

    def get_performance_metrics(self) -> Dict:
        """
        Get performance metrics
        """
        if not self.profiling_enabled:
            return {'error': 'Profiling not enabled'}

        return {
            'analysis_times': self.metrics['analysis_times'],
            'memory_usage': self.metrics['memory_usage'],
            'cache_stats': {
                'hits': self.metrics['cache_hits'],
                'misses': self.metrics['cache_misses'],
                'hit_rate': self.metrics['cache_hits'] / (self.metrics['cache_hits'] + self.metrics['cache_misses']) if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0
            },
            'avg_analysis_time': sum(self.metrics['analysis_times']) / len(self.metrics['analysis_times']) if self.metrics['analysis_times'] else 0,
            'avg_memory_usage': sum(self.metrics['memory_usage']) / len(self.metrics['memory_usage']) if self.metrics['memory_usage'] else 0
        }

    async def analyze_with_profiling(self, file_path: str) -> Dict:
        """
        Analyze file with performance profiling
        """
        try:
            if not self.profiling_enabled:
                return await self.semantic_analyzer.analyze_file(file_path)

            start_time = time.time()
            start_memory = self._get_memory_usage()

            # Check cache
            cache_key = file_path
            if cache_key in self.cache:
                self.metrics['cache_hits'] += 1
                return self.cache[cache_key]

            self.metrics['cache_misses'] += 1

            # Perform analysis
            result = await self.semantic_analyzer.analyze_file(file_path)

            # Measure performance
            end_time = time.time()
            end_memory = self._get_memory_usage()

            # Store metrics
            analysis_time = end_time - start_time
            memory_used = end_memory - start_memory

            self.metrics['analysis_times'].append(analysis_time)
            self.metrics['memory_usage'].append(memory_used)

            # Cache result
            self.cache[cache_key] = result

            return result
        except Exception as e:
            logger.error(f"Error in analyze_with_profiling: {e}")
            return {'error': str(e)}

    def _get_memory_usage(self) -> int:
        """
        Get current memory usage
        """
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except Exception:
            return 0

    def optimize_cache(self, max_size: int = 100) -> None:
        """
        Optimize cache by removing least recently used items
        """
        try:
            if len(self.cache) <= max_size:
                return

            # Simple LRU cache eviction
            sorted_cache = sorted(self.cache.items(), key=lambda x: x[1]['last_access'], reverse=True)
            items_to_remove = sorted_cache[max_size:]
            for item in items_to_remove:
                del self.cache[item[0]]
        except Exception as e:
            logger.error(f"Error optimizing cache: {e}")

    def clear_cache(self) -> None:
        """
        Clear entire cache
        """
        self.cache = {}

    async def batch_analyze(self, file_paths: List[str], max_concurrent: int = 5) -> List[Dict]:
        """
        Analyze multiple files with performance optimization
        """
        try:
            semaphore = asyncio.Semaphore(max_concurrent)
            tasks = []

            async def analyze_with_semaphore(file_path: str):
                async with semaphore:
                    return await self.analyze_with_profiling(file_path)

            for file_path in file_paths:
                tasks.append(analyze_with_semaphore(file_path))

            results = await asyncio.gather(*tasks)
            return results
        except Exception as e:
            logger.error(f"Error in batch_analyze: {e}")
            return []

    def get_performance_recommendations(self) -> List[Dict]:
        """
        Get performance recommendations
        """
        try:
            recommendations = []

            if self.profiling_enabled:
                metrics = self.get_performance_metrics()
                if metrics['avg_analysis_time'] > 1.0:
                    recommendations.append({
                        'type': 'performance',
                        'description': 'High average analysis time detected',
                        'suggestion': 'Consider optimizing algorithms or increasing cache size',
                        'priority': 'high'
                    })

                if metrics['cache_hit_rate'] < 0.5:
                    recommendations.append({
                        'type': 'performance',
                        'description': 'Low cache hit rate detected',
                        'suggestion': 'Consider increasing cache size or improving cache strategy',
                        'priority': 'medium'
                    })

            return recommendations
        except Exception as e:
            logger.error(f"Error getting performance recommendations: {e}")
            return []

    async def analyze_project_performance(self, project_path: str) -> Dict:
        """
        Analyze performance of entire project
        """
        try:
            project_info = {
                'path': project_path,
                'total_files': 0,
                'total_analysis_time': 0,
                'avg_analysis_time': 0,
                'memory_usage': 0,
                'performance_issues': []
            }

            # Analyze all files in project
            file_paths = []
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and self._is_supported_file(file_path):
                    file_paths.append(str(file_path))

            project_info['total_files'] = len(file_paths)

            if file_paths:
                # Analyze files in batches
                batch_size = 10
                for i in range(0, len(file_paths), batch_size):
                    batch = file_paths[i:i + batch_size]
                    batch_results = await self.batch_analyze(batch)

                    # Collect metrics
                    for result in batch_results:
                        if 'error' not in result:
                            project_info['total_analysis_time'] += result.get('analysis_time', 0)
                            project_info['memory_usage'] += result.get('memory_usage', 0)

                # Calculate averages
                project_info['avg_analysis_time'] = project_info['total_analysis_time'] / len(file_paths)
                project_info['memory_usage'] /= len(file_paths)

                # Check for performance issues
                if project_info['avg_analysis_time'] > 2.0:
                    project_info['performance_issues'].append({
                        'type': 'slow_analysis',
                        'description': 'High average analysis time',
                        'suggestion': 'Consider optimizing algorithms or using caching'
                    })

            return project_info
        except Exception as e:
            logger.error(f"Error analyzing project performance: {e}")
            return {'error': str(e)}

    def _is_supported_file(self, file_path: Path) -> bool:
        """
        Check if file is supported for analysis
        """
        supported_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']
        return file_path.suffix in supported_extensions