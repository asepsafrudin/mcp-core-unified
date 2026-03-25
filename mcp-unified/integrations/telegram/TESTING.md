# 🧪 Testing Guide

Dokumen ini menjelaskan cara melakukan testing pada struktur Telegram yang baru.

## 📋 Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
```

## 🚀 Menjalankan Tests

### 1. Syntax Check
```bash
cd mcp-unified/integrations/telegram
python tests/run_tests.py --syntax
```

### 2. Unit Tests
```bash
# Basic test run
python tests/run_tests.py

# Verbose output
python tests/run_tests.py -v

# Dengan coverage report
python tests/run_tests.py --coverage
```

### 3. Direct pytest
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config.py -v

# Run dengan coverage
pytest tests/ --cov=integrations.telegram --cov-report=html
```

## 📊 Test Coverage Areas

| Module | Test File | Coverage |
|--------|-----------|----------|
| Config | `test_config.py` | Settings, validation, enums |
| Services | `test_services.py` | Messaging, memory, AI |
| Core | `test_core.py` | Protocol, client, responses |
| Handlers | *(TODO)* | Command, message handlers |
| Middleware | *(TODO)* | Auth, logging, rate limit |
| Workers | *(TODO)* | Base worker, queue |

## 🔧 Test Fixtures

File `conftest.py` menyediakan:
- `mock_config`: Mock TelegramConfig untuk testing
- `mock_mcp_client`: Mock MCP client dengan semua methods

## 📝 Menambah Tests Baru

```python
# tests/test_new_module.py
import pytest
from ..services.new_service import NewService

class TestNewService:
    def test_feature(self):
        service = NewService()
        result = service.do_something()
        assert result == expected
```

## 🎯 Testing Checklist

- [ ] Semua Python files pass syntax check
- [ ] Unit tests pass (config, services, core)
- [ ] Integration tests dengan mock MCP client
- [ ] Coverage > 80%

## 🐛 Troubleshooting

### Import Errors
```bash
# Pastikan path benar
export PYTHONPATH="${PYTHONPATH}:$(pwd)/mcp-unified"
```

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Async Test Errors
```bash
# pytest-asyncio sudah di conftest.py
# Gunakan @pytest.mark.asyncio decorator
```
