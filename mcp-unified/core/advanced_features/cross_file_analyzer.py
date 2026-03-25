import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class CrossFileAnalyzer:
    def __init__(self, semantic_analyzer: SemanticAnalyzer):
        self.semantic_analyzer = semantic_analyzer
        self.cache = {}

    def analyze_project(self, project_path: str, depth: int = 2) -> Dict:
        """
        Menganalisis seluruh proyek untuk menemukan hubungan antar file
        """
        try:
            project_info = {
                'path': project_path,
                'depth': depth,
                'files': [],
                'dependencies': {},
                'symbol_map': {},
                'cross_references': []
            }

            # Langkah 1: Analisis semua file
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and self._is_supported_file(file_path):
                    file_analysis = self._analyze_file(file_path)
                    project_info['files'].append(file_analysis)

                    # Update symbol map
                    self._update_symbol_map(project_info['symbol_map'], file_analysis)

            # Langkah 2: Temukan dependencies
            self._find_dependencies(project_info)

            # Langkah 3: Temukan cross-references
            self._find_cross_references(project_info)

            return project_info
        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            return {'error': str(e)}

    def _is_supported_file(self, file_path: Path) -> bool:
        """
        Memeriksa apakah file didukung untuk analisis
        """
        supported_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']
        return file_path.suffix in supported_extensions

    def _analyze_file(self, file_path: Path) -> Dict:
        """
        Menganalisis file individual
        """
        try:
            # Cek cache
            cache_key = str(file_path)
            if cache_key in self.cache:
                return self.cache[cache_key]

            # Analisis file
            analysis = self.semantic_analyzer.analyze_file(str(file_path))

            # Ekstrak informasi penting
            file_info = {
                'path': str(file_path),
                'name': file_path.name,
                'extension': file_path.suffix,
                'size': file_path.stat().st_size,
                'symbols': self._extract_symbols(analysis),
                'dependencies': self._extract_dependencies(analysis),
                'functions': self._extract_functions(analysis),
                'classes': self._extract_classes(analysis)
            }

            # Simpan ke cache
            self.cache[cache_key] = file_info

            return file_info
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return {
                'path': str(file_path),
                'error': str(e)
            }

    def _extract_symbols(self, analysis: Dict) -> List[Dict]:
        """
        Mengekstrak symbol dari analisis
        """
        symbols = []
        if 'ast' in analysis:
            ast_info = analysis['ast']
            symbols.extend([
                {'name': cls['name'], 'type': 'class', 'lineno': cls['lineno']}
                for cls in ast_info.get('classes', [])
            ])
            symbols.extend([
                {'name': func['name'], 'type': 'function', 'lineno': func['lineno']}
                for func in ast_info.get('functions', [])
            ])
        return symbols

    def _extract_dependencies(self, analysis: Dict) -> List[str]:
        """
        Mengekstrak dependencies dari analisis
        """
        dependencies = []
        if 'ast' in analysis:
            for imp in analysis['ast'].get('imports', []):
                if 'module' in imp:
                    dependencies.append(imp['module'])
                else:
                    for name in imp['names']:
                        dependencies.append(name['name'])
        return dependencies

    def _extract_functions(self, analysis: Dict) -> List[Dict]:
        """
        Mengekstrak functions dari analisis
        """
        functions = []
        if 'ast' in analysis:
            for func in analysis['ast'].get('functions', []):
                functions.append({
                    'name': func['name'],
                    'lineno': func['lineno'],
                    'args': func.get('args', [])
                })
        return functions

    def _extract_classes(self, analysis: Dict) -> List[Dict]:
        """
        Mengekstrak classes dari analisis
        """
        classes = []
        if 'ast' in analysis:
            for cls in analysis['ast'].get('classes', []):
                classes.append({
                    'name': cls['name'],
                    'lineno': cls['lineno'],
                    'methods': cls.get('methods', 0)
                })
        return classes

    def _update_symbol_map(self, symbol_map: Dict, file_info: Dict):
        """
        Update symbol map dengan informasi dari file
        """
        for symbol in file_info.get('symbols', []):
            symbol_name = symbol['name']
            if symbol_name not in symbol_map:
                symbol_map[symbol_name] = []
            symbol_map[symbol_name].append({
                'file': file_info['path'],
                'type': symbol['type'],
                'lineno': symbol['lineno']
            })

    def _find_dependencies(self, project_info: Dict):
        """
        Temukan dependencies antar file
        """
        for file_info in project_info['files']:
            for dependency in file_info.get('dependencies', []):
                # Cari file yang menyediakan dependency ini
                for other_file in project_info['files']:
                    if other_file['path'] != file_info['path']:
                        for symbol in other_file.get('symbols', []):
                            if symbol['name'] == dependency:
                                # Ditemukan dependency
                                if file_info['path'] not in project_info['dependencies']:
                                    project_info['dependencies'][file_info['path']] = []
                                project_info['dependencies'][file_info['path']].append({
                                    'type': 'import',
                                    'symbol': dependency,
                                    'from': other_file['path'],
                                    'lineno': symbol['lineno']
                                })

    def _find_cross_references(self, project_info: Dict):
        """
        Temukan cross-references antar file
        """
        for symbol_name, symbol_locations in project_info['symbol_map'].items():
            if len(symbol_locations) > 1:
                # Symbol ini digunakan di multiple file
                for i, location in enumerate(symbol_locations):
                    for other_location in symbol_locations[i+1:]:
                        # Tambahkan cross-reference
                        if location['file'] not in project_info['cross_references']:
                            project_info['cross_references'][location['file']] = []
                        project_info['cross_references'][location['file']].append({
                            'type': 'cross_reference',
                            'symbol': symbol_name,
                            'to': other_location['file'],
                            'lineno': location['lineno']
                        })

    def find_symbol_uses(self, project_path: str, symbol: str) -> List[Dict]:
        """
        Mencari penggunaan symbol di seluruh proyek
        """
        try:
            results = []
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and self._is_supported_file(file_path):
                    analysis = self._analyze_file(file_path)
                    for func in analysis.get('functions', []):
                        if symbol in func['name']:
                            results.append({
                                'file': str(file_path),
                                'symbol': func['name'],
                                'type': 'function',
                                'lineno': func['lineno']
                            })
                    for cls in analysis.get('classes', []):
                        if symbol in cls['name']:
                            results.append({
                                'file': str(file_path),
                                'symbol': cls['name'],
                                'type': 'class',
                                'lineno': cls['lineno']
                            })
            return results
        except Exception as e:
            logger.error(f"Error finding symbol uses: {e}")
            return []

    def get_project_metrics(self, project_info: Dict) -> Dict:
        """
        Mendapatkan metrics untuk proyek
        """
        try:
            metrics = {
                'total_files': len(project_info['files']),
                'total_symbols': len(project_info['symbol_map']),
                'dependencies': len(project_info.get('dependencies', {})),
                'cross_references': len(project_info.get('cross_references', {})),
                'language_distribution': {}
            }

            # Hitung distribusi bahasa
            for file_info in project_info['files']:
                ext = file_info['extension']
                metrics['language_distribution'][ext] = metrics['language_distribution'].get(ext, 0) + 1

            return metrics
        except Exception as e:
            logger.error(f"Error getting project metrics: {e}")
            return {'error': str(e)}

    def visualize_dependencies(self, project_info: Dict) -> Dict:
        """
        Visualisasi dependencies proyek
        """
        try:
            graph = {
                'nodes': [],
                'edges': []
            }

            # Tambahkan nodes
            for file_info in project_info['files']:
                graph['nodes'].append({
                    'id': file_info['path'],
                    'label': file_info['name'],
                    'size': file_info['size'],
                    'type': 'file'
                })

            # Tambahkan edges untuk dependencies
            for file_path, deps in project_info.get('dependencies', {}).items():
                for dep in deps:
                    graph['edges'].append({
                        'source': file_path,
                        'target': dep['from'],
                        'type': dep['type'],
                        'symbol': dep['symbol']
                    })

            # Tambahkan edges untuk cross-references
            for file_path, refs in project_info.get('cross_references', {}).items():
                for ref in refs:
                    graph['edges'].append({
                        'source': file_path,
                        'target': ref['to'],
                        'type': ref['type'],
                        'symbol': ref['symbol']
                    })

            return graph
        except Exception as e:
            logger.error(f"Error visualizing dependencies: {e}")
            return {'error': str(e)}