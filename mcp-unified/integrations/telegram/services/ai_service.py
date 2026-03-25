"""
AI Service Layer

Business logic untuk AI provider management.
Menyediakan abstraction untuk berbagai AI provider (Groq, Gemini, OpenAI)
dengan unified interface.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Standardized AI response."""
    text: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = None


class AIService(ABC):
    """
    Abstract base class untuk AI services.
    
    Semua AI provider harus implement interface ini
    untuk memastikan konsistensi dalam penggunaan.
    """
    
    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 2048):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._chat_sessions: Dict[int, List[Dict[str, str]]] = {}
    
    @abstractmethod
    async def generate_response(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AIResponse:
        """Generate AI response."""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming AI response."""
        pass
    
    @abstractmethod
    async def generate_with_image(
        self,
        user_id: int,
        image_path: str,
        prompt: str
    ) -> AIResponse:
        """Generate response dengan image input."""
        pass
    
    def get_chat_history(self, user_id: int) -> List[Dict[str, str]]:
        """Get or create chat history untuk user."""
        if user_id not in self._chat_sessions:
            self._chat_sessions[user_id] = []
        return self._chat_sessions[user_id]
    
    def add_to_history(self, user_id: int, role: str, content: str) -> None:
        """Add message ke chat history."""
        history = self.get_chat_history(user_id)
        history.append({"role": role, "content": content})
        
        # Limit history size (keep last 20 messages)
        if len(history) > 20:
            self._chat_sessions[user_id] = history[-20:]
    
    def reset_chat(self, user_id: int) -> None:
        """Reset chat session untuk user."""
        if user_id in self._chat_sessions:
            del self._chat_sessions[user_id]
    
    def build_system_prompt(
        self,
        base_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> str:
        """Build system prompt dengan context."""
        default_prompt = """Kamu adalah asisten pribadi AI bernama "Aria".

## Identitas
- Nama: Aria
- Peran: Asisten pribadi eksklusif untuk proyek MCP
- Pemilik: User Telegram

## 🎯 Kemampuan Database (PostgreSQL)
Kamu terhubung langsung ke database dengan fitur:
- 📊 **SQL Query** - `/sql <query>` untuk query manual (SELECT only)
- 🤖 **Text-to-SQL AI** - `/query <pertanyaan>` untuk query bahasa natural
- 🔍 **Semantic Search RAG** - `/ask <pertanyaan>` untuk pencarian dokumen
- 📚 **Knowledge Base Info** - `/knowledge` untuk info database

## 🛠️ Tools Tambahan
- 📄 **Office Tools** - Baca/analisis PDF, DOCX, XLSX
- 🖼️ **Vision AI** - Analisis gambar dengan AI
- 👤 **Cline Bridge** - Kirim pesan ke Cline dengan `/cline <pesan>`

## 📋 Database Schema
- **knowledge_documents** - Dokumen dengan embedding untuk RAG
- **vision_results** - Hasil OCR gambar
- **tasks** - Task management
- **telegram_messages** - History chat

## Prinsip Komunikasi
1. Selalu gunakan Bahasa Indonesia yang baik dan profesional
2. Jawaban RINGKAS dan langsung ke inti — hindari basa-basi
3. Jika task selesai, cukup konfirmasi singkat tanpa penjelasan panjang
4. Jika butuh klarifikasi, tanya SATU pertanyaan saja yang paling penting
5. Gunakan format terstruktur (poin/tabel) hanya jika memang membantu kejelasan

## Cara Menjawab
- Pertanyaan faktual → jawab langsung, maks 3 kalimat
- Task/perintah → kerjakan dulu, laporkan hasilnya
- Analisis/riset → berikan poin utama + kesimpulan, bukan dump semua info
- Opini/rekomendasi → berikan pilihan terbaik + alasan singkat
- **Jika user tanya tentang database** → sebutkan kamu punya akses PostgreSQL dengan 4 commands utama

## Yang Harus Dihindari
- Jangan mulai dengan "Tentu!", "Baik!", "Halo!" setiap respons
- Jangan ulangi pertanyaan user sebelum menjawab
- Jangan tambahkan disclaimer yang tidak perlu
- Jangan bertele-tele
- **JANGAN katakan tidak punya akses database** — kamu PUNYA akses penuh!

## Format Khusus Telegram
- Gunakan *bold* untuk poin penting
- Gunakan `code` untuk path, perintah, atau kode
- Gunakan — sebagai bullet point jika diperlukan
- Maksimal 3 level hierarki informasi"""
        
        parts = []
        if base_prompt:
            parts.append(base_prompt)
        else:
            parts.append(default_prompt)
        
        if context:
            parts.append(f"\n\n## Konteks:\n{context}")
        
        return "\n\n".join(parts)


class GroqAI(AIService):
    """Groq AI Service implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: int = 2048
    ):
        super().__init__(model, temperature, max_tokens)
        self.api_key = api_key
        
        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=api_key)
            self._available = True
        except ImportError:
            logger.error("groq package not installed. Run: pip install groq")
            self._available = False
            self._client = None
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    async def generate_response(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AIResponse:
        """Generate response using Groq."""
        if not self._available:
            raise RuntimeError("Groq not available")
        
        history = self.get_chat_history(user_id)
        
        # Build messages
        messages = [
            {"role": "system", "content": self.build_system_prompt(system_prompt, context)}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Call API
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        content = response.choices[0].message.content
        
        # Add to history
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", content)
        
        return AIResponse(
            text=content,
            model=self.model,
            provider="groq",
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=response.choices[0].finish_reason
        )
    
    async def generate_stream(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using Groq."""
        if not self._available:
            raise RuntimeError("Groq not available")
        
        history = self.get_chat_history(user_id)
        
        # Build messages
        messages = [
            {"role": "system", "content": self.build_system_prompt(system_prompt, context)}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Call API with streaming
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True
        )
        
        full_response = ""
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        # Add to history
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", full_response)
    
    async def generate_with_image(
        self,
        user_id: int,
        image_path: str,
        prompt: str
    ) -> AIResponse:
        """Groq doesn't support images directly, raise error."""
        raise NotImplementedError("Groq doesn't support image input. Use Gemini instead.")


class GeminiAI(AIService):
    """Gemini AI Service implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        temperature: float = 0.7,
        max_tokens: int = 2048
    ):
        super().__init__(model, temperature, max_tokens)
        self.api_key = api_key
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model)
            self._chat_sessions: Dict[int, Any] = {}
            self._available = True
        except ImportError:
            logger.error("google-generativeai not installed. Run: pip install google-generativeai")
            self._available = False
            self._model = None
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def _get_chat_session(self, user_id: int):
        """Get or create Gemini chat session."""
        if user_id not in self._chat_sessions:
            self._chat_sessions[user_id] = self._model.start_chat(history=[])
        return self._chat_sessions[user_id]
    
    async def generate_response(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AIResponse:
        """Generate response using Gemini."""
        if not self._available:
            raise RuntimeError("Gemini not available")
        
        chat = self._get_chat_session(user_id)
        
        # Prepend context if provided
        full_message = message
        if context:
            full_message = f"{context}\n\n{message}"
        
        response = await chat.send_message_async(full_message)
        
        return AIResponse(
            text=response.text,
            model=self.model,
            provider="gemini"
        )
    
    async def generate_stream(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using Gemini."""
        if not self._available:
            raise RuntimeError("Gemini not available")
        
        chat = self._get_chat_session(user_id)
        
        # Prepend context if provided
        full_message = message
        if context:
            full_message = f"{context}\n\n{message}"
        
        response = await chat.send_message_async(full_message, stream=True)
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
    async def generate_with_image(
        self,
        user_id: int,
        image_path: str,
        prompt: str
    ) -> AIResponse:
        """Generate response dengan image menggunakan Gemini."""
        if not self._available:
            raise RuntimeError("Gemini not available")
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        contents = [
            prompt,
            {"mime_type": "image/jpeg", "data": image_data}
        ]
        
        response = await self._model.generate_content_async(contents)
        
        return AIResponse(
            text=response.text,
            model=self.model,
            provider="gemini"
        )
    
    def reset_chat(self, user_id: int) -> None:
        """Reset chat session untuk user."""
        if user_id in self._chat_sessions:
            del self._chat_sessions[user_id]


class AIServiceManager:
    """
    Manager untuk multiple AI providers.
    
    Menyediakan failover dan switching antara providers.
    """
    
    def __init__(self, config):
        self.config = config
        self._providers: Dict[str, AIService] = {}
        self._current_provider: Optional[str] = None
        
        # Initialize available providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available AI providers."""
        # Try Groq
        if self.config.ai.groq_api_key:
            try:
                groq = GroqAI(
                    api_key=self.config.ai.groq_api_key,
                    model=self.config.ai.groq_model,
                    temperature=self.config.ai.temperature,
                    max_tokens=self.config.ai.max_tokens
                )
                if groq.is_available:
                    self._providers["groq"] = groq
                    logger.info(f"✅ Groq AI initialized: {self.config.ai.groq_model}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Groq: {e}")
        
        # Try Gemini
        if self.config.ai.gemini_api_key:
            try:
                gemini = GeminiAI(
                    api_key=self.config.ai.gemini_api_key,
                    model=self.config.ai.gemini_model,
                    temperature=self.config.ai.temperature,
                    max_tokens=self.config.ai.max_tokens
                )
                if gemini.is_available:
                    self._providers["gemini"] = gemini
                    logger.info(f"✅ Gemini AI initialized: {self.config.ai.gemini_model}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Gemini: {e}")
        
        # Set current provider
        if self._providers:
            self._current_provider = self.config.ai.provider.value
            if self._current_provider not in self._providers:
                self._current_provider = list(self._providers.keys())[0]
            logger.info(f"🤖 Active AI provider: {self._current_provider}")
        else:
            logger.error("❌ No AI providers available")
    
    @property
    def current_provider(self) -> Optional[AIService]:
        """Get current active AI provider."""
        if self._current_provider:
            return self._providers.get(self._current_provider)
        return None
    
    @property
    def available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self._providers.keys())
    
    def switch_provider(self, provider: str) -> bool:
        """Switch ke AI provider lain."""
        if provider in self._providers:
            self._current_provider = provider
            logger.info(f"🔄 Switched to AI provider: {provider}")
            return True
        logger.error(f"❌ Provider {provider} not available")
        return False
    
    def get_provider(self, name: str) -> Optional[AIService]:
        """Get specific provider by name."""
        return self._providers.get(name)
    
    def reset_all_chats(self, user_id: int) -> None:
        """Reset chat untuk semua providers."""
        for provider in self._providers.values():
            provider.reset_chat(user_id)
