# Development Guide: Semantic Analysis Tools

Panduan lengkap untuk development Semantic Analysis Tools.

## Environment Setup

### 1. Create Virtual Environment
```bash
cd mcp-unified/core/semantic_analysis
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# atau
.venv\Scripts\activate     # Windows
```

### 2. Install Dependencies
```bash
make install
# atau
pip install -r requirements.txt
pip install -e .
```

### 3. Install Development Tools
```bash
pip install pre-commit
pre-commit install
```

## Development Workflow

### 1. Code Quality
Sebelum commit, jalankan:
```bash
make lint
make format
```

### 2. Testing
```bash
make test
# atau
pytest tests/ -v
```

### 3. Running Examples
```bash
make examples
# atau
python examples/basic_usage.py
```

### 4. Integration Testing
```bash
make integration
```

## Project Structure

```
semantic_analysis/
├── core/                 # Core logic
│   ├── semantic_analyzer.py
│   ├── language_server_integration.py
│   └── code_context.py
├── tests/               # Test suite
│   ├── test_semantic_analysis.py
│   ├── test_examples.py
│   └── test_integration.py
├── examples/            # Usage examples
│   └── basic_usage.py
├── docs/               # Documentation
│   └── integration_guide.md
├── scripts/            # Development scripts
│   └── run_tests.sh
├── Makefile           # Development commands
├── requirements.txt   # Dependencies
├── setup.py          # Package configuration
└── README.md         # Project documentation
```

## Code Style Guidelines

### Python
- Gunakan **black** untuk formatting
- Gunakan **flake8** untuk linting
- Gunakan **mypy** untuk type checking
- Maksimum line length: 88 characters

### Documentation
- Gunakan Google Style docstring
- Dokumentasikan semua public functions dan classes
- Sertakan type hints

### Testing
- Gunakan pytest untuk testing
- Coverage minimum 90%
- Gunakan fixtures untuk setup/teardown

## Architecture Overview

### SemanticAnalyzer
- **Responsibility**: Core semantic analysis logic
- **Components**: AST parsing, symbol resolution, context extraction
- **Dependencies**: LanguageServerClient

### LanguageServerClient
- **Responsibility**: Communication dengan language servers
- **Components**: Process management, request handling
- **Dependencies**: External language servers

### CodeContext
- **Responsibility**: Context extraction dan file structure
- **Components**: Surrounding lines, symbol analysis, dependencies
- **Dependencies**: SemanticAnalyzer

## Performance Optimization

### Caching Strategy
- **AST Cache**: Cache hasil parsing untuk file yang sama
- **Symbol Cache**: Cache resolusi symbol
- **Language Server Cache**: Cache responses dari language server

### Memory Management
- **Object Pooling**: Reuse objects untuk mengurangi GC pressure
- **Lazy Loading**: Load data hanya saat dibutuhkan
- **Configurable Limits**: Batasi ukuran cache dan memory usage

## Debugging Tips

### Common Issues
1. **Language Server Not Found**
   - Periksa PATH environment variable
   - Install language server yang diperlukan
   - Verifikasi file permissions

2. **Performance Issues**
   - Kurangi context size
   - Enable caching
   - Monitor memory usage

3. **Integration Issues**
   - Periksa tool registry configuration
   - Verifikasi MCP server status
   - Cek network connectivity

### Debugging Tools
```bash
# Debug dengan pdb
python -m pdb examples/basic_usage.py

# Debug dengan logging
export LOG_LEVEL=DEBUG
python examples/basic_usage.py

# Performance profiling
python -m cProfile -o profile.prof examples/basic_usage.py
```

## Contributing

### Before Submitting
1. Jalankan `make lint`
2. Jalankan `make test`
3. Jalankan `make format`
4. Update documentation jika perlu

### Code Review Checklist
- [ ] Code follows style guidelines
- [ ] Tests cover new functionality
- [ ] Documentation updated
- [ ] Performance considerations addressed
- [ ] Error handling implemented

## Release Process

### 1. Update Version
Edit `setup.py` dan update version number

### 2. Update Changelog
Tambahkan perubahan di CHANGELOG.md

### 3. Run Tests
```bash
make test
make integration
```

### 4. Build Package
```bash
python setup.py sdist bdist_wheel
```

### 5. Publish
```bash
twine upload dist/*
```

## Resources

- **Language Server Protocol**: https://microsoft.github.io/language-server-protocol/
- **Python AST**: https://docs.python.org/3/library/ast.html
- **pytest**: https://docs.pytest.org/
- **black**: https://black.readthedocs.io/
- **mypy**: https://mypy.readthedocs.io/

## Support

Untuk bantuan development:
- Cek FAQ di README.md
- Buka issues di GitHub repository
- Join development community