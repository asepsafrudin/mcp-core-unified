import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import sys
import os
sys.path.insert(0, '/home/aseps/MCP/mcp-unified/core')
from advanced_features.ai_semantic_analyzer import AISemanticAnalyzer
from semantic_analysis.semantic_analyzer import SemanticAnalyzer
from semantic_analysis.language_server_integration import LanguageServerIntegration
import sys

class TestAISemanticAnalyzer(unittest.TestCase):
    def setUp(self):
        self.language_server = LanguageServerIntegration({})
        self.semantic_analyzer = SemanticAnalyzer(self.language_server)
        self.ai_analyzer = AISemanticAnalyzer(self.semantic_analyzer)

    @patch('openai.ChatCompletion.create')
    def test_analyze_with_ai(self, mock_openai):
        mock_openai.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content='{"analysis": "test"}'))])
        
        test_file = 'test_ai.py'
        with open(test_file, 'w') as f:
            f.write('def test(): pass')
        
        result = self.ai_analyzer.analyze_with_ai(test_file)
        self.assertIn('basic_analysis', result)
        self.assertIn('ai_analysis', result)
        
        os.unlink(test_file)

if __name__ == '__main__':
    unittest.main(argv=[''], exit=False)

