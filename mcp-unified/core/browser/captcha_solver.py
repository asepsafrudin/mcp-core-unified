"""
core/browser/captcha_solver.py — Modul Pemecah CAPTCHA Universal (Reusable Singleton)

Menyediakan interface terpadu untuk memecahkan teks CAPTCHA (Base64, Bytes, atau PIL Image)
menggunakan pola Singleton Lazy-Loaded EasyOCR reader, dengan opsi fallback ke metode lain.
Dapat digunakan lintas portal (Srikandi, SIKERJA, OSS, JDIH, dsb).
"""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Optional, Union
from PIL import Image

logger = logging.getLogger("captcha_solver")

# Singleton instance internal
_EASYOCR_READER = None


def get_easyocr_reader(gpu: bool = False):
    """
    Mengambil instance singleton EasyOCR Reader.
    Inisialisasi lazy (hanya saat pertama kali dipanggil), sehingga tidak membebani import startup.
    """
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            logger.info("Menginisialisasi Singleton EasyOCR Reader (CPU mode)...")
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=gpu)
        except Exception as e:
            logger.error(f"Gagal memuat EasyOCR reader: {e}")
            return None
    return _EASYOCR_READER


def solve_text_captcha(
    image_input: Union[str, bytes, Image.Image],
    allowlist: Optional[str] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    clean_regex: str = r"[^a-zA-Z0-9]",
) -> str:
    """
    Memecahkan teks CAPTCHA alfanumerik dari gambar.

    Args:
        image_input: Base64 string (dengan atau tanpa prefix data:image/...), bytes gambar mentah, atau objek PIL.Image.
        allowlist: Karakter yang diizinkan untuk dibaca oleh model OCR.
        clean_regex: Pola regex untuk membersihkan noise karakter non-target.

    Returns:
        String hasil ekstraksi CAPTCHA (bersih).
    """
    reader = get_easyocr_reader()
    if reader is None:
        logger.warning("EasyOCR Reader tidak tersedia.")
        return ""

    try:
        import numpy as np

        img: Image.Image
        if isinstance(image_input, str):
            if "," in image_input:
                image_input = image_input.split(",", 1)[1]
            img_bytes = base64.b64decode(image_input)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        elif isinstance(image_input, (bytes, bytearray)):
            img = Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, Image.Image):
            img = image_input.convert("RGB")
        else:
            raise ValueError(f"Tipe input gambar tidak didukung: {type(image_input)}")

        # Jalankan ekstraksi teks
        kwargs = {"detail": 0}
        if allowlist:
            kwargs["allowlist"] = allowlist

        results = reader.readtext(np.array(img), **kwargs)
        if not results:
            return ""

        raw_text = "".join(results)
        cleaned = re.sub(clean_regex, "", raw_text).strip()
        return cleaned

    except Exception as e:
        logger.warning(f"Terjadi kesalahan saat mengekstrak CAPTCHA dengan EasyOCR: {e}")
        return ""

