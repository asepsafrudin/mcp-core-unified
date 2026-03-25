import logging
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
from mcp_unified.core.semantic_analysis import SemanticAnalyzer
import openai

logger = logging.getLogger(__name__)

class AdvancedAI:
    def __init__(self, semantic_analyzer: SemanticAnalyzer, openai_api_key: str):
        self.semantic_analyzer = semantic_analyzer
        self.openai_api_key = openai_api_key
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.ai_config = {
            'model': 'gpt-4',
            'max_tokens': 4000,
            'temperature': 0.7
        }

    async def analyze_with_ai(self, file_path: str) -> Dict:
        """
        Analyze file using AI with semantic analysis
        """
        try:
            # Perform semantic analysis
            semantic_result = await self.semantic_analyzer.analyze_file(file_path)

            # Generate AI prompt
            prompt = self._generate_ai_prompt(file_path, semantic_result)

            # Get AI analysis
            ai_result = await self._call_ai_analyzer(prompt)

            # Combine results
            combined_result = {
                'semantic_analysis': semantic_result,
                'ai_analysis': ai_result,
                'insights': self._generate_insights(semantic_result, ai_result)
            }

            return combined_result
        except Exception as e:
            logger.error(f"Error in analyze_with_ai: {e}")
            return {'error': str(e)}

    def _generate_ai_prompt(self, file_path: str, semantic_result: Dict) -> str:
        """
        Generate AI prompt based on semantic analysis
        """
        try:
            prompt = f"""
Analyze this code file and provide insights:

File: {file_path}
Semantic Analysis:
- Functions: {len(semantic_result.get('functions', []))}
- Classes: {len(semantic_result.get('classes', []))}
- Variables: {len(semantic_result.get('variables', []))}
- Dependencies: {len(semantic_result.get('dependencies', []))}

Key Insights:
- Main purpose: {semantic_result.get('main_purpose', 'Unknown')}
- Complexity: {semantic_result.get('complexity', 'Unknown')}
- Potential issues: {semantic_result.get('potential_issues', [])}

Please provide:
1. Code quality assessment
2. Security vulnerabilities
3. Performance issues
4. Maintainability suggestions
5. Best practices recommendations
6. Alternative implementations
7. Testing suggestions

Focus on practical, actionable insights for a developer.
"""
            return prompt
        except Exception as e:
            logger.error(f"Error generating AI prompt: {e}")
            return "Analyze this code file and provide insights."

    async def _call_ai_analyzer(self, prompt: str) -> Dict:
        """
        Call AI analyzer with OpenAI
        """
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.ai_config['model'],
                messages=[
                    {'role': 'system', 'content': 'You are a senior software engineer analyzing code quality.'},
                    {'role': 'user', 'content': prompt}
                ],
                max_tokens=self.ai_config['max_tokens'],
                temperature=self.ai_config['temperature']
            )

            return {
                'response': response.choices[0].message.content,
                'analysis_time': response.created
            }
        except Exception as e:
            logger.error(f"Error calling AI analyzer: {e}")
            return {'error': str(e)}

    async def analyze_project_with_ai(self, project_path: str) -> Dict:
        """
        Analyze entire project using AI
        """
        try:
            project_info = {
                'path': project_path,
                'total_files': 0,
                'ai_analysis': [],
                'overall_insights': [],
                'quality_score': 0
            }

            # Analyze all files in project
            file_paths = []
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and self._is_supported_file(file_path):
                    file_paths.append(str(file_path))

            project_info['total_files'] = len(file_paths)

            if file_paths:
                # Analyze files in batches
                batch_size = 5
                for i in range(0, len(file_paths), batch_size):
                    batch = file_paths[i:i + batch_size]
                    batch_results = await asyncio.gather(
                        *[self.analyze_with_ai(file_path) for file_path in batch]
                    )

                    # Collect AI analysis
                    for result in batch_results:
                        if 'error' not in result:
                            project_info['ai_analysis'].append(result)

                # Generate overall insights
                project_info['overall_insights'] = self._generate_project_insights(project_info['ai_analysis'])
                project_info['quality_score'] = self._calculate_quality_score(project_info['overall_insights'])

            return project_info
        except Exception as e:
            logger.error(f"Error analyzing project with AI: {e}")
            return {'error': str(e)}

    def _generate_project_insights(self, ai_analysis: List[Dict]) -> List[Dict]:
        """
        Generate insights for entire project
        """
        try:
            insights = []

            # Collect common issues
            issues = {}
            for analysis in ai_analysis:
                if 'ai_analysis' in analysis and 'response' in analysis['ai_analysis']:
                    response = analysis['ai_analysis']['response']
                    # Simple pattern matching for common issues
                    if 'security vulnerability' in response:
                        issues['security'] = issues.get('security', 0) + 1
                    if 'performance issue' in response:
                        issues['performance'] = issues.get('performance', 0) + 1
                    if 'code quality' in response:
                        issues['quality'] = issues.get('quality', 0) + 1

            # Generate insights
            if issues:
                for issue_type, count in issues.items():
                    insights.append({
                        'type': issue_type,
                        'severity': 'medium' if count < 5 else 'high',
                        'description': f'{count} files have {issue_type} issues',
                        'recommendation': f'Review and fix {issue_type} issues in {count} files'
                    })

            return insights
        except Exception as e:
            logger.error(f"Error generating project insights: {e}")
            return []

    def _calculate_quality_score(self, insights: List[Dict]) -> float:
        """
        Calculate overall quality score
        """
        try:
            if not insights:
                return 100.0

            # Simple scoring: 100 - (number of issues * 10)
            score = 100 - (len(insights) * 10)
            return max(0, min(100, score))
        except Exception:
            return 0.0

    async def generate_code_suggestions(self, file_path: str, context: str = '') -> Dict:
        """
        Generate code suggestions using AI
        """
        try:
            # Get current file content
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Generate AI prompt
            prompt = f"""
You are a senior software engineer. Please provide code suggestions for this file:

File: {file_path}
Context: {context}

Current code:
{content}

Please provide:
1. Code improvements
2. Performance optimizations
3. Security enhancements
4. Best practices suggestions
5. Alternative implementations
6. Testing recommendations

Focus on practical, actionable suggestions.
"""

            # Get AI suggestions
            suggestions = await self._call_ai_analyzer(prompt)

            return {
                'file': file_path,
                'suggestions': suggestions,
                'confidence': self._calculate_confidence(suggestions)
            }
        except Exception as e:
            logger.error(f"Error generating code suggestions: {e}")
            return {'error': str(e)}

    def _calculate_confidence(self, suggestions: Dict) -> float:
        """
        Calculate confidence level of suggestions
        """
        try:
            if 'error' in suggestions:
                return 0.0

            # Simple confidence calculation based on response length
            response = suggestions.get('response', '')
            if len(response) > 500:
                return 0.9
            elif len(response) > 200:
                return 0.7
            else:
                return 0.5
        except Exception:
            return 0.0

    async def refactor_code(self, file_path: str, refactoring_type: str) -> Dict:
        """
        Refactor code using AI
        """
        try:
            # Get current file content
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Generate AI prompt
            prompt = f"""
You are a senior software engineer. Please refactor this code:

File: {file_path}
Refactoring type: {refactoring_type}

Current code:
{content}

Please provide:
1. Refactored code
2. Explanation of changes
3. Benefits of refactoring
4. Potential trade-offs

Focus on clean, maintainable code.
"""

            # Get AI refactoring
            refactoring = await self._call_ai_analyzer(prompt)

            return {
                'file': file_path,
                'refactoring_type': refactoring_type,
                'refactored_code': refactoring.get('response', ''),
                'confidence': self._calculate_confidence(refactoring)
            }
        except Exception as e:
            logger.error(f"Error refactoring code: {e}")
            return {'error': str(e)}

    async def analyze_code_patterns(self, project_path: str) -> Dict:
        """
        Analyze code patterns across project
        """
        try:
            patterns = {
                'common_patterns': [],
                'anti_patterns': [],
                'best_practices': []
            }

            # Analyze all files
            file_paths = []
            for file_path in Path(project_path).rglob('*'):
                if file_path.is_file() and self._is_supported_file(file_path):
                    file_paths.append(str(file_path))

            if file_paths:
                # Analyze patterns in batches
                batch_size = 10
                for i in range(0, len(file_paths), batch_size):
                    batch = file_paths[i:i + batch_size]
                    batch_results = await asyncio.gather(
                        *[self._analyze_file_patterns(file_path) for file_path in batch]
                    )

                    # Collect patterns
                    for result in batch_results:
                        if 'error' not in result:
                            patterns['common_patterns'].extend(result.get('common_patterns', []))
                            patterns['anti_patterns'].extend(result.get('anti_patterns', []))
                            patterns['best_practices'].extend(result.get('best_practices', []))

            return patterns
        except Exception as e:
            logger.error(f"Error analyzing code patterns: {e}")
            return {'error': str(e)}

    async def _analyze_file_patterns(self, file_path: str) -> Dict:
        """
        Analyze patterns in single file
        """
        try:
            # Get file content
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Simple pattern analysis
            common_patterns = []
            anti_patterns = []
            best_practices = []

            # Check for common patterns
            if 'for' in content and 'range' in content:
                common_patterns.append('for loop with range')
            if 'with' in content and 'open' in content:
                common_patterns.append('context manager for file operations')

            # Check for anti-patterns
            if 'except:' in content:
                anti_patterns.append('bare except clause')
            if 'print(' in content and 'logging' not in content:
                anti_patterns.append('print statement instead of logging')

            # Check for best practices
            if 'async' in content and 'await' in content:
                best_practices.append('async/await usage')
            if 'def __init__' in content:
                best_practices.append('proper class initialization')

            return {
                'file': file_path,
                'common_patterns': common_patterns,
                'anti_patterns': anti_patterns,
                'best_practices': best_practices
            }
        except Exception as e:
            logger.error(f"Error analyzing file patterns: {e}")
            return {'error': str(e)}

    def _is_supported_file(self, file_path: Path) -> bool:
        """
        Check if file is supported for AI analysis
        """
        supported_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.php', '.rb']
        return file_path.suffix in supported_extensions