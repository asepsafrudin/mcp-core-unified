import logging
import openai
from typing import Dict, List, Optional, Any
from pathlib import Path
from core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class AdvancedAI:
    def __init__(self, semantic_analyzer: SemanticAnalyzer, openai_api_key: str = None):
        self.semantic_analyzer = semantic_analyzer
        self.openai_api_key = openai_api_key
        self.model = "gpt-4"
        self.temperature = 0.1
        self.max_tokens = 4000

        if openai_api_key:
            openai.api_key = openai_api_key

    def analyze_with_advanced_ai(self, file_path: str, context: Dict = None) -> Dict:
        """
        Menganalisis file dengan advanced AI untuk pemahaman semantik yang sangat mendalam
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
                'content_preview': file_content[:2000],
                'full_content': file_content
            }

            # Langkah 3: Buat prompt untuk AI
            prompt = self._create_advanced_ai_prompt(basic_analysis, file_info, context)

            # Langkah 4: Panggil AI untuk analisis
            ai_response = self._call_advanced_ai(prompt)

            # Langkah 5: Gabungkan hasil
            return {
                'basic_analysis': basic_analysis,
                'ai_analysis': ai_response,
                'file_info': file_info,
                'context': context
            }
        except Exception as e:
            logger.error(f"Error in advanced AI analysis: {e}")
            return {'error': str(e)}

    def _create_advanced_ai_prompt(self, basic_analysis: Dict, file_info: Dict, context: Dict = None) -> str:
        """
        Membuat prompt untuk advanced AI berdasarkan analisis file
        """
        prompt = f"""
        Anda adalah ahli analisis kode tingkat lanjut dengan kemampuan pemahaman semantik yang sangat mendalam.

        Informasi file:
        - Path: {file_info['path']}
        - Ukuran: {file_info['size']} bytes
        - Jumlah baris: {file_info['lines']}
        - Ekstensi: {file_info['extension']}
        - Preview: {file_info['content_preview'][:500]}

        Analisis dasar:
        {self._format_basic_analysis(basic_analysis)}

        Context tambahan:
        {self._format_context(context)}

        Tugas Anda:
        Berikan analisis semantik yang sangat mendalam tentang kode ini, termasuk:
        1. Tujuan utama dan secondary purposes dari kode
        2. Pola desain yang digunakan (design patterns)
        3. Arsitektur dan struktur kode
        4. Potensi masalah atau improvement dengan justifikasi
        5. Hubungan antar komponen dan dependencies
        6. Saran untuk optimasi dengan trade-off analysis
        7. Kompleksitas kode (cyclomatic complexity, cognitive complexity)
        8. Rekomendasi dokumentasi dan testing
        9. Potensi security vulnerabilities
        10. Performance bottlenecks dan optimasi
        11. Maintainability assessment
        12. Scalability considerations
        13. Best practices compliance
        14. Code smells dan anti-patterns
        15. Refactoring opportunities dengan prioritas

        Jawab dengan format JSON yang sangat terstruktur dan detail.
        """
        return prompt

    def _format_basic_analysis(self, basic_analysis: Dict) -> str:
        """
        Format analisis dasar untuk prompt advanced AI
        """
        if 'ast' in basic_analysis:
            ast_info = basic_analysis['ast']
            return f"""
            AST Analysis:
            - Classes: {len(ast_info.get('classes', []))}
            - Functions: {len(ast_info.get('functions', []))}
            - Imports: {len(ast_info.get('imports', []))}
            - Variables: {len(ast_info.get('variables', []))}

            Functions Details:
            {self._format_functions_details(ast_info.get('functions', []))}

            Classes Details:
            {self._format_classes_details(ast_info.get('classes', []))}
            """
        return "AST analysis not available"

    def _format_functions_details(self, functions: List[Dict]) -> str:
        """
        Format details functions untuk prompt
        """
        if not functions:
            return "No functions found"

        details = []
        for func in functions:
            details.append(f"- {func['name']}(): {len(func.get('args', []))} args")
        return "\n".join(details)

    def _format_classes_details(self, classes: List[Dict]) -> str:
        """
        Format details classes untuk prompt
        """
        if not classes:
            return "No classes found"

        details = []
        for cls in classes:
            details.append(f"- {cls['name']}(): {cls.get('methods', 0)} methods")
        return "\n".join(details)

    def _call_advanced_ai(self, prompt: str) -> Dict:
        """
        Memanggil API AI untuk analisis advanced
        """
        try:
            if not self.openai_api_key:
                return {
                    'error': 'OpenAI API key not configured',
                    'suggestion': 'Please provide OpenAI API key for advanced AI analysis'
                }

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'Anda adalah ahli analisis kode tingkat lanjut yang memberikan analisis semantik sangat mendalam.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return {
                'ai_response': response.choices[0].message.content,
                'model': self.model,
                'temperature': self.temperature,
                'max_tokens': self.max_tokens
            }
        except Exception as e:
            logger.error(f"Error calling advanced AI API: {e}")
            return {'error': str(e)}

    def analyze_project_with_ai(self, project_path: str, depth: int = 3) -> Dict:
        """
        Menganalisis seluruh proyek dengan advanced AI
        """
        try:
            # Analisis file-file dalam proyek
            analysis_results = []
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and self._is_supported_file(file_path):
                    analysis = self.analyze_with_advanced_ai(str(file_path))
                    analysis_results.append(analysis)

            # Analisis tingkat proyek
            project_analysis = self._analyze_project_structure(project_path, depth)

            # Generate project insights
            project_insights = self._generate_project_insights(analysis_results, project_analysis)

            return {
                'project_path': project_path,
                'depth': depth,
                'file_analyses': analysis_results,
                'project_analysis': project_analysis,
                'project_insights': project_insights
            }
        except Exception as e:
            logger.error(f"Error analyzing project with AI: {e}")
            return {'error': str(e)}

    def _generate_project_insights(self, analysis_results: List[Dict], project_analysis: Dict) -> Dict:
        """
        Generate insights untuk seluruh proyek
        """
        try:
            insights = {
                'architecture_assessment': {},
                'code_quality': {},
                'security_assessment': {},
                'performance_assessment': {},
                'maintainability': {},
                'recommendations': []
            }

            # Architecture assessment
            insights['architecture_assessment'] = {
                'design_patterns_used': self._detect_design_patterns(analysis_results),
                'architecture_style': self._detect_architecture_style(project_analysis),
                'modularity': self._assess_modularity(analysis_results)
            }

            # Code quality
            insights['code_quality'] = {
                'complexity_metrics': self._calculate_complexity_metrics(analysis_results),
                'code_smells': self._detect_code_smells(analysis_results),
                'test_coverage_suggestion': self._suggest_test_coverage(analysis_results)
            }

            # Security assessment
            insights['security_assessment'] = {
                'vulnerabilities': self._detect_security_vulnerabilities(analysis_results),
                'best_practices': self._check_security_best_practices(analysis_results)
            }

            # Performance assessment
            insights['performance_assessment'] = {
                'bottlenecks': self._detect_performance_bottlenecks(analysis_results),
                'optimization_opportunities': self._find_optimization_opportunities(analysis_results)
            }

            # Maintainability
            insights['maintainability'] = {
                'readability_score': self._calculate_readability_score(analysis_results),
                'documentation_quality': self._assess_documentation_quality(analysis_results)
            }

            # Generate recommendations
            insights['recommendations'] = self._generate_recommendations(analysis_results)

            return insights
        except Exception as e:
            logger.error(f"Error generating project insights: {e}")
            return {'error': str(e)}

    def _detect_design_patterns(self, analysis_results: List[Dict]) -> List[str]:
        """
        Detect design patterns yang digunakan
        """
        patterns = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'design_patterns' in ai_response:
                        patterns.extend(ai_response['design_patterns'])
                except Exception:
                    pass
        return list(set(patterns))

    def _detect_architecture_style(self, project_analysis: Dict) -> str:
        """
        Detect architecture style
        """
        # Simple heuristic berdasarkan file structure
        if 'structure' in project_analysis:
            structure = project_analysis['structure']
            if 'src' in structure and 'tests' in structure:
                return 'Modular MVC'
            elif 'api' in structure and 'models' in structure:
                return 'RESTful API'
            else:
                return 'Monolithic'
        return 'Unknown'

    def _assess_modularity(self, analysis_results: List[Dict]) -> Dict:
        """
        Assess modularity of project
        """
        modules = {}
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'modularity' in ai_response:
                        modules[analysis['file_info']['path']] = ai_response['modularity']
                except Exception:
                    pass
        return modules

    def _calculate_complexity_metrics(self, analysis_results: List[Dict]) -> Dict:
        """
        Calculate complexity metrics
        """
        metrics = {
            'avg_cyclomatic_complexity': 0,
            'avg_cognitive_complexity': 0,
            'high_complexity_files': []
        }

        complexities = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'complexity_metrics' in ai_response:
                        complexities.append(ai_response['complexity_metrics'])
                except Exception:
                    pass

        if complexities:
            metrics['avg_cyclomatic_complexity'] = sum(c['cyclomatic_complexity'] for c in complexities) / len(complexities)
            metrics['avg_cognitive_complexity'] = sum(c['cognitive_complexity'] for c in complexities) / len(complexities)
            metrics['high_complexity_files'] = [c for c in complexities if c['cyclomatic_complexity'] > 10]

        return metrics

    def _detect_code_smells(self, analysis_results: List[Dict]) -> List[str]:
        """
        Detect code smells
        """
        smells = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'code_smells' in ai_response:
                        smells.extend(ai_response['code_smells'])
                except Exception:
                    pass
        return list(set(smells))

    def _suggest_test_coverage(self, analysis_results: List[Dict]) -> Dict:
        """
        Suggest test coverage
        """
        suggestions = {}
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'test_coverage_suggestions' in ai_response:
                        suggestions[analysis['file_info']['path']] = ai_response['test_coverage_suggestions']
                except Exception:
                    pass
        return suggestions

    def _detect_security_vulnerabilities(self, analysis_results: List[Dict]) -> List[str]:
        """
        Detect security vulnerabilities
        """
        vulnerabilities = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'security_vulnerabilities' in ai_response:
                        vulnerabilities.extend(ai_response['security_vulnerabilities'])
                except Exception:
                    pass
        return list(set(vulnerabilities))

    def _check_security_best_practices(self, analysis_results: List[Dict]) -> Dict:
        """
        Check security best practices
        """
        best_practices = {}
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'security_best_practices' in ai_response:
                        best_practices[analysis['file_info']['path']] = ai_response['security_best_practices']
                except Exception:
                    pass
        return best_practices

    def _detect_performance_bottlenecks(self, analysis_results: List[Dict]) -> List[str]:
        """
        Detect performance bottlenecks
        """
        bottlenecks = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'performance_bottlenecks' in ai_response:
                        bottlenecks.extend(ai_response['performance_bottlenecks'])
                except Exception:
                    pass
        return list(set(bottlenecks))

    def _find_optimization_opportunities(self, analysis_results: List[Dict]) -> List[str]:
        """
        Find optimization opportunities
        """
        opportunities = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'optimization_opportunities' in ai_response:
                        opportunities.extend(ai_response['optimization_opportunities'])
                except Exception:
                    pass
        return list(set(opportunities))

    def _calculate_readability_score(self, analysis_results: List[Dict]) -> float:
        """
        Calculate readability score
        """
        scores = []
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'readability_score' in ai_response:
                        scores.append(ai_response['readability_score'])
                except Exception:
                    pass
        return sum(scores) / len(scores) if scores else 0.0

    def _assess_documentation_quality(self, analysis_results: List[Dict]) -> Dict:
        """
        Assess documentation quality
        """
        quality = {}
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'documentation_quality' in ai_response:
                        quality[analysis['file_info']['path']] = ai_response['documentation_quality']
                except Exception:
                    pass
        return quality

    def _generate_recommendations(self, analysis_results: List[Dict]) -> List[Dict]:
        """
        Generate recommendations
        """
        recommendations = []

        # Priority 1: Critical issues
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'critical_recommendations' in ai_response:
                        recommendations.extend(ai_response['critical_recommendations'])
                except Exception:
                    pass

        # Priority 2: High impact improvements
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'high_impact_recommendations' in ai_response:
                        recommendations.extend(ai_response['high_impact_recommendations'])
                except Exception:
                    pass

        # Priority 3: General improvements
        for analysis in analysis_results:
            if 'ai_analysis' in analysis:
                try:
                    ai_response = analysis['ai_analysis']
                    if 'general_recommendations' in ai_response:
                        recommendations.extend(ai_response['general_recommendations'])
                except Exception:
                    pass

        return recommendations