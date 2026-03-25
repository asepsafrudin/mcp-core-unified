import unittest
import sys
import os
from pathlib import Path

# Add semantic_analysis to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from semantic_analyzer import SemanticAnalyzer
from language_server_integration import LanguageServerIntegration

class TestStandalone(unittest.TestCase):
    def setUp(self):
        self.language_server = LanguageServerIntegration({})
        self.analyzer = SemanticAnalyzer(self.language_server)

    def test_analyze_simple_file(self):
        test_file = "standalone_test.py"
        content = '''
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
'''
        with open(test_file, 'w') as f:
            f.write(content)

        result = self.analyzer.analyze_file(test_file)
        self.assertIn('ast', result)
        self.assertEqual(result['ast']['functions'][0]['name'], 'add')
        Path(test_file).unlink()

if __name__ == '__main__':
    unittest.main(argv=[''], exit=False)

