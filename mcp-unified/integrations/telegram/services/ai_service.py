"""
AI Service Layer

Business logic untuk AI provider management.
Menyediakan abstraction untuk berbagai AI provider (Groq, Gemini, OpenAI)
dengan unified interface.

Changelog:
- Tambah OpenAI provider (gpt-4o-mini)
- Migrasi Gemini dari google-generativeai ke google-genai SDK baru (v1.57+)
- Verifikasi Groq model: qwen/qwen3-32b (aktif, context 131072)
"""

import os
import re
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field

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
    
    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 4096):
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
    
    @staticmethod
    def strip_thinking_tags(text: str) -> str:
        """Hapus tag <think>...</think> dari output thinking models (Qwen3, QwQ, dll).
        
        Model seperti qwen/qwen3-32b mengeluarkan proses berpikir dalam tag <think>.
        Tag ini harus dihapus sebelum dikirim ke user.
        """
        if not text:
            return text
        # Hapus blok <think>...</think> (termasuk multiline, case-insensitive)
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Bersihkan whitespace berlebih di awal/akhir
        cleaned = cleaned.strip()
        # Jika ada baris kosong berlebih, kompres jadi max 2 baris
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned
    
    @staticmethod
    def get_current_datetime_wib() -> str:
        """Dapatkan tanggal dan waktu saat ini dalam WIB (UTC+7)."""
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)
        day_names = {
            0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis',
            4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'
        }
        month_names = {
            1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
            5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
            9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
        }
        day = day_names[now.weekday()]
        month = month_names[now.month]
        return (
            f"{day}, {now.day} {month} {now.year} "
            f"pukul {now.strftime('%H:%M')} WIB"
        )
    
    def build_system_prompt(
        self,
        base_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> str:
        """Build system prompt dengan context dan datetime WIB yang selalu diperbarui."""
        # Datetime WIB real-time — diinjeksi setiap kali prompt dibangun
        current_datetime = self.get_current_datetime_wib()
        
        default_prompt = f"""Kamu adalah asisten pribadi AI bernama "Aria".

## 🕐 Waktu & Tanggal Saat Ini
Sekarang adalah: **{current_datetime}**
Kamu HARUS menggunakan informasi ini saat menjawab pertanyaan tentang hari, tanggal, atau waktu.
JANGAN katakan kamu tidak tahu tanggal/waktu — kamu sudah mengetahuinya dari informasi di atas.

## Identitas
- Nama: Aria
- Peran: Asisten pribadi eksklusif untuk proyek MCP
- Pemilik: User Telegram

## 🎯 Kemampuan Korespondensi
Kamu dapat mencari data surat masuk/keluar secara real-time:
- 🔍 **Cari Perihal** - Gunakan tool `search_letters` (parameter: `query`) untuk mencari berdasarkan perihal, nomor surat, atau pengirim.
- 📬 **Status Korespondensi** - Gunakan `get_correspondence` untuk ringkasan terkini.
- 🔢 **Hitung Surat** - Gunakan `count_letters` untuk statistik kuantitatif.

## 📊 Database Schema (PostgreSQL)
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
- **JANGAN katakan tidak tahu tanggal/waktu** — kamu sudah tahu dari system prompt!

## Format Khusus Telegram
- Gunakan *bold* untuk poin penting
- Gunakan `code` untuk path, perintah, atau kode
- Gunakan — sebagai bullet point jika diperlukan
- Maksimal 3 level hierarki informasi"""
        
        parts = []
        if base_prompt:
            # Jika ada custom prompt, tetap inject datetime di awal
            datetime_header = f"## 🕐 Waktu & Tanggal Saat Ini\nSekarang adalah: **{current_datetime}**\n"
            parts.append(datetime_header)
            parts.append(base_prompt)
        else:
            parts.append(default_prompt)
        
        if context:
            parts.append(f"\n\n## Konteks:\n{context}")
        
        return "\n\n".join(parts)


# ==============================================================================
# GROQ AI (Provider 1 - AKTIF)
# Model: qwen/qwen3-32b | Context: 131072 | Max completion: 40960
# Status: ✅ Verified aktif via API 2026-03-27
# ==============================================================================
class GroqAI(AIService):
    """Groq AI Service implementation.
    
    Model yang digunakan: qwen/qwen3-32b
    Verified aktif: 2026-03-27 via GET /openai/v1/models
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        super().__init__(model, temperature, max_tokens)
        self.api_key = api_key
        
        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=api_key)
            self._available = True
            logger.info(f"✅ Groq client initialized (model: {model})")
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
        
        raw_content = response.choices[0].message.content
        # Filter <think> tag — qwen3-32b adalah thinking model
        content = self.strip_thinking_tags(raw_content)
        
        # Add to history (simpan versi yang sudah bersih)
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
        
        # Untuk streaming, kumpulkan dulu semua chunk lalu filter think tags
        # karena <think> bisa terpotong di tengah stream
        raw_chunks = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                raw_chunks.append(chunk.choices[0].delta.content)
        
        # Gabung semua chunk, filter <think>, lalu yield bersih
        full_raw = "".join(raw_chunks)
        full_response = self.strip_thinking_tags(full_raw)
        
        # Yield response yang sudah bersih (simulasi streaming per kata)
        # agar UX tetap terasa streaming
        words = full_response.split(' ')
        for i, word in enumerate(words):
            yield word + (' ' if i < len(words) - 1 else '')
        
        # Add to history (versi bersih)
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", full_response)
    
    async def generate_with_image(
        self,
        user_id: int,
        image_path: str,
        prompt: str
    ) -> AIResponse:
        """Groq doesn't support images directly, raise error."""
        raise NotImplementedError("Groq doesn't support image input. Use Gemini atau OpenAI instead.")

    async def generate_with_tools(
        self,
        user_id: int,
        message: str,
        tools: List[Dict],
        tool_executor,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        max_iterations: int = 3
    ) -> str:
        """
        Agentic loop dengan Function Calling.

        LLM memutuskan sendiri kapan memanggil tools, mengeksekusinya,
        lalu melanjutkan sampai menghasilkan respons final untuk user.

        Args:
            user_id: Telegram user ID
            message: Pesan user
            tools: List tool definitions (JSON schema)
            tool_executor: ToolExecutor instance
            system_prompt: Custom system prompt
            context: Additional context
            max_iterations: Batas iterasi (default 3, cukup untuk 1-2 tool call)

        Returns:
            Final response string
        """
        if not self._available:
            raise RuntimeError("Groq not available")

        history = self.get_chat_history(user_id)
        messages = [
            {"role": "system", "content": self.build_system_prompt(system_prompt, context)}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        final_response = ""
        # Hitung berapa kali tool gagal berturut untuk deteksi stuck
        consecutive_errors = 0

        for iteration in range(max_iterations):
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            msg = choice.message

            # Build assistant message dict
            msg_dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            messages.append(msg_dict)

            # LLM selesai → ambil hasilnya langsung
            if finish_reason == "stop" or not msg.tool_calls:
                raw = msg.content or ""
                final_response = self.strip_thinking_tags(raw)
                break

            # Eksekusi semua tool calls
            logger.info(f"🔧 Agentic iter {iteration+1}/{max_iterations}: {len(msg.tool_calls)} tool(s)")
            iter_had_error = False

            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except Exception:
                    tool_args = {}

                tool_result = await tool_executor.execute(tool_name, tool_args)
                logger.info(f"  → {tool_name}: {tool_result[:120]}")

                # Deteksi tool error / DB unavailable
                try:
                    result_data = json.loads(tool_result)
                    if result_data.get("status") == "db_unavailable":
                        iter_had_error = True
                    elif "error" in result_data and "success" not in result_data and "data" not in result_data:
                        iter_had_error = True
                except Exception:
                    pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
        else:
            # Max iterations tercapai
            logger.warning(f"Agentic loop reached max {max_iterations} iterations")
            if not final_response:
                final_response = "Saya memerlukan terlalu banyak langkah. Coba pertanyaan yang lebih spesifik."

        # Simpan ke history
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", final_response)

        return final_response


# ==============================================================================
# GEMINI AI (Provider 2 - FALLBACK)
# Menggunakan google-genai SDK baru (v1.57+) — bukan google-generativeai lama
# Model: gemini-2.0-flash
# ==============================================================================
class GeminiAI(AIService):
    """Gemini AI Service implementation.
    
    Menggunakan google-genai SDK baru (v1.57+).
    Menggantikan google-generativeai yang sudah deprecated.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        super().__init__(model, temperature, max_tokens)
        self.api_key = api_key
        self._chat_histories: Dict[int, List[Dict]] = {}
        
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=api_key)
            self._types = types
            self._available = True
            logger.info(f"✅ Gemini client initialized via google-genai SDK (model: {model})")
        except ImportError:
            logger.error("google-genai not installed. Run: pip install google-genai")
            self._available = False
            self._client = None
            self._types = None
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def _format_history_for_gemini(self, history: List[Dict[str, str]]) -> List[Dict]:
        """Konversi history ke format Gemini (role: user/model)."""
        formatted = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            formatted.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        return formatted
    
    async def generate_response(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AIResponse:
        """Generate response using Gemini (google-genai SDK)."""
        if not self._available:
            raise RuntimeError("Gemini not available")
        
        import asyncio
        
        system = self.build_system_prompt(system_prompt, context)
        full_message = message
        if context:
            full_message = f"{context}\n\n{message}"
        
        # Build config
        config = self._types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        
        # Build contents dengan history
        history = self.get_chat_history(user_id)
        contents = self._format_history_for_gemini(history)
        contents.append({"role": "user", "parts": [{"text": full_message}]})
        
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self.model,
            contents=contents,
            config=config
        )
        
        text = response.text
        
        # Add to history
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", text)
        
        return AIResponse(
            text=text,
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
        """Generate streaming response using Gemini (google-genai SDK)."""
        if not self._available:
            raise RuntimeError("Gemini not available")
        
        import asyncio
        import queue
        import threading
        
        system = self.build_system_prompt(system_prompt, context)
        full_message = message
        if context:
            full_message = f"{context}\n\n{message}"
        
        config = self._types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        
        history = self.get_chat_history(user_id)
        contents = self._format_history_for_gemini(history)
        contents.append({"role": "user", "parts": [{"text": full_message}]})
        
        # Gunakan asyncio queue untuk streaming sync->async bridge
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        full_response = []
        
        def stream_in_thread():
            try:
                for chunk in self._client.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=config
                ):
                    if chunk.text:
                        full_response.append(chunk.text)
                        loop.call_soon_threadsafe(q.put_nowait, chunk.text)
            except Exception as e:
                loop.call_soon_threadsafe(q.put_nowait, None)
                logger.error(f"Gemini stream error: {e}")
            finally:
                loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel
        
        thread = threading.Thread(target=stream_in_thread, daemon=True)
        thread.start()
        
        while True:
            text = await q.get()
            if text is None:
                break
            yield text
        
        # Add to history
        final_response = "".join(full_response)
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", final_response)
    
    async def generate_with_image(
        self,
        user_id: int,
        image_path: str,
        prompt: str
    ) -> AIResponse:
        """Generate response dengan image menggunakan Gemini (google-genai SDK)."""
        if not self._available:
            raise RuntimeError("Gemini not available")
        
        import asyncio
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Deteksi mime type dari extension
        ext = image_path.lower().split('.')[-1]
        mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'gif': 'image/gif', 'webp': 'image/webp'}
        mime_type = mime_map.get(ext, 'image/jpeg')
        
        contents = [
            {"role": "user", "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_data}}
            ]}
        ]
        
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self.model,
            contents=contents
        )
        
        return AIResponse(
            text=response.text,
            model=self.model,
            provider="gemini"
        )

    async def generate_with_tools(
        self,
        user_id: int,
        message: str,
        tools: List[Dict],
        tool_executor,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        max_iterations: int = 5
    ) -> str:
        """
        Agentic loop untuk Gemini (Function Calling).
        Implementasi menggunakan google-genai SDK baru.
        """
        if not self._available:
            raise RuntimeError("Gemini not available")

        import asyncio
        import json

        # 1. Bangun system instruction & contents
        system = self.build_system_prompt(system_prompt, context)
        history = self.get_chat_history(user_id)
        
        # Konversi history ke format Gemini
        contents = self._format_history_for_gemini(history)
        contents.append({"role": "user", "parts": [{"text": message}]})

        # 2. Konversi OpenAI tools ke Gemini format (minimal)
        # Note: GenAI SDK bisa menerima dict JSON schema langsung
        gemini_tools = []
        for t in tools:
            if t.get("type") == "function":
                gemini_tools.append({"function_declarations": [t["function"]]})
            else:
                # Fallback if already in different format
                gemini_tools.append(t)

        # 3. Agentic Loop
        final_response = ""
        
        for iteration in range(max_iterations):
            config = self._types.GenerateContentConfig(
                system_instruction=system,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
                tools=gemini_tools
            )

            # Generate response
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.model,
                contents=contents,
                config=config
            )

            # Cek result
            if not response.candidates:
                final_response = "Maaf, sistem AI tidak memberikan respon valid."
                break

            candidate = response.candidates[0]
            # Tambahkan model response ke contents (untuk context di iterasi berikutnya)
            contents.append(candidate.content)

            # Cek tool calls
            tool_calls = []
            for part in candidate.content.parts:
                if part.call:
                    tool_calls.append(part.call)

            if not tool_calls:
                # Selesai, ambil teks
                text = response.text or ""
                final_response = text
                break

            # Eksekusi tools
            logger.info(f"🔧 Gemini Agentic iter {iteration+1}: {len(tool_calls)} tool(s)")
            
            # Gemini mengizinkan multiple tool calls dalam satu turn
            tool_responses = []
            for call in tool_calls:
                tool_name = call.name
                tool_args = call.args if call.args else {}
                
                # Execute tool
                tool_result = await tool_executor.execute(tool_name, tool_args)
                logger.info(f"  → {tool_name}: {tool_result[:120]}")
                
                # Tambahkan response part
                tool_responses.append({
                    "function_response": {
                        "name": tool_name,
                        "response": {"result": tool_result}
                    }
                })

            # Append tool responses as 'user' (atau 'tool' role tergantung SDK)
            # SDK v1.57+ menggunakan role 'user' untuk function responses
            contents.append({
                "role": "user",
                "parts": tool_responses
            })
        else:
            final_response = "Iterasi maksimal tercapai. Silakan coba pertanyaan yang lebih sederhana."

        # Simpan ke history
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", final_response)

        return final_response
    
    def reset_chat(self, user_id: int) -> None:
        """Reset chat session untuk user."""
        super().reset_chat(user_id)
        if user_id in self._chat_histories:
            del self._chat_histories[user_id]


# ==============================================================================
# OPENAI AI (Provider 3 - BARU)
# Model: gpt-4o-mini
# Status: ✅ API key valid (HTTP 200 GET /v1/models terverifikasi 2026-03-27)
# ==============================================================================
class OpenAIService(AIService):
    """OpenAI AI Service implementation.
    
    Model: gpt-4o-mini (default) atau gpt-4o
    API key status: Terverifikasi valid 2026-03-27
    Mendukung: text generation, streaming, dan image input (vision)
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        super().__init__(model, temperature, max_tokens)
        self.api_key = api_key
        
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
            self._available = True
            logger.info(f"✅ OpenAI client initialized (model: {model})")
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
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
        """Generate response using OpenAI."""
        if not self._available:
            raise RuntimeError("OpenAI not available")
        
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
            provider="openai",
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
        """Generate streaming response using OpenAI."""
        if not self._available:
            raise RuntimeError("OpenAI not available")
        
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
        """Generate response dengan image menggunakan OpenAI Vision (gpt-4o)."""
        if not self._available:
            raise RuntimeError("OpenAI not available")
        
        import base64
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Deteksi mime type
        ext = image_path.lower().split('.')[-1]
        mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'gif': 'image/gif', 'webp': 'image/webp'}
        mime_type = mime_map.get(ext, 'image/jpeg')
        
        # Gunakan gpt-4o untuk vision (gpt-4o-mini juga mendukung)
        vision_model = self.model if "4o" in self.model else "gpt-4o-mini"
        
        response = await self._client.chat.completions.create(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}"
                    }}
                ]
            }],
            max_tokens=self.max_tokens
        )
        
        return AIResponse(
            text=response.choices[0].message.content,
            model=vision_model,
            provider="openai",
            tokens_used=response.usage.total_tokens if response.usage else None
        )

    async def generate_with_tools(
        self,
        user_id: int,
        message: str,
        tools: List[Dict],
        tool_executor,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        max_iterations: int = 5
    ) -> str:
        """
        Agentic loop dengan Function Calling (OpenAI style).
        """
        if not self._available:
            raise RuntimeError("OpenAI not available")

        import json
        history = self.get_chat_history(user_id)
        messages = [
            {"role": "system", "content": self.build_system_prompt(system_prompt, context)}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        final_response = ""
        for iteration in range(max_iterations):
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            msg = choice.message

            # Build assistant message dict for context
            msg_dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            messages.append(msg_dict)

            # LLM selesai → ambil hasilnya langsung
            if finish_reason == "stop" or not msg.tool_calls:
                final_response = msg.content or ""
                break

            # Eksekusi semua tool calls
            logger.info(f"🔧 Agentic iter {iteration+1}/{max_iterations}: {len(msg.tool_calls)} tool(s)")
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except Exception:
                    tool_args = {}

                tool_result = await tool_executor.execute(tool_name, tool_args)
                logger.info(f"  → {tool_name}: {tool_result[:120]}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
        else:
            final_response = "Batas iterasi tercapai tanpa hasil final."

        # Simpan ke history
        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", final_response)
        return final_response


class OllamaChatService(AIService):
    """
    Service untuk Ollama (Lokal).
    Sangat berguna sebagai cadangan terakhir saat semua cloud API limit.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        super().__init__(model, temperature, max_tokens)
        self.base_url = base_url.rstrip('/')
        self._available = False
        
        # Check availability
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/api/tags", timeout=2)
            if r.status_code == 200:
                self._available = True
                logger.info(f"🏠 Ollama server found at {self.base_url}")
        except Exception:
            self._available = False

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
        import httpx
        history = self.get_chat_history(user_id)
        messages = [{"role": "system", "content": self.build_system_prompt(system_prompt, context)}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self.temperature}
                }
            )
            r.raise_for_status()
            data = r.json()
            content = data["message"]["content"]

        self.add_to_history(user_id, "user", message)
        self.add_to_history(user_id, "assistant", content)

        return AIResponse(text=content, model=self.model, provider="ollama")

    async def generate_stream(
        self,
        user_id: int,
        message: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        import httpx
        import json
        history = self.get_chat_history(user_id)
        messages = [{"role": "system", "content": self.build_system_prompt(system_prompt, context)}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": self.temperature}
                }
            ) as response:
                full_content = ""
                async for line in response.aiter_lines():
                    if not line: continue
                    chunk = json.loads(line)
                    if "message" in chunk:
                        content = chunk["message"].get("content", "")
                        full_content += content
                        yield content
                
                self.add_to_history(user_id, "user", message)
                self.add_to_history(user_id, "assistant", full_content)

    async def generate_with_tools(self, *args, **kwargs) -> str:
        # LLama3.2 3B support tools theoretically, but simple version for now:
        # Fallback to normal response
        resp = await self.generate_response(kwargs.get('user_id', 0), kwargs.get('message', ''))
        return resp.text


# ==============================================================================
# AI SERVICE MANAGER
# Mengelola semua provider dengan failover otomatis
# Priority: groq → gemini → openai (sesuai AI_PROVIDER env)
# ==============================================================================
class AIServiceManager:
    """
    Manager untuk multiple AI providers.
    
    Menyediakan failover dan switching antara providers.
    
    Provider yang didukung:
    - groq    → qwen/qwen3-32b (AKTIF, default)
    - gemini  → gemini-2.0-flash (google-genai SDK baru)
    - openai  → gpt-4o-mini (BARU, API terverifikasi)
    """
    
    def __init__(self, config):
        self.config = config
        self._providers: Dict[str, AIService] = {}
        self._current_provider: Optional[str] = None
        
        # Initialize available providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available AI providers."""
        
        # --- Provider 1: Groq ---
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
                    logger.info(f"✅ Groq AI registered: {self.config.ai.groq_model}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Groq: {e}")
        
        # --- Provider 2: Gemini (google-genai SDK baru) ---
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
                    logger.info(f"✅ Gemini AI registered: {self.config.ai.gemini_model} (via google-genai SDK)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Gemini: {e}")
        
        # --- Provider 3: OpenAI (BARU) ---
        if self.config.ai.openai_api_key:
            try:
                openai_svc = OpenAIService(
                    api_key=self.config.ai.openai_api_key,
                    model=self.config.ai.openai_model,
                    temperature=self.config.ai.temperature,
                    max_tokens=self.config.ai.max_tokens
                )
                if openai_svc.is_available:
                    self._providers["openai"] = openai_svc
                    logger.info(f"✅ OpenAI registered: {self.config.ai.openai_model}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize OpenAI: {e}")
        
        # --- Provider 4: Ollama (LOCAL NUCLEAR FALLBACK) ---
        if self.config.ai.ollama_url:
            try:
                ollama = OllamaChatService(
                    base_url=self.config.ai.ollama_url,
                    model=self.config.ai.ollama_model,
                    temperature=self.config.ai.temperature,
                    max_tokens=self.config.ai.max_tokens
                )
                if ollama.is_available:
                    self._providers["ollama"] = ollama
                    logger.info(f"🏠 Ollama registered: {self.config.ai.ollama_model} (Local Nuclear Fallback)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Ollama: {e}")

        # --- Set current provider ---
        if self._providers:
            requested = self.config.ai.provider.value
            if requested in self._providers:
                self._current_provider = requested
            else:
                # Fallback priority: groq -> gemini -> openai -> ollama
                priority = ["groq", "gemini", "openai", "ollama"]
                for p in priority:
                    if p in self._providers:
                        self._current_provider = p
                        break
                else:
                    self._current_provider = list(self._providers.keys())[0]

                logger.warning(
                    f"⚠️ Provider '{requested}' tidak tersedia, "
                    f"fallback ke '{self._current_provider}'"
                )
            logger.info(
                f"🤖 Active AI provider: {self._current_provider} "
                f"| Available: {list(self._providers.keys())}"
            )
        else:
            logger.error("❌ No AI providers available! Periksa API keys di .env")
    
    @property
    def current_provider(self) -> Optional[AIService]:
        """Get current active AI provider."""
        if self._current_provider:
            return self._providers.get(self._current_provider)
        return None
    
    @property
    def current_provider_name(self) -> Optional[str]:
        """Get current provider name."""
        return self._current_provider
    
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
        logger.error(f"❌ Provider '{provider}' tidak tersedia. Tersedia: {list(self._providers.keys())}")
        return False
    
    def get_provider(self, name: str) -> Optional[AIService]:
        """Get specific provider by name."""
        return self._providers.get(name)
    
    def reset_all_chats(self, user_id: int) -> None:
        """Reset chat untuk semua providers."""
        for provider in self._providers.values():
            provider.reset_chat(user_id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get status semua provider (untuk /status command)."""
        return {
            "current_provider": self._current_provider,
            "available_providers": self.available_providers,
            "providers_detail": {
                name: {
                    "model": svc.model,
                    "temperature": svc.temperature,
                    "max_tokens": svc.max_tokens,
                    "is_active": name == self._current_provider
                }
                for name, svc in self._providers.items()
            }
        }
