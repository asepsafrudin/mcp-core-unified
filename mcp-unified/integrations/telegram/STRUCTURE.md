# 📁 Struktur Profesional Telegram Integration

Dokumen ini menjelaskan struktur folder dan file yang profesional untuk integrasi Telegram dengan MCP.

## 🏗️ Struktur Folder

```
mcp-unified/integrations/telegram/
├── __init__.py                    # Package initialization & exports
├── bot.py                         # Main TelegramBot class
├── run.py                         # Entry point script
│
├── config/                        # ⚙️ Configuration Module
│   ├── __init__.py
│   ├── settings.py               # TelegramConfig, AIConfig, dll
│   └── constants.py              # Enums & constants
│
├── core/                          # 🔌 MCP Protocol Integration (MCP Compliance)
│   ├── __init__.py
│   ├── protocol.py               # MCPProtocol abstract class
│   └── client.py                 # MCPClientWrapper implementation
│
├── services/                      # 🧠 Business Logic Layer
│   ├── __init__.py
│   ├── ai_service.py             # AI providers (Groq, Gemini, OpenAI)
│   ├── messaging_service.py      # Message processing & chunking
│   ├── telegram_context_service.py # Konteks lokal khusus bot Telegram
│   ├── agent_bridge_memory_service.py # Bridge eksplisit ke agent/MCP
│   └── memory_service.py         # Legacy MCP/LTM/knowledge service
│
├── handlers/                      # 📨 Telegram Update Handlers
│   ├── __init__.py
│   ├── base.py                   # BaseHandler abstract class
│   ├── commands.py               # Command handlers (/start, /help)
│   ├── messages.py               # Text message handlers
│   └── media.py                  # Photo & document handlers
│
├── middleware/                    # 🛡️ Request Processing Middleware
│   ├── __init__.py
│   ├── auth.py                   # Authentication middleware
│   ├── logging.py                # Request logging middleware
│   └── rate_limit.py             # Rate limiting middleware
│
├── workers/                       # ⚡ Background Task Workers
│   ├── __init__.py
│   ├── base.py                   # BaseWorker abstract class
│   ├── message_worker.py         # Message processing worker
│   └── queue.py                  # Priority task queue
│
├── bridges/                       # 🌉 Human-in-the-Loop Bridges
│   ├── __init__.py
│   └── cline_bridge.py           # Cline integration
│
├── utils/                         # 🛠️ Utility Functions
│   ├── __init__.py
│   ├── helpers.py                # Helper functions
│   └── formatters.py             # Message formatters
│
├── .env.example                   # Environment template
├── .env                          # Environment variables (gitignored)
├── requirements.txt               # Dependencies
└── README.md                      # User documentation
```

## 📊 Aspek & Implementasi

| Aspek | Implementasi | Relevansi dengan Project |
|-------|-------------|--------------------------|
| **Modularity** | Self-contained module di `integrations/telegram/` dengan sub-modules yang jelas (config, core, services, handlers, middleware, workers, bridges, utils) | Konsisten dengan struktur data-layer abstraction yang pernah didiskusikan |
| **Scalability** | Layered architecture (services → handlers → middleware) dengan message chunking & progressive loading untuk data besar | Mendukung chunking & progressive loading untuk data besar |
| **Worker Support** | Dedicated `workers/` folder dengan BaseWorker, MessageWorker, dan TaskQueue | Sesuai SOP DevOps untuk data besar (>1MB) |
| **MCP Compliance** | Clear separation antara core protocol (`core/`) dan integration layer dengan abstract MCPProtocol class | Memudahkan maintenance dan testing |

## 🔄 Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Telegram  │────▶│  Handlers   │────▶│  Middleware │
│    User     │     │  (Update)   │     │  (Auth/Log) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Telegram  │◀────│   Workers   │◀────│   Services  │
│     API     │     │ (Chunking)  │     │(AI/Context) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │    Core     │
                                        │   (MCP)     │
                                        └─────────────┘
```

## 🎯 Key Features

### 1. Config Module (`config/`)
- **TelegramConfig**: Main configuration dengan validation
- **AIConfig**: AI provider settings (Groq, Gemini, OpenAI)
- **SecurityConfig**: User whitelist dan access control
- **WorkerConfig**: Background task settings

### 2. Core Module (`core/`)
- **MCPProtocol**: Abstract interface untuk MCP integration
- **MCPClientWrapper**: Production-ready client dengan retry logic
- **Hook system**: Extensibility melalui before/after hooks

### 3. Services Module (`services/`)
- **AIService**: Abstract base untuk AI providers
- **GroqAI/GeminiAI**: Concrete implementations
- **AIServiceManager**: Multi-provider management dengan failover
- **MessagingService**: Message chunking & formatting
- **TelegramContextService**: Konteks percakapan lokal bot Telegram
- **AgentBridgeMemoryService**: Jalur eksplisit untuk bridge ke agent/MCP
- **MemoryService**: Service legacy MCP/LTM/knowledge yang tidak lagi menjadi konteks default chat

### 4. Handlers Module (`handlers/`)
- **BaseHandler**: Common functionality untuk semua handlers
- **CommandHandlers**: Bot commands (/start, /help, dll)
- **MessageHandlers**: Text message processing dengan streaming
- **MediaHandlers**: Photo & document handling

### 5. Middleware Module (`middleware/`)
- **AuthMiddleware**: User authentication & authorization
- **LoggingMiddleware**: Request/response logging dengan metrics
- **RateLimitMiddleware**: Rate limiting per user

### 6. Workers Module (`workers/`)
- **BaseWorker**: Abstract worker dengan retry logic
- **MessageWorker**: Background message processing
- **TaskQueue**: Priority queue dengan scheduling

### 7. Bridges Module (`bridges/`)
- **ClineBridge**: Human-in-the-loop integration

### 8. Utils Module (`utils/`)
- **helpers.py**: Utility functions
- **formatters.py**: Message formatting

## 📦 Usage

```python
# Basic usage
from integrations.telegram import TelegramBot, TelegramConfig

config = TelegramConfig.from_env()
bot = TelegramBot(config)
await bot.start()

# Custom config
config = TelegramConfig(
    bot_token="your_token",
    mode=TelegramMode.POLLING,
    ai=AIConfig(provider=AIProvider.GROQ)
)
```

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Token dari @BotFather |
| `TELEGRAM_MODE` | ❌ | `polling` | `polling` atau `webhook` |
| `AI_PROVIDER` | ❌ | `groq` | `groq`, `gemini`, `openai` |
| `GROQ_API_KEY` | ⚠️ | - | Required jika pakai Groq |
| `GEMINI_API_KEY` | ⚠️ | - | Required jika pakai Gemini |
| `TELEGRAM_ALLOWED_USERS` | ❌ | - | User ID whitelist |
| `WORKER_MAX_THREADS` | ❌ | `4` | Worker thread count |

## 🧪 Testing

Struktur ini mendukung unit testing dengan mudah:

```python
# Mock MCP untuk testing
class MockMCP(MCPProtocol):
    async def process_message(self, *args, **kwargs):
        return MCPResponse.success(data={"test": True})

# Test dengan mock
bot = TelegramBot()
bot.mcp = MockMCP()
```

## 📈 Version

**Current Version**: 2.0.0

**Changelog**:
- v2.0.0: Refactor ke struktur profesional dengan modularity, scalability, worker support
- v1.0.0: Initial implementation (flat structure)
