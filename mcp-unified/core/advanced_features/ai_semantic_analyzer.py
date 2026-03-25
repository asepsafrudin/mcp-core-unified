import logging
import openai
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class AISemanticAnalyzer:
    def __init__(self, semantic_analyzer: SemanticAnalyzer, openai_api_key: str = None):
        self.semantic_analyzer = semantic_analyzer
        self.openai_api_key = openai_api_key
        self.model = "gpt-4"
        self.temperature = 0.3

        if openai_api_key:
            openai.api_key = openai_api_key

    def analyze_with_ai(self, file_path: str, context: Dict = None) -> Dict:
        """
        Menganalisis file dengan bantuan AI untuk pemahaman semantik yang lebih dalam
        """
        try:
            # Langkah 1: Analisis dasar dengan semantic analyzer
            basic_analysis = self.semantic_analyzer.analyze_file(file_path)

            # Langkah 2: Ekstrak informasi untuk AI
            file_content = Path(file_path).read_text(encoding='utf-8')
            file_info = {
                'path': file_path,
                'size': len(file_content),
                'lines': file_content.count('\n') + 1,
                'extension': Path(file_path).suffix,
                'content_preview': file_content[:1000]
            }

            # Langkah 3: Buat prompt untuk AI
            prompt = self._create_ai_prompt(basic_analysis, file_info, context)

            # Langkah 4: Panggil AI untuk analisis
            ai_response = self._call_ai(prompt)

            # Langkah 5: Gabungkan hasil
            return {
                'basic_analysis': basic_analysis,
                'ai_analysis': ai_response,
                'file_info': file_info,
                'context': context
            }
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {'error': str(e)}

    def _create_ai_prompt(self, basic_analysis: Dict, file_info: Dict, context: Dict = None) -> str:
        """
        Membuat prompt untuk AI berdasarkan analisis file
        """
        prompt = f"""
        Anda adalah ahli analisis kode yang membantu memahami kode secara semantik.

        Informasi file:
        - Path: {file_info['path']}
        - Ukuran: {file_info['size']} bytes
        - Jumlah baris: {file_info['lines']}
        - Ekstensi: {file_info['extension']}
        - Preview: {file_info['content_preview']}

        Analisis dasar:
        {self._format_basic_analysis(basic_analysis)}

        Context tambahan:
        {self._format_context(context)}

        Tugas Anda:
        Berikan analisis semantik yang mendalam tentang kode ini, termasuk:
        1. Tujuan utama dari kode
        2. Pola desain yang digunakan
        3. Potensi masalah atau improvement
        4. Hubungan antar komponen
        5. Saran untuk optimasi
        6. Kompleksitas kode
        7. Rekomendasi dokumentasi

        Jawab dengan format JSON yang terstruktur.
        """
        return prompt

    def _format_basic_analysis(self, basic_analysis: Dict) -> str:
        """
        Format analisis dasar untuk prompt AI
        """
        if 'ast' in basic_analysis:
            ast_info = basic_analysis['ast']
            return f"""
            AST Analysis:
            - Classes: {len(ast_info.get('classes', []))}
            - Functions: {len(ast_info.get('functions', []))}
            - Imports: {len(ast_info.get('imports', []))}
            - Variables: {len(ast_info.get('variables', []))}
            """
        return "AST analysis not available"

    def _format_context(self, context: Dict = None) -> str:
        """
        Format context tambahan untuk prompt AI
        """
        if not context:
            return "Tidak ada context tambahan"
        return f"Context: {context}"

    def _call_ai(self, prompt: str) -> Dict:
        """
        Memanggil API AI untuk analisis
        """
        try:
            if not self.openai_api_key:
                return {
                    'error': 'OpenAI API key not configured',
                    'suggestion': 'Please provide OpenAI API key for AI analysis'
                }

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'Anda adalah ahli analisis kode yang memberikan analisis semantik mendalam.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=2000
            )

            return {
                'ai_response': response.choices[0].message.content,
                'model': self.model,
                'temperature': self.temperature
            }
        except Exception as e:
            logger.error(f"Error calling AI API: {e}")
            return {'error': str(e)}

    def analyze_project(self, project_path: str, depth: int = 2) -> Dict:
        """
        Menganalisis seluruh proyek dengan pemahaman semantik
        """
        try:
            # Analisis file-file dalam proyek
            analysis_results = []
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.java', '.cpp']:
                    analysis = self.analyze_with_ai(str(file_path))
                    analysis_results.append(analysis)

            # Analisis tingkat proyek
            project_analysis = self._analyze_project_structure(project_path, depth)

            return {
                'project_path': project_path,
                'depth': depth,
                'file_analyses': analysis_results,
                'project_analysis': project_analysis
            }
        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            return {'error': str(e)}

    def _analyze_project_structure(self, project_path: str, depth: int) -> Dict:
        """
        Menganalisis struktur proyek
        """
        try:
            project_info = {
                'path': project_path,
                'depth': depth,
                'structure': self._get_directory_structure(project_path, depth),
                'file_counts': {},
                'language_distribution': {}
            }

            # Hitung file dan distribusi bahasa
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file():
                    ext = file_path.suffix
                    project_info['file_counts'][ext] = project_info['file_counts'].get(ext, 0) + 1
                    project_info['language_distribution'][ext] = project_info['language_distribution'].get(ext, 0) + 1

            return project_info
        except Exception as e:
            logger.error(f"Error analyzing project structure: {e}")
            return {'error': str(e)}

    def _get_directory_structure(self, path: str, depth: int, current_depth: int = 0) -> Dict:
        """
        Mendapatkan struktur direktori secara rekursif
        """
        if current_depth >= depth:
            return {}

        structure = {
            'path': path,
            'name': Path(path).name,
            'type': 'directory',
            'contents': []
        }

        try:
            for item in Path(path).iterdir():
                if item.is_dir():
                    if current_depth < depth:
                        structure['contents'].append(
                            self._get_directory_structure(str(item), depth, current_depth + 1)
                        )
                else:
                    structure['contents'].append({
                        'path': str(item),
                        'name': item.name,
                        'type': 'file',
                        'size': item.stat().st_size if item.stat().st_size else 0
                    })
        except Exception as e:
            logger.debug(f"Error reading directory {path}: {e}")

        return structure