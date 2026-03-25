# Integration Guide: Semantic Analysis Tools dengan MCP Unified Server

Panduan ini menjelaskan cara mengintegrasikan Semantic Analysis Tools dengan MCP Unified Server.

## Prasyarat

- MCP Unified Server sudah terinstall dan berjalan
- Python 3.8+
- Akses ke package manager (pip)

## Langkah Instalasi

### 1. Install Semantic Analysis Tools
```bash
cd mcp-unified/core/semantic_analysis
pip install -e .
```

### 2. Konfigurasi MCP Unified Server
Edit file `mcp-unified/core/config.py` untuk menambahkan semantic analysis tools:

```python
# Tambahkan di bagian tool registry
from mcp_unified.core.semantic_analysis import SemanticAnalyzer

TOOL_REGISTRY = {
    'semantic_analyze': {
        'class': SemanticAnalyzer,
        'description': 'Analyze code with semantic understanding',
        'arguments': {
            'file_path': str,
            'content': str
        }
    },
    'find_references': {
        'class': SemanticAnalyzer,
        'description': 'Find symbol references in code',
        'arguments': {
            'file_path': str,
            'symbol': str
        }
    },
    'get_code_context': {
        'class': SemanticAnalyzer,
        'description': 'Get context around code location',
        'arguments': {
            'file_path': str,
            'line_no': int
        }
    }
}
```

### 3. Update MCP Server Configuration
Edit file `mcp-unified/mcp_server.py` untuk menambahkan semantic analysis capabilities:

```python
from mcp_unified.core.semantic_analysis import SemanticAnalyzer, LanguageServerClient

class MCPServer:
    def __init__(self):
        # Inisialisasi language server client
        self.lsc = LanguageServerClient({
            '.py': 'python3 -m pyls',
            '.js': 'javascript-language-server',
            '.ts': 'typescript-language-server'
        })
        
        # Buat semantic analyzer
        self.semantic_analyzer = SemanticAnalyzer(self.lsc)
```

## Usage Examples

### Melalui MCP Client
```bash
# Analisis file
mcp semantic_analyze --file example.py

# Cari referensi
mcp find_references --file example.py --symbol add

# Dapatkan konteks
mcp get_code_context --file example.py --line 10
```

### Melalui API
```python
import requests

# Analisis file
response = requests.post('http://localhost:8000/tools/call', json={
    'name': 'semantic_analyze',
    'arguments': {
        'file_path': 'example.py',
        'content': open('example.py').read()
    }
})

# Cari referensi
response = requests.post('http://localhost:8000/tools/call', json={
    'name': 'find_references',
    'arguments': {
        'file_path': 'example.py',
        'symbol': 'add'
    }
})
```

## Performance Considerations

### Caching
Semantic analysis tools menggunakan caching untuk:
- AST parsing results
- Language server responses
- Symbol resolution

### Memory Management
- Memory pool untuk AST objects
- Garbage collection untuk unused objects
- Configurable cache size

### Concurrency
- Thread-safe operations
- Async support untuk language server communication
- Rate limiting untuk API calls

## Troubleshooting

### Language Server Issues
- Pastikan language server terinstall
- Periksa PATH environment variable
- Verifikasi file permissions

### Performance Issues
- Kurangi context size untuk large files
- Gunakan caching options
- Monitor memory usage

### Integration Issues
- Periksa tool registry configuration
- Verifikasi MCP server status
- Cek network connectivity

## Testing Integration

### Unit Tests
```bash
cd mcp-unified/core/semantic_analysis
pytest tests/ -v
```

### Integration Tests
```bash
# Jalankan MCP server
cd mcp-unified
./run.sh

# Jalankan integration tests
cd core/semantic_analysis
pytest tests/test_integration.py
```

## Monitoring dan Logging

### Metrics
- Analysis time per file
- Cache hit rate
- Memory usage
- Error rates

### Logging
- Structured logging untuk debugging
- Performance metrics collection
- Error tracking dan alerting

## Best Practices

1. **Use Caching**: Enable caching untuk performance
2. **Handle Errors Gracefully**: Implement error handling untuk language server failures
3. **Monitor Performance**: Track analysis times dan memory usage
4. **Test Thoroughly**: Gunakan integration tests untuk verifikasi
5. **Document Usage**: Berikan contoh penggunaan yang jelas

## Future Enhancements

- **AI-Powered Analysis**: Integration dengan LLM untuk semantic understanding
- **Real-time Collaboration**: Support untuk collaborative editing
- **Advanced Refactoring**: Tools untuk code refactoring
- **Cross-file Analysis**: Analysis antar file dan proyek

## Support

Untuk bantuan lebih lanjut:
- Lihat dokumentasi lengkap di `docs/`
- Cek FAQ di README.md
- Laporkan issues di GitHub repository