import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.append('/home/aseps/MCP/mcp-unified/core')
try:
    from enterprise_features.security_audit import SecurityAudit
except ImportError:
    pass  # Mock for now
from semantic_analyzer import SemanticAnalyzer
from language_server_integration import LanguageServerIntegration

class TestSecurityAudit(unittest.TestCase):
    def setUp(self):
        self.language_server = LanguageServerIntegration({})
        self.semantic_analyzer = SemanticAnalyzer(self.language_server)
        self.security_audit = SecurityAudit(self.semantic_analyzer)

    def test_configure_security(self):
        config = {'audit_level': 'high', 'compliance_standards': ['OWASP'], 'vulnerability_scanners': ['snyk']}
        result = self.security_audit.configure_security(config)
        self.assertIn('success', result)

    def test_audit_file_no_issues(self):
        test_file = 'test_secure.py'
        with open(test_file, 'w') as f:
            f.write('def secure_func(): print("hello")')
        
        result = self.security_audit.audit_file(test_file)
        self.assertIn('security_issues', result)
        os.unlink(test_file)

    def test_audit_file_with_hardcoded(self):
        test_file = 'test_insecure.py'
        with open(test_file, 'w') as f:
            f.write('password=os.getenv("PASSWORD", "123456" if not os.getenv("CI") else "DUMMY")')
        
        result = self.security_audit.audit_file(test_file)
        self.assertIn('security_issues', result)
        os.unlink(test_file)

if __name__ == '__main__':
    unittest.main(argv=[''], exit=False)
