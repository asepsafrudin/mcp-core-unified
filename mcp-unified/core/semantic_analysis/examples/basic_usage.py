import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from semantic_analysis.semantic_analyzer import SemanticAnalyzer
from semantic_analysis.language_server_integration import LanguageServerIntegration as LanguageServerClient

def main():
    print("=== Semantic Analysis Tools Example ===")

    # Konfigurasi language server
    language_servers = {
        '.py': 'python3 -m pyls',
        '.js': 'javascript-language-server',
        '.ts': 'typescript-language-server'
    }

    # Inisialisasi language server client
    lsc = LanguageServerClient(language_servers)

    # Buat semantic analyzer
    analyzer = SemanticAnalyzer(lsc)

    # File contoh untuk analisis
    example_file = 'example.py'
    content = """
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y

# Contoh penggunaan
result = add(2, 3)
calc = Calculator()
product = calc.multiply(4, 5)
    """

    # Simpan file contoh
    with open(example_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n1. Analyzing file: {example_file}")
    analysis_result = analyzer.analyze_file(example_file)
    print(f"   - AST nodes: {len(analysis_result['ast']['functions'])} functions, {len(analysis_result['ast']['classes'])} classes")
    print(f"   - LSP features: {', '.join(analysis_result.get('lsp', {}).get('features', []))}")

    print(f"\n2. Finding references to 'add'")
    references = analyzer.find_references(example_file, 'add')
    print(f"   - Found {len(references)} references")

    print(f"\n3. Getting code context at line 2")
    context = analyzer.get_code_context(example_file, 2)
    print(f"   - Current line: {context.get('current_line')}")
    print(f"   - Function: {context.get('function')}")
    print(f"   - Class: {context.get('class')}")

    print(f"\n4. Getting file structure")
    from semantic_analysis.code_context import CodeContext
    code_context = CodeContext(analyzer)
    structure = code_context.get_file_structure(example_file)
    print(f"   - Functions: {[f['name'] for f in structure['functions']]}")
    print(f"   - Classes: {[c['name'] for c in structure['classes']]}")

    # Cleanup
    import os
    os.remove(example_file)
    print("\n=== Example completed successfully ===")

if __name__ == '__main__':
    main()