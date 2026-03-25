"""
Vulnerability Scanner for MCP Unified System.

Performs security scans on codebase, dependencies, and configuration.
"""

import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import subprocess


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Category(str, Enum):
    SECRET = "secret"
    INJECTION = "injection"
    CONFIG = "config"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    INPUT_VALIDATION = "input_validation"


@dataclass
class Vulnerability:
    """Represents a security vulnerability."""
    id: str
    title: str
    description: str
    severity: str
    category: str
    file_path: str
    line_number: int
    code_snippet: str
    remediation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None


class SecurityScanner:
    """
    Security vulnerability scanner.
    
    Scans for:
    - Hardcoded secrets
    - SQL injection
    - Command injection
    - Path traversal
    - Insecure configurations
    - Dependency vulnerabilities
    """
    
    # Secret patterns
    SECRET_PATTERNS = [
        (r'password\s*=\s*["\'][^"\']{4,}["\']', "Hardcoded password", Severity.HIGH),
        (r'secret\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret", Severity.CRITICAL),
        (r'api_key\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded API key", Severity.CRITICAL),
        (r'token\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded token", Severity.CRITICAL),
        (r'private_key\s*=\s*["\'][^"\']{20,}["\']', "Hardcoded private key", Severity.CRITICAL),
        (r'aws_access_key_id\s*=\s*["\'][^"\']{16,20}["\']', "AWS Access Key", Severity.CRITICAL),
        (r'aws_secret_access_key\s*=\s*["\'][^"\']{40}["\']', "AWS Secret Key", Severity.CRITICAL),
        (r'Bearer\s+[a-zA-Z0-9_\-\.]+', "Bearer token in code", Severity.HIGH),
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        (r'execute\s*\(\s*["\'].*%s.*["\']', "Potential SQL injection (string formatting)", Severity.HIGH),
        (r'execute\s*\(\s*["\'].*\+.*["\']', "Potential SQL injection (concatenation)", Severity.HIGH),
        (r'execute\s*\(\s*f["\']', "Potential SQL injection (f-string)", Severity.HIGH),
        (r'\.format\s*\(.*\).*execute', "Potential SQL injection (.format)", Severity.MEDIUM),
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        (r'os\.system\s*\(', "Dangerous os.system call", Severity.HIGH),
        (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', "Subprocess with shell=True", Severity.HIGH),
        (r'subprocess\.Popen\s*\([^)]*shell\s*=\s*True', "Popen with shell=True", Severity.HIGH),
        (r'eval\s*\(', "Dangerous eval() call", Severity.CRITICAL),
        (r'exec\s*\(', "Dangerous exec() call", Severity.CRITICAL),
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        (r'open\s*\(\s*.*\+', "Potential path traversal", Severity.MEDIUM),
        (r'\.\./', "Path traversal pattern", Severity.MEDIUM),
        (r'\.\.\\', "Path traversal pattern (Windows)", Severity.MEDIUM),
    ]
    
    # Insecure config patterns
    INSECURE_CONFIG_PATTERNS = [
        (r'debug\s*=\s*True', "Debug mode enabled", Severity.HIGH),
        (r'DEBUG\s*=\s*True', "Debug mode enabled", Severity.HIGH),
        (r'verify\s*=\s*False', "SSL verification disabled", Severity.HIGH),
        (r'validate_cert\s*=\s*False', "Certificate validation disabled", Severity.HIGH),
        (r'allow_origin\s*=\s*["\']*["\']', "Overly permissive CORS", Severity.MEDIUM),
        (r'allow_origin\s*=\s*["\']\*["\']', "Wildcard CORS allowed", Severity.MEDIUM),
    ]
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.vulnerabilities: List[Vulnerability] = []
        self.scanned_files = 0
    
    def scan_file(self, file_path: Path) -> List[Vulnerability]:
        """Scan a single file for vulnerabilities."""
        vulnerabilities = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception:
            return vulnerabilities
        
        # Scan each pattern category
        all_patterns = [
            (self.SECRET_PATTERNS, Category.SECRET),
            (self.SQL_INJECTION_PATTERNS, Category.INJECTION),
            (self.COMMAND_INJECTION_PATTERNS, Category.INJECTION),
            (self.PATH_TRAVERSAL_PATTERNS, Category.INPUT_VALIDATION),
            (self.INSECURE_CONFIG_PATTERNS, Category.CONFIG),
        ]
        
        for patterns, category in all_patterns:
            for pattern, description, severity in patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    code_snippet = lines[line_num - 1].strip()[:100]
                    
                    vuln = Vulnerability(
                        id=f"VULN-{len(vulnerabilities) + 1:04d}",
                        title=description,
                        description=f"Potential security issue: {description}",
                        severity=severity.value,
                        category=category.value,
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=code_snippet,
                        remediation=self._get_remediation(category, description)
                    )
                    vulnerabilities.append(vuln)
        
        # AST-based analysis for Python files
        if file_path.suffix == '.py':
            vulnerabilities.extend(self._ast_analysis(file_path, content))
        
        self.scanned_files += 1
        return vulnerabilities
    
    def _ast_analysis(self, file_path: Path, content: str) -> List[Vulnerability]:
        """Perform AST-based analysis."""
        vulnerabilities = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return vulnerabilities
        
        for node in ast.walk(tree):
            # Check for dangerous functions
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec']:
                        vuln = Vulnerability(
                            id=f"VULN-{len(vulnerabilities) + 1:04d}",
                            title=f"Dangerous {node.func.id}() call",
                            description=f"Use of {node.func.id}() is dangerous and should be avoided",
                            severity=Severity.CRITICAL.value,
                            category=Category.INJECTION.value,
                            file_path=str(file_path),
                            line_number=getattr(node, 'lineno', 0),
                            code_snippet=content.split('\n')[getattr(node, 'lineno', 1) - 1].strip()[:100],
                            remediation=f"Avoid using {node.func.id}(). Use safer alternatives like ast.literal_eval()"
                        )
                        vulnerabilities.append(vuln)
            
            # Check for hardcoded strings that might be secrets
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if len(node.value) > 20 and self._looks_like_secret(node.value):
                    vuln = Vulnerability(
                        id=f"VULN-{len(vulnerabilities) + 1:04d}",
                        title="Potential hardcoded secret",
                        description="String looks like a hardcoded secret or key",
                        severity=Severity.MEDIUM.value,
                        category=Category.SECRET.value,
                        file_path=str(file_path),
                        line_number=getattr(node, 'lineno', 0),
                        code_snippet=content.split('\n')[getattr(node, 'lineno', 1) - 1].strip()[:100],
                        remediation="Move secrets to environment variables or secret management"
                    )
                    vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def _looks_like_secret(self, value: str) -> bool:
        """Check if a string looks like a secret."""
        # Check for common secret patterns
        secret_indicators = [
            r'^[A-Za-z0-9_\-]{20,}$',  # Long alphanumeric
            r'^[A-Fa-f0-9]{32,}$',      # Hex string
            r'^[A-Za-z0-9+/]{20,}={0,2}$',  # Base64-like
            r'sk_live_',                # Stripe live key
            r'rk_live_',                # Stripe restricted key
            r'ghp_',                    # GitHub personal token
        ]
        
        for pattern in secret_indicators:
            if re.match(pattern, value):
                return True
        return False
    
    def _get_remediation(self, category: Category, description: str) -> str:
        """Get remediation advice based on category."""
        remediations = {
            Category.SECRET: "Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS Secrets Manager.",
            Category.INJECTION: "Use parameterized queries, input validation, and avoid dynamic code execution.",
            Category.INPUT_VALIDATION: "Validate and sanitize all user inputs. Use allowlists for file paths.",
            Category.CONFIG: "Review configuration for production readiness. Disable debug mode and enable SSL verification.",
            Category.PERMISSION: "Implement principle of least privilege. Review file permissions.",
        }
        return remediations.get(category, "Review and fix the security issue.")
    
    def scan_directory(self, path: Optional[str] = None) -> List[Vulnerability]:
        """Scan entire directory for vulnerabilities."""
        scan_path = Path(path) if path else self.base_path
        
        # Files to skip
        skip_patterns = [
            r'__pycache__',
            r'\.pyc$',
            r'\.git',
            r'node_modules',
            r'venv',
            r'\.env',
            r'\.venv',
            r'dist',
            r'build',
            r'\.pytest_cache',
        ]
        
        for root, dirs, files in os.walk(scan_path):
            # Skip directories matching patterns
            dirs[:] = [d for d in dirs if not any(re.search(p, d) for p in skip_patterns)]
            
            for file in files:
                file_path = Path(root) / file
                
                # Skip files matching patterns
                if any(re.search(p, str(file_path)) for p in skip_patterns):
                    continue
                
                # Scan Python and config files
                if file_path.suffix in ['.py', '.json', '.yaml', '.yml', '.env', '.sh']:
                    self.vulnerabilities.extend(self.scan_file(file_path))
        
        return self.vulnerabilities
    
    def scan_dependencies(self) -> List[Vulnerability]:
        """Scan dependencies for known vulnerabilities."""
        vulnerabilities = []
        
        # Check requirements.txt
        req_file = self.base_path / "requirements.txt"
        if req_file.exists():
            try:
                # Run safety check if available
                result = subprocess.run(
                    ["safety", "check", "--file", str(req_file), "--json"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    # Parse safety output
                    try:
                        data = json.loads(result.stdout)
                        for vuln in data.get("vulnerabilities", []):
                            vulnerabilities.append(Vulnerability(
                                id=f"DEP-{vuln.get('vulnerability_id', '0000')}",
                                title=f"Vulnerable dependency: {vuln.get('package_name')}",
                                description=vuln.get('vulnerable_spec', ''),
                                severity=Severity.HIGH.value,
                                category=Category.DEPENDENCY.value,
                                file_path="requirements.txt",
                                line_number=0,
                                code_snippet=f"{vuln.get('package_name')} {vuln.get('vulnerable_spec')}",
                                remediation=f"Upgrade to {vuln.get('analyzed_spec', 'latest version')}"
                            ))
                    except json.JSONDecodeError:
                        pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # safety not installed, skip
                pass
        
        return vulnerabilities
    
    def generate_report(self) -> Dict:
        """Generate scan report."""
        # Count by severity
        severity_counts = {s.value: 0 for s in Severity}
        for vuln in self.vulnerabilities:
            severity_counts[vuln.severity] = severity_counts.get(vuln.severity, 0) + 1
        
        # Count by category
        category_counts = {}
        for vuln in self.vulnerabilities:
            category_counts[vuln.category] = category_counts.get(vuln.category, 0) + 1
        
        return {
            "scan_summary": {
                "total_files_scanned": self.scanned_files,
                "total_vulnerabilities": len(self.vulnerabilities),
                "severity_breakdown": severity_counts,
                "category_breakdown": category_counts,
                "scan_timestamp": str(json.dumps("datetime.utcnow().isoformat()")),
            },
            "vulnerabilities": [asdict(v) for v in self.vulnerabilities]
        }
    
    def print_report(self):
        """Print scan report to console."""
        report = self.generate_report()
        summary = report["scan_summary"]
        
        print("=" * 80)
        print("SECURITY SCAN REPORT")
        print("=" * 80)
        print(f"\nFiles Scanned: {summary['total_files_scanned']}")
        print(f"Total Vulnerabilities: {summary['total_vulnerabilities']}")
        
        print("\nSeverity Breakdown:")
        for severity, count in summary['severity_breakdown'].items():
            if count > 0:
                icon = "🔴" if severity in ["CRITICAL", "HIGH"] else "🟡" if severity == "MEDIUM" else "🟢"
                print(f"  {icon} {severity}: {count}")
        
        print("\nCategory Breakdown:")
        for category, count in summary['category_breakdown'].items():
            print(f"  • {category}: {count}")
        
        if self.vulnerabilities:
            print("\n" + "=" * 80)
            print("VULNERABILITIES DETAIL")
            print("=" * 80)
            
            # Sort by severity
            severity_order = {s.value: i for i, s in enumerate(Severity)}
            sorted_vulns = sorted(
                self.vulnerabilities,
                key=lambda v: severity_order.get(v.severity, 99)
            )
            
            for vuln in sorted_vulns[:20]:  # Show top 20
                icon = "🔴" if vuln.severity in ["CRITICAL", "HIGH"] else "🟡" if vuln.severity == "MEDIUM" else "🟢"
                print(f"\n{icon} [{vuln.severity}] {vuln.title}")
                print(f"   File: {vuln.file_path}:{vuln.line_number}")
                print(f"   Category: {vuln.category}")
                print(f"   Code: {vuln.code_snippet[:80]}...")
                print(f"   Fix: {vuln.remediation[:100]}...")
        
        print("\n" + "=" * 80)


# CLI entry point
if __name__ == "__main__":
    import sys
    
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    print(f"🔍 Starting security scan of: {path}")
    print("=" * 80)
    
    scanner = SecurityScanner(path)
    scanner.scan_directory()
    
    # Also scan dependencies if safety is available
    try:
        import subprocess
        subprocess.run(["safety", "--version"], capture_output=True, check=True)
        print("📦 Scanning dependencies...")
        scanner.vulnerabilities.extend(scanner.scan_dependencies())
    except:
        print("⚠️  'safety' not installed. Skipping dependency scan.")
        print("   Install with: pip install safety")
    
    scanner.print_report()
    
    # Exit with error code if critical/high vulnerabilities found
    critical_high = sum(1 for v in scanner.vulnerabilities if v.severity in ["CRITICAL", "HIGH"])
    sys.exit(1 if critical_high > 0 else 0)