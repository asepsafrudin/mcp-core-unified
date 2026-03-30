"""
Voice/Audio Transcription Service

Transkripsi pesan suara dan audio menggunakan Groq Whisper API.
Model: whisper-large-v3-turbo (gratis, mendukung Bahasa Indonesia)

Pipeline:
  Voice/Audio → Download → Groq Whisper → Teks → LLM
"""

import os
import logging
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceTranscriptionService:
    """
    Service transkripsi suara menggunakan Groq Whisper.

    Mendukung format: OGG, MP3, WAV, M4A, FLAC, WebM
    Model: whisper-large-v3-turbo (gratis di Groq, akurat untuk Bahasa Indonesia)
    """

    # Model Groq Whisper yang tersedia
    MODELS = {
        "turbo": "whisper-large-v3-turbo",   # Cepat, gratis
        "large": "whisper-large-v3",          # Paling akurat
    }

    def __init__(self, groq_api_key: str, model: str = "turbo"):
        self.api_key = groq_api_key
        self.model_name = self.MODELS.get(model, self.MODELS["turbo"])
        self._client = None
        self._available = False

        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=groq_api_key)
            self._available = True
            logger.info(f"✅ VoiceTranscriptionService initialized (model: {self.model_name})")
        except ImportError:
            logger.error("groq package not installed")
        except Exception as e:
            logger.error(f"Failed to init VoiceTranscriptionService: {e}")

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None

    async def transcribe_file(
        self,
        file_path: str,
        language: str = "id",
        prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Transkripsi file audio ke teks.

        Args:
            file_path: Path ke file audio lokal
            language: Kode bahasa (default: 'id' = Indonesia)
            prompt: Opsional — hint konteks untuk akurasi lebih baik

        Returns:
            Teks hasil transkripsi, atau None jika gagal
        """
        if not self.is_available:
            logger.error("VoiceTranscriptionService not available")
            return None

        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return None

        try:
            with open(file_path, "rb") as audio_file:
                kwargs = {
                    "file": audio_file,
                    "model": self.model_name,
                    "language": language,
                    "response_format": "text",
                }
                if prompt:
                    kwargs["prompt"] = prompt

                transcription = await self._client.audio.transcriptions.create(**kwargs)

            # Response bisa berupa string langsung atau object
            if isinstance(transcription, str):
                result = transcription.strip()
            else:
                result = getattr(transcription, 'text', str(transcription)).strip()

            logger.info(f"✅ Transcribed {os.path.basename(file_path)}: '{result[:50]}...'")
            return result if result else None

        except Exception as e:
            logger.error(f"Transcription failed for {file_path}: {e}")
            return None

    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg",
        language: str = "id"
    ) -> Optional[str]:
        """
        Transkripsi audio dari bytes (tanpa file sementara).

        Args:
            audio_bytes: Raw audio bytes
            filename: Nama file untuk deteksi format
            language: Kode bahasa

        Returns:
            Teks hasil transkripsi
        """
        # Tulis ke file temp
        suffix = os.path.splitext(filename)[1] or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return await self.transcribe_file(tmp_path, language=language)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def get_supported_formats(self) -> list:
        """Daftar format audio yang didukung Groq Whisper."""
        return ["ogg", "mp3", "wav", "m4a", "flac", "webm", "mp4"]
