import unittest
from pathlib import Path
import sys
import os

# Add the parent directory to the path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from semantic_analysis.semantic_analyzer import SemanticAnalyzer
from semantic_analysis.language_server_integration import LanguageServerIntegration

class TestSemanticAnalysis(unittest.TestCase):
    def setUp(self):
        self.language_server = LanguageServerIntegration({})
        self.analyzer = SemanticAnalyzer(self.language_server)

    def test_analyze_simple_file(self):
        test_file = "test_file.py"
        content = """
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
        """

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)

        result = self.analyzer.analyze_file(test_file)
        self.assertIn('ast', result)
        self.assertIn('lsp', result)
        self.assertEqual(result['ast']['functions'][0]['name'], 'add')
        self.assertEqual(result['ast']['classes'][0]['name'], 'Calculator')

        Path(test_file).unlink()

    def test_find_references(self):
        test_file = "test_references.py"
        content = """
def greet(name):
    return f"Hello, {name}!"

def welcome():
    return greet("Guest")
        """

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)

        references = self.analyzer.find_references(test_file, 'greet')
        self.assertGreater(len(references), 0)

        Path(test_file).unlink()

    def test_get_code_context(self):
        test_file = "test_context.py"
        content = """
def process_data(data):
    result = data * 2
    return result
        """

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)

        context = self.analyzer.get_code_context(test_file, 2)
        self.assertIn('current_line', context)
        self.assertIn('surrounding', context)

        Path(test_file).unlink()

    def test_code_context_class(self):
        test_file = "test_class.py"
        content = """
class User:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hi, I'm {self.name}"
        """

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)

        context = self.analyzer.get_code_context(test_file, 4)
        self.assertIn('function', context)
        self.assertIn('class', context)

        Path(test_file).unlink()

if __name__ == '__main__':
    unittest.main()