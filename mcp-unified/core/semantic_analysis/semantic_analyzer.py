import ast
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from .language_server_integration import LanguageServerIntegration

logger = logging.getLogger(__name__)

class SemanticAnalyzer:
    def __init__(self, language_server: LanguageServerIntegration):
        self.language_server = language_server

    def analyze_file(self, file_path: str) -> Dict:
        """
        Menganalisis file untuk mendapatkan informasi semantik
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Parse AST untuk analisis struktur
            tree = ast.parse(content)
            semantic_info = self._extract_semantic_info(tree)

            # Dapatkan informasi tambahan dari language server
            lsp_info = self.language_server.analyze_file(file_path, content)

            return {
                'ast': semantic_info,
                'lsp': lsp_info,
                'file_info': {
                    'path': file_path,
                    'size': len(content),
                    'lines': content.count('\n') + 1
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return {'error': str(e)}

    def _extract_semantic_info(self, tree: ast.AST) -> Dict:
        """
        Mengekstrak informasi semantik dari AST
        """
        semantic_info = {
            'classes': [],
            'functions': [],
            'imports': [],
            'variables': []
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                semantic_info['classes'].append({
                    'name': node.name,
                    'lineno': node.lineno,
                    'col_offset': node.col_offset,
                    'methods': len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                })
            elif isinstance(node, ast.FunctionDef):
                semantic_info['functions'].append({
                    'name': node.name,
                    'lineno': node.lineno,
                    'col_offset': node.col_offset,
                    'args': [arg.arg for arg in node.args.args]
                })
            elif isinstance(node, ast.Import):
                semantic_info['imports'].append({
                    'names': [alias.name for alias in node.names],
                    'lineno': node.lineno
                })
            elif isinstance(node, ast.ImportFrom):
                semantic_info['imports'].append({
                    'module': node.module,
                    'names': [alias.name for alias in node.names],
                    'lineno': node.lineno
                })

        return semantic_info

    def find_references(self, file_path: str, symbol: str) -> List[Dict]:
        """
        Mencari referensi symbol dalam file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Gunakan language server untuk pencarian yang lebih akurat
            return self.language_server.find_references(file_path, symbol)
        except Exception as e:
            logger.error(f"Error finding references for {symbol}: {e}")
            return []

    def get_code_context(self, file_path: str, line_no: int) -> Dict:
        """
        Mendapatkan konteks kode di sekitar line tertentu
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            context = {
                'current_line': lines[line_no - 1].strip() if line_no <= len(lines) else None,
                'surrounding': lines[max(0, line_no - 5):min(len(lines), line_no + 5)],
                'function': self._get_enclosing_function(lines, line_no),
                'class': self._get_enclosing_class(lines, line_no)
            }

            return context
        except Exception as e:
            logger.error(f"Error getting code context: {e}")
            return {'error': str(e)}

    def _get_enclosing_function(self, lines: List[str], line_no: int) -> Optional[str]:
        """
        Mendapatkan fungsi yang membungkus line tertentu
        """
        for i in range(line_no - 1, max(0, line_no - 10), -1):
            line = lines[i].strip()
            if line.startswith('def ') and line.endswith(':'):
                return line[4:-1].split('(')[0].strip()
        return None

    def _get_enclosing_class(self, lines: List[str], line_no: int) -> Optional[str]:
        """
        Mendapatkan class yang membungkus line tertentu
        """
        for i in range(line_no - 1, max(0, line_no - 20), -1):
            line = lines[i].strip()
            if line.startswith('class ') and line.endswith(':'):
                return line[6:-1].split('(')[0].strip()
        return None