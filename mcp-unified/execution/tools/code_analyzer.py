#!/usr/bin/env python3
"""
ML Code Quality Analyzer - MCP Unified Version
Menganalisis risiko kode berdasarkan metrik kompleksitas

Adopted from: /home/aseps/Projects/tools/ml_analyzer.py
Integrated into MCP Unified execution tools for self-review capabilities.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """Risk level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CodeMetrics:
    """Code metrics data class"""
    complexity: int
    loc: int
    dependencies: int
    functions: int
    classes: int
    max_function_length: int


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    risk_score: float
    risk_level: RiskLevel
    status: str
    recommendation: str
    breakdown: Dict[str, float]
    metrics: CodeMetrics


class CodeQualityAnalyzer:
    """
    ML-based Code Quality Analyzer for MCP Unified
    
    Provides:
    - Complexity analysis
    - Risk scoring
    - Refactoring recommendations
    - Batch analysis for projects
    """
    
    # Thresholds based on industry best practices
    THRESHOLDS = {
        'complexity': 30,
        'loc': 200,
        'dependencies': 10,
        'function_length': 50
    }
    
    def __init__(self, custom_thresholds: Optional[Dict] = None):
        """
        Initialize analyzer with optional custom thresholds
        
        Args:
            custom_thresholds: Override default thresholds
        """
        self.thresholds = {**self.THRESHOLDS, **(custom_thresholds or {})}
    
    def analyze_file(self, filepath: str) -> RiskAssessment:
        """
        Analyze a single Python file
        
        Args:
            filepath: Path to Python file
            
        Returns:
            RiskAssessment with scores and recommendations
        """
        metrics = self._count_metrics(filepath)
        return self._calculate_risk(metrics)
    
    def analyze_code(self, code: str, filename: str = "<string>") -> RiskAssessment:
        """
        Analyze code string directly
        
        Args:
            code: Python code string
            filename: Optional filename for reference
            
        Returns:
            RiskAssessment
        """
        metrics = self._count_metrics_from_source(code, filename)
        return self._calculate_risk(metrics)
    
    def analyze_project(self, project_path: str, 
                       exclude_patterns: Optional[List[str]] = None) -> Dict[str, RiskAssessment]:
        """
        Analyze entire project directory
        
        Args:
            project_path: Root path of project
            exclude_patterns: List of patterns to exclude (e.g., ['venv', '__pycache__'])
            
        Returns:
            Dictionary mapping file paths to RiskAssessments
        """
        exclude = exclude_patterns or ['venv', '__pycache__', '.git', 'node_modules', '.pytest_cache']
        results = {}
        
        for root, dirs, files in os.walk(project_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude and not d.startswith('.')]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        results[filepath] = self.analyze_file(filepath)
                    except Exception as e:
                        results[filepath] = RiskAssessment(
                            risk_score=0.0,
                            risk_level=RiskLevel.HIGH,
                            status="ERROR",
                            recommendation=f"Failed to analyze: {str(e)}",
                            breakdown={},
                            metrics=CodeMetrics(0, 0, 0, 0, 0, 0)
                        )
        
        return results
    
    def _count_metrics(self, filepath: str) -> CodeMetrics:
        """Count metrics from Python file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        return self._count_metrics_from_source(source, filepath)
    
    def _count_metrics_from_source(self, source: str, filename: str = "<string>") -> CodeMetrics:
        """Count metrics from source code string"""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise SyntaxError(f"Syntax error in {filename}: {e}")
        
        lines = source.split('\n')
        
        # Count LoC (excluding empty lines and comments)
        loc = 0
        in_multiline_string = False
        for line in lines:
            stripped = line.strip()
            
            # Handle multiline strings
            if '"""' in stripped or "'''" in stripped:
                quote_count = stripped.count('"""') + stripped.count("'''")
                if quote_count % 2 == 1:
                    in_multiline_string = not in_multiline_string
                    continue
            
            if in_multiline_string:
                continue
                
            # Skip empty lines and single-line comments
            if not stripped or stripped.startswith('#'):
                continue
                
            loc += 1
        
        # Count dependencies (imports)
        dependencies = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                dependencies += 1
        
        # Count complexity indicators
        complexity = 0
        functions = 0
        classes = 0
        max_function_length = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions += 1
                func_length = len(node.body)
                max_function_length = max(max_function_length, func_length)
                complexity += 1  # Base cost for function
            elif isinstance(node, ast.ClassDef):
                classes += 1
                complexity += 1
            elif isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.With):
                complexity += 1
        
        return CodeMetrics(
            complexity=complexity,
            loc=loc,
            dependencies=dependencies,
            functions=functions,
            classes=classes,
            max_function_length=max_function_length
        )
    
    def _calculate_risk(self, metrics: CodeMetrics) -> RiskAssessment:
        """Calculate risk score from metrics"""
        # Normalize metrics (0-1 scale)
        complexity_score = min(metrics.complexity / self.thresholds['complexity'], 1.0)
        loc_score = min(metrics.loc / self.thresholds['loc'], 1.0)
        dep_score = min(metrics.dependencies / self.thresholds['dependencies'], 1.0)
        func_length_score = min(metrics.max_function_length / self.thresholds['function_length'], 1.0)
        
        # Weighted average (complexity most important)
        risk_score = (
            complexity_score * 0.4 + 
            loc_score * 0.3 + 
            dep_score * 0.15 +
            func_length_score * 0.15
        )
        risk_score = round(risk_score, 3)
        
        # Determine risk level and status
        if risk_score > 0.8:
            risk_level = RiskLevel.CRITICAL
            status = "REJECT"
            recommendation = (
                "🚨 CRITICAL: Kode terlalu kompleks dan berisiko tinggi. "
                "Refactor segera: pecah menjadi modul terpisah, kurangi kompleksitas fungsi, "
                "dan pertimbangkan redesign arsitektur."
            )
        elif risk_score > 0.6:
            risk_level = RiskLevel.HIGH
            status = "REJECT"
            recommendation = (
                "⚠️ HIGH RISK: Kode perlu refactoring. "
                "Pecah fungsi panjang, kurangi dependencies, dan tingkatkan test coverage."
            )
        elif risk_score > 0.4:
            risk_level = RiskLevel.MEDIUM
            status = "WARNING"
            recommendation = (
                "⚡ MEDIUM RISK: Kode masih acceptable tapi bisa ditingkatkan. "
                "Pertimbangkan refactoring untuk maintainability jangka panjang."
            )
        else:
            risk_level = RiskLevel.LOW
            status = "PASS"
            recommendation = (
                "✅ LOW RISK: Kode dalam kondisi baik. "
                "Pertahankan kualitas ini dengan test coverage yang baik."
            )
        
        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            status=status,
            recommendation=recommendation,
            breakdown={
                "complexity_contribution": round(complexity_score * 0.4, 3),
                "loc_contribution": round(loc_score * 0.3, 3),
                "dep_contribution": round(dep_score * 0.15, 3),
                "function_length_contribution": round(func_length_score * 0.15, 3)
            },
            metrics=metrics
        )
    
    def generate_report(self, assessment: RiskAssessment, filepath: str = "") -> str:
        """Generate formatted report string"""
        lines = [
            "=" * 60,
            "📊 MCP CODE QUALITY AUDIT REPORT",
            "=" * 60,
        ]
        
        if filepath:
            lines.extend([
                f"📁 File: {filepath}",
                "-" * 60
            ])
        
        lines.extend([
            f"| {'Metrik':<25} | {'Nilai':<15} | {'Threshold':<10} |",
            f"|{'-'*27}|{'-'*17}|{'-'*12}|",
            f"| {'Complexity':<25} | {assessment.metrics.complexity:<15} | {self.thresholds['complexity']:<10} |",
            f"| {'Lines of Code':<25} | {assessment.metrics.loc:<15} | {self.thresholds['loc']:<10} |",
            f"| {'Dependencies':<25} | {assessment.metrics.dependencies:<15} | {self.thresholds['dependencies']:<10} |",
            f"| {'Functions':<25} | {assessment.metrics.functions:<15} | {'-':<10} |",
            f"| {'Classes':<25} | {assessment.metrics.classes:<15} | {'-':<10} |",
            f"| {'Max Function Length':<25} | {assessment.metrics.max_function_length:<15} | {self.thresholds['function_length']:<10} |",
            "-" * 60,
            f"| {'ML Risk Score':<25} | {assessment.risk_score:<15.3f} | {'0.0-1.0':<10} |",
            f"| {'Risk Level':<25} | {assessment.risk_level.value.upper():<15} | {'-':<10} |",
            f"| {'Status':<25} | {assessment.status:<15} | {'-':<10} |",
            "=" * 60,
            "",
            f"📝 Rekomendasi:")
        
        # Word wrap recommendation
        words = assessment.recommendation.split()
        line = "   "
        for word in words:
            if len(line) + len(word) + 1 > 57:
                lines.append(line)
                line = "   " + word
            else:
                line += " " + word
        lines.append(line)
        
        lines.extend([
            "",
            "📈 Risk Breakdown:",
            f"   • Complexity:    {assessment.breakdown.get('complexity_contribution', 0):.1%}",
            f"   • Lines of Code: {assessment.breakdown.get('loc_contribution', 0):.1%}",
            f"   • Dependencies:  {assessment.breakdown.get('dep_contribution', 0):.1%}",
            f"   • Function Len:  {assessment.breakdown.get('function_length_contribution', 0):.1%}",
            ""
        ])
        
        return "\n".join(lines)


# Singleton instance for quick access
_default_analyzer = None

def get_analyzer() -> CodeQualityAnalyzer:
    """Get default analyzer instance"""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = CodeQualityAnalyzer()
    return _default_analyzer


def analyze_file(filepath: str) -> RiskAssessment:
    """Quick analyze file using default analyzer"""
    return get_analyzer().analyze_file(filepath)


def analyze_code(code: str, filename: str = "<string>") -> RiskAssessment:
    """Quick analyze code string"""
    return get_analyzer().analyze_code(code, filename)


def analyze_project(project_path: str, 
                   exclude_patterns: Optional[List[str]] = None) -> Dict[str, RiskAssessment]:
    """Quick analyze project"""
    return get_analyzer().analyze_project(project_path, exclude_patterns)


if __name__ == "__main__":
    import sys
    
    analyzer = CodeQualityAnalyzer()
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path):
            # Analyze single file
            print(f"🔍 Analyzing file: {path}\n")
            assessment = analyzer.analyze_file(path)
            print(analyzer.generate_report(assessment, path))
        elif os.path.isdir(path):
            # Analyze project
            print(f"🔍 Analyzing project: {path}\n")
            results = analyzer.analyze_project(path)
            
            high_risk = sum(1 for r in results.values() if r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL))
            medium_risk = sum(1 for r in results.values() if r.risk_level == RiskLevel.MEDIUM)
            low_risk = sum(1 for r in results.values() if r.risk_level == RiskLevel.LOW)
            
            print(f"📊 Project Analysis Summary")
            print("=" * 60)
            print(f"Total Files: {len(results)}")
            print(f"🔴 High/Critical Risk: {high_risk}")
            print(f"🟡 Medium Risk: {medium_risk}")
            print(f"🟢 Low Risk: {low_risk}")
            print("=" * 60)
            print()
            
            # Show high risk files
            if high_risk > 0:
                print("🔴 High Risk Files:")
                for filepath, assessment in results.items():
                    if assessment.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                        print(f"   • {filepath} (Score: {assessment.risk_score:.3f})")
                print()
            
            # Detailed reports for high risk files
            for filepath, assessment in results.items():
                if assessment.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    print(analyzer.generate_report(assessment, filepath))
                    print()
    else:
        # Demo with sample code
        sample_code = '''
def complex_function(data):
    result = []
    for item in data:
        if item > 0:
            if item % 2 == 0:
                result.append(item * 2)
            else:
                result.append(item * 3)
        elif item < 0:
            if item % 2 == 0:
                result.append(item / 2)
            else:
                result.append(item / 3)
        else:
            result.append(0)
    return result
'''
        print("🔍 Demo Analysis:\n")
        assessment = analyzer.analyze_code(sample_code, "demo.py")
        print(analyzer.generate_report(assessment, "demo.py"))