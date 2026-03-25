import logging
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class LanguageServerIntegration:
    def __init__(self, language_servers: Dict[str, str]):
        """
        Inisialisasi client untuk language server
        Args:
            language_servers: Dictionary mapping file extensions ke language server commands
        """
        self.language_servers = language_servers
        self.processes = {}

    def start_server(self, file_path: str) -> bool:
        """
        Memulai language server untuk file tertentu
        """
        try:
            ext = Path(file_path).suffix
            if ext not in self.language_servers:
                logger.warning(f"No language server configured for extension {ext}")
                return False

            command = self.language_servers[ext]
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            self.processes[file_path] = process
            return True
        except Exception as e:
            logger.error(f"Error starting language server for {file_path}: {e}")
            return False

    def stop_server(self, file_path: str) -> bool:
        """
        Menghentikan language server untuk file tertentu
        """
        try:
            if file_path in self.processes:
                self.processes[file_path].terminate()
                del self.processes[file_path]
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping language server for {file_path}: {e}")
            return False

    def analyze_file(self, file_path: str, content: str) -> Dict:
        """
        Menganalisis file menggunakan language server
        """
        try:
            # Simulasi analisis language server
            # Dalam implementasi nyata, ini akan berkomunikasi dengan language server
            ext = Path(file_path).suffix
            analysis = {
                'symbols': self._extract_symbols(content),
                'diagnostics': self._check_errors(content),
                'hover_info': self._get_hover_info(content)
            }

            if ext == '.py':
                analysis['type'] = 'python'
                analysis['features'] = ['type_inference', 'docstring_completion']
            elif ext == '.js':
                analysis['type'] = 'javascript'
                analysis['features'] = ['type_inference', 'auto_import']
            elif ext == '.ts':
                analysis['type'] = 'typescript'
                analysis['features'] = ['strict_types', 'interface_completion']

            return analysis
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return {'error': str(e)}

    def find_references(self, file_path: str, symbol: str) -> List[Dict]:
        """
        Mencari referensi symbol menggunakan language server
        """
        try:
            # Simulasi pencarian referensi
            references = [
                {'file': file_path, 'line': 10, 'column': 5, 'context': f"Reference to {symbol}"},
                {'file': file_path, 'line': 25, 'column': 8, 'context': f"Another reference to {symbol}"}
            ]
            return references
        except Exception as e:
            logger.error(f"Error finding references for {symbol}: {e}")
            return []

    def _extract_symbols(self, content: str) -> List[Dict]:
        """
        Mengekstrak symbol dari konten
        """
        symbols = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                func_name = line.split('def ')[1].split('(')[0].strip()
                symbols.append({
                    'name': func_name,
                    'type': 'function',
                    'line': i + 1,
                    'kind': 'declaration'
                })
            elif line.strip().startswith('class '):
                class_name = line.split('class ')[1].split('(')[0].strip()
                symbols.append({
                    'name': class_name,
                    'type': 'class',
                    'line': i + 1,
                    'kind': 'declaration'
                })

        return symbols

    def _check_errors(self, content: str) -> List[Dict]:
        """
        Memeriksa error sintaksis
        """
        errors = []
        lines = content.split('\n')

        # Contoh sederhana untuk deteksi error
        for i, line in enumerate(lines):
            if 'print(' in line and not line.strip().endswith(')'):
                errors.append({
                    'severity': 'error',
                    'message': 'Missing closing parenthesis',
                    'line': i + 1,
                    'column': line.find('print(') + 6
                })

        return errors

    def _get_hover_info(self, content: str) -> Dict:
        """
        Mendapatkan info hover untuk symbol
        """
        hover_info = {
            'functions': {},
            'classes': {}
        }

        lines = content.split('\n')

        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                func_name = line.split('def ')[1].split('(')[0].strip()
                hover_info['functions'][func_name] = {
                    'signature': line.strip(),
                    'description': f"Function {func_name} definition",
                    'line': i + 1
                }
            elif line.strip().startswith('class '):
                class_name = line.split('class ')[1].split('(')[0].strip()
                hover_info['classes'][class_name] = {
                    'signature': line.strip(),
                    'description': f"Class {class_name} definition",
                    'line': i + 1
                }

        return hover_info