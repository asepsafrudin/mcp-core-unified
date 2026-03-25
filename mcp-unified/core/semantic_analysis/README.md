# Semantic Analysis Tools for MCP Unified

Semantic analysis tools yang dirancang untuk memberikan pemahaman kode semantik yang mendalam untuk MCP Unified Server.

## Fitur Utama

- **Semantic Code Analysis**: Analisis struktur kode menggunakan AST dan language server
- **Context-Aware Understanding**: Pemahaman konteks kode berdasarkan lokasi dan hubungan
- **Multi-Language Support**: Dukungan untuk Python, JavaScript, TypeScript, dan bahasa lainnya
- **Symbol Resolution**: Resolusi symbol dan pencarian referensi
- **Code Context Extraction**: Ekstraksi konteks kode untuk pengambilan keputusan

## Instalasi

### Menggunakan pip
```bash
pip install mcp-unified-semantic-analysis
```

### Dari source
```bash
git clone https://github.com/mcp-unified/semantic-analysis.git
cd semantic-analysis
pip install -e .
```

## Quick Start

### Basic Usage
```python
from mcp_unified.core.semantic_analysis import SemanticAnalyzer, LanguageServerClient

# Inisialisasi language server client
language_servers = {
    '.py': 'python3 -m pyls',
    '.js': 'javascript-language-server',
    '.ts': 'typescript-language-server'
}
lsc = LanguageServerClient(language_servers)

# Buat semantic analyzer
analyzer = SemanticAnalyzer(lsc)

# Analisis file
result = analyzer.analyze_file('example.py')
print(result['ast'])
```

### CLI Usage
```bash
semantic-analyzer analyze example.py
semantic-analyzer context example.py:10
semantic-analyzer find example.py greet
```

## API Reference

### SemanticAnalyzer
- `analyze_file(file_path)`: Menganalisis file untuk mendapatkan informasi semantik
- `find_references(file_path, symbol)`: Mencari referensi symbol
- `get_code_context(file_path, line_no)`: Mendapatkan konteks kode

### LanguageServerClient
- `start_server(file_path)`: Memulai language server
- `stop_server(file_path)`: Menghentikan language server
- `analyze_file(file_path, content)`: Menganalisis file menggunakan language server

## Supported Languages

- **Python**: Full support dengan pyls (Python Language Server)
- **JavaScript**: Support dengan javascript-language-server
- **TypeScript**: Support dengan typescript-language-server
- **JSON**: Basic support
- **HTML/CSS**: Basic support

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
black .
flake8 .
mypy .
```

## Performance

Semantic analysis tools dirancang untuk:
- **Fast Analysis**: Caching dan optimasi untuk file besar
- **Memory Efficient**: Penggunaan memori yang optimal
- **Scalable**: Dapat menangani proyek besar dengan ribuan file

## Integration

Tools ini dapat diintegrasikan dengan:
- **MCP Unified Server**: Sebagai module untuk semantic understanding
- **IDE Extensions**: Untuk fitur semantic-aware
- **Code Review Tools**: Untuk analisis otomatis
- **Documentation Generators**: Untuk dokumentasi berbasis kode

## License

MIT License - Lihat file LICENSE untuk detail lengkap.