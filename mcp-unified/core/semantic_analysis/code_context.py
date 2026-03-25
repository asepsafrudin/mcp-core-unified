from typing import Dict, List, Optional, Any
from pathlib import Path

class CodeContext:
    def __init__(self, semantic_analyzer: 'SemanticAnalyzer'):
        self.semantic_analyzer = semantic_analyzer

    def get_context(self, file_path: str, line_no: int, context_size: int = 5) -> Dict:
        """
        Mendapatkan konteks lengkap untuk suatu lokasi di kode
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            if line_no < 1 or line_no > len(lines):
                return {'error': 'Line number out of range'}

            context = {
                'current_line': lines[line_no - 1].strip(),
                'surrounding': self._get_surrounding_lines(lines, line_no, context_size),
                'semantic': self.semantic_analyzer.get_code_context(file_path, line_no),
                'symbols': self._get_symbols_in_context(lines, line_no),
                'dependencies': self._get_dependencies(file_path)
            }

            return context
        except Exception as e:
            return {'error': str(e)}

    def _get_surrounding_lines(self, lines: List[str], line_no: int, size: int) -> List[Dict]:
        """
        Mendapatkan baris-baris di sekitar line tertentu
        """
        start = max(0, line_no - size - 1)
        end = min(len(lines), line_no + size)
        surrounding = []

        for i in range(start, end):
            surrounding.append({
                'line': i + 1,
                'content': lines[i].strip(),
                'is_current': i == line_no - 1
            })

        return surrounding

    def _get_symbols_in_context(self, lines: List[str], line_no: int) -> List[Dict]:
        """
        Mendapatkan symbol-symbol yang relevan dalam konteks
        """
        symbols = []
        start = max(0, line_no - 20)
        end = min(len(lines), line_no + 20)

        for i in range(start, end):
            line = lines[i].strip()
            if line.startswith('def ') and line.endswith(':'):
                func_name = line.split('def ')[1].split('(')[0].strip()
                symbols.append({
                    'name': func_name,
                    'type': 'function',
                    'line': i + 1,
                    'kind': 'declaration',
                    'distance': abs(i - line_no + 1)
                })
            elif line.startswith('class ') and line.endswith(':'):
                class_name = line.split('class ')[1].split('(')[0].strip()
                symbols.append({
                    'name': class_name,
                    'type': 'class',
                    'line': i + 1,
                    'kind': 'declaration',
                    'distance': abs(i - line_no + 1)
                })

        return sorted(symbols, key=lambda x: x['distance'])

    def _get_dependencies(self, file_path: str) -> List[str]:
        """
        Mendapatkan dependencies dari file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            dependencies = []
            lines = content.split('\n')

            for line in lines:
                if line.strip().startswith('import '):
                    module = line.split('import ')[1].split(' ')[0].strip()
                    dependencies.append(f"import {module}")
                elif line.strip().startswith('from '):
                    parts = line.split('from ')[1].split(' import ')
                    if len(parts) > 1:
                        module = parts[0].strip()
                        dependencies.append(f"from {module} import ...")

            return dependencies
        except Exception as e:
            return []

    def get_file_structure(self, file_path: str) -> Dict:
        """
        Mendapatkan struktur file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            structure = {
                'classes': [],
                'functions': [],
                'imports': [],
                'variables': []
            }

            lines = content.split('\n')
            current_class = None

            for i, line in enumerate(lines):
                if line.strip().startswith('class '):
                    class_name = line.split('class ')[1].split('(')[0].strip()
                    structure['classes'].append({
                        'name': class_name,
                        'line': i + 1,
                        'methods': []
                    })
                    current_class = class_name
                elif line.strip().startswith('def ') and not line.strip().startswith('def __'):
                    func_name = line.split('def ')[1].split('(')[0].strip()
                    if current_class:
                        structure['classes'][-1]['methods'].append({
                            'name': func_name,
                            'line': i + 1
                        })
                    else:
                        structure['functions'].append({
                            'name': func_name,
                            'line': i + 1
                        })
                elif line.strip().startswith('import '):
                    module = line.split('import ')[1].split(' ')[0].strip()
                    structure['imports'].append({
                        'module': module,
                        'line': i + 1
                    })

            return structure
        except Exception as e:
            return {'error': str(e)}