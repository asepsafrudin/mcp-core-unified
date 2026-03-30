"""AI Providers - Groq, Gemini & Ollama (Local SQLCoder)."""
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import Groq
try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Try to import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


@dataclass
class AIResponse:
    """Standard response format for all AI providers."""
    text: str
    provider: str
    success: bool = True
    error: Optional[str] = None


class GroqAI:
    """Groq AI Client with streaming."""
    
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        if not GROQ_AVAILABLE:
            raise RuntimeError("Groq not installed. Run: pip install groq")
        self.client = AsyncGroq(api_key=api_key)
        self.model = model
        self.chat_history: Dict[int, List[Dict]] = {}
    
    def get_history(self, user_id: int) -> List[Dict]:
        if user_id not in self.chat_history:
            self.chat_history[user_id] = []
        return self.chat_history[user_id]
    
    async def generate_response(self, user_id: int, message: str, system_prompt: str = "", context: str = ""):
        """Generate non-streaming response."""
        from dataclasses import dataclass
        
        @dataclass
        class Response:
            text: str
        
        history = self.get_history(user_id)
        
        # Build system prompt
        full_system_prompt = self._build_system_prompt(context)
        if system_prompt:
            full_system_prompt = system_prompt + "\n\n" + full_system_prompt
        
        messages = [{"role": "system", "content": full_system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            stream=False
        )
        
        content = response.choices[0].message.content
        history.append({"role": "assistant", "content": content})
        
        return Response(text=content)
    
    async def generate_stream(self, user_id: int, message: str, context: str = ""):
        """Generate streaming response."""
        history = self.get_history(user_id)
        
        system_prompt = self._build_system_prompt(context)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        full_response = ""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        history.append({"role": "assistant", "content": full_response})
    
    def _build_system_prompt(self, context: str) -> str:
        prompt = """Kamu adalah Aria, asisten AI untuk MCP.

## Fokus Telegram Bot
Kamu membantu percakapan Telegram yang ringkas dan operasional.
Untuk data korespondensi, prioritaskan fitur pencarian surat, ringkasan dashboard, dan status operasional.
Jangan mengasumsikan bot chat utama punya akses default ke SQL/knowledge agent.

## Tools Tambahan
- 📄 **Office Tools** - Baca/analisis PDF, DOCX, XLSX
- 🖼️ **Vision AI** - Analisis gambar dengan AI
- 👤 **Cline Bridge** - Kirim pesan ke Cline dengan `/cline <pesan>`

## Prinsip Respon
- Bahasa Indonesia yang baik dan profesional
- Jawaban RINGKAS dan langsung ke inti
- Gunakan *bold* untuk poin penting
- Gunakan `code` untuk path/perintah
- Jika user minta akses database mendalam, arahkan bahwa itu dipisahkan ke service SQL/agent terdedikasi

## Database Schema (Singkat)
Tabel: knowledge_documents, vision_results, tasks, telegram_messages"""
        if context:
            prompt += f"\n\nContext:\n{context}"
        return prompt
    
    def reset(self, user_id: int):
        if user_id in self.chat_history:
            del self.chat_history[user_id]


class GeminiAI:
    """Gemini AI Client."""
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        if not GEMINI_AVAILABLE:
            raise RuntimeError("Gemini not installed. Run: pip install google-generativeai")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.sessions: Dict[int, Any] = {}
    
    def get_chat(self, user_id: int):
        if user_id not in self.sessions:
            self.sessions[user_id] = self.model.start_chat(history=[])
        return self.sessions[user_id]
    
    async def generate_stream(self, user_id: int, message: str, context: str = ""):
        """Generate streaming response."""
        chat = self.get_chat(user_id)
        response = await chat.send_message_async(message, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
    def reset(self, user_id: int):
        if user_id in self.sessions:
            del self.sessions[user_id]


class OllamaAI:
    """Ollama AI Client for local SQLCoder model."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "sqlcoder:7b-q4_0"):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=35)  # 35s timeout
        logger.info(f"🧠 Ollama AI initialized: {model}")
    
    async def generate_sql(self, question: str, schema: str) -> AIResponse:
        """
        Generate SQL from natural language using SQLCoder.
        
        Args:
            question: Natural language question
            schema: Database schema context
            
        Returns:
            AIResponse with SQL or error
        """
        # SQLCoder prompt template
        prompt = self._build_sqlcoder_prompt(question, schema)
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                response = await session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Low temp for SQL accuracy
                            "num_predict": 512,   # Max tokens
                        }
                    }
                )
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ollama error: {error_text}")
                    return AIResponse(
                        text="",
                        provider="ollama",
                        success=False,
                        error=f"HTTP {response.status}: {error_text[:100]}"
                    )
                
                data = await response.json()
                generated_text = data.get("response", "").strip()
                
                # Extract SQL from response
                sql = self._extract_sql(generated_text)
                
                logger.info(f"🧠 SQLCoder generated SQL: {sql[:60]}...")
                
                return AIResponse(
                    text=sql,
                    provider="ollama",
                    success=True
                )
                
        except asyncio.TimeoutError:
            logger.warning("⏱️ Ollama timeout (>35s)")
            return AIResponse(
                text="",
                provider="ollama",
                success=False,
                error="Timeout - local model too slow"
            )
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return AIResponse(
                text="",
                provider="ollama",
                success=False,
                error=str(e)[:100]
            )
    
    def _build_sqlcoder_prompt(self, question: str, schema: str) -> str:
        """Build SQLCoder prompt template."""
        return f"""### Task
Generate a SQL query to answer [QUESTION]{question}[/QUESTION]

### Database Schema
The query will run on a database with the following schema:
{schema}

### Answer
Given the database schema, here is the SQL query that answers [QUESTION]{question}[/QUESTION]
[SQL]
"""
    
    def _extract_sql(self, text: str) -> str:
        """Extract SQL from generated text."""
        # Remove [SQL] and [/SQL] tags if present
        text = text.replace("[SQL]", "").replace("[/SQL]", "").strip()
        
        # Extract SQL between ```sql and ``` if present
        import re
        sql_match = re.search(r'```sql\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        
        # Look for SELECT statement
        select_match = re.search(r'(SELECT\s+.+?)(?:;|$)', text, re.DOTALL | re.IGNORECASE)
        if select_match:
            return select_match.group(1).strip()
        
        # Return as-is if no patterns found
        return text.strip()
    
    async def check_availability(self) -> bool:
        """Check if Ollama server and model are available."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                response = await session.get(f"{self.base_url}/api/tags")
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return self.model in models or self.model.split(':')[0] in [m.split(':')[0] for m in models]
                return False
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False


class HybridSQLProvider:
    """
    Hybrid SQL Provider: Try local Ollama first, fallback to Groq/Gemini.
    
    This provider prioritizes:
    1. Privacy (local processing when possible)
    2. Speed (fallback to API if local is slow)
    3. Reliability (always return a result)
    """
    
    def __init__(self, ollama: OllamaAI, fallback_provider, fallback_type: str = "groq"):
        """
        Initialize hybrid provider.
        
        Args:
            ollama: OllamaAI instance for local SQL generation
            fallback_provider: GroqAI or GeminiAI instance for API fallback
            fallback_type: "groq" or "gemini"
        """
        self.ollama = ollama
        self.fallback = fallback_provider
        self.fallback_type = fallback_type
        self.stats = {
            "local_success": 0,
            "fallback_success": 0,
            "local_failures": 0,
            "total_requests": 0
        }
        logger.info(f"🔄 Hybrid SQL Provider initialized (fallback: {fallback_type})")
    
    async def generate_sql(self, question: str, schema: str, user_id: int = 0) -> AIResponse:
        """
        Generate SQL using hybrid approach.
        
        Flow:
        1. Try Ollama (local) with 35s timeout
        2. If fail/timeout, fallback to Groq/Gemini API
        
        Args:
            question: Natural language question
            schema: Database schema
            user_id: User ID for fallback provider
            
        Returns:
            AIResponse with SQL
        """
        self.stats["total_requests"] += 1
        
        # Step 1: Try local Ollama
        logger.info(f"🧠 Trying local SQLCoder for: {question[:50]}...")
        
        ollama_response = await self.ollama.generate_sql(question, schema)
        
        if ollama_response.success and ollama_response.text:
            logger.info("✅ Local SQLCoder success")
            self.stats["local_success"] += 1
            return AIResponse(
                text=ollama_response.text,
                provider="ollama-sqlcoder",
                success=True
            )
        
        # Step 2: Fallback to API
        logger.info(f"⚡ Fallback to {self.fallback_type} API")
        self.stats["local_failures"] += 1
        
        try:
            fallback_prompt = f"""Convert this question to SQL query.

Database Schema:
{schema}

Question: {question}

Return ONLY the SQL query, nothing else."""
            
            if self.fallback_type == "groq":
                response = await self.fallback.generate_response(
                    user_id=user_id,
                    message=fallback_prompt,
                    system_prompt="You are a SQL expert. Generate only SQL queries."
                )
                sql = response.text.strip()
            else:
                # Gemini
                chat = self.fallback.get_chat(user_id)
                response = await chat.send_message_async(fallback_prompt)
                sql = response.text.strip()
            
            logger.info(f"⚡ Fallback {self.fallback_type} success")
            self.stats["fallback_success"] += 1
            
            return AIResponse(
                text=sql,
                provider=f"{self.fallback_type}-fallback",
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ Fallback also failed: {e}")
            return AIResponse(
                text="",
                provider="hybrid",
                success=False,
                error=f"Both local and API failed: {str(e)[:100]}"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        total = self.stats["total_requests"]
        return {
            "total_requests": total,
            "local_success": self.stats["local_success"],
            "fallback_success": self.stats["fallback_success"],
            "local_success_rate": f"{(self.stats['local_success'] / total * 100):.1f}%" if total > 0 else "N/A",
            "local_failures": self.stats["local_failures"]
        }


# Availability flags
OLLAMA_AVAILABLE = True  # Always True, checked at runtime
