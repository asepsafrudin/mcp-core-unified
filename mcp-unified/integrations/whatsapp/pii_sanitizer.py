"""
pii_sanitizer.py — Personally Identifiable Information (PII) Masking & Sanitizer.
Ensures compliance with Indonesian Personal Data Protection (UU PDP No. 27/2022)
by masking phone numbers, NIK, email, and personal identities in system logs and telemetry.
"""

import re
from typing import Dict, Any, Union, List


class PIISanitizer:
    """
    Sanitizer & Masker data sensitif pengguna (Nomor WhatsApp, NIK, Nama, Email)
    sebelum dicatat ke berkas log persisten atau analitik publik.
    """

    PHONE_PATTERN = re.compile(r'(\+?62|0)(\d{2,4})[-.\s]?(\d{3,4})[-.\s]?(\d{3,5})')
    EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')
    NIK_PATTERN = re.compile(r'\b\d{16}\b')

    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """
        Menyensor nomor telepon dengan mempertahankan kode negara dan digit akhir.
        Contoh: '+6285717223889' -> '+62857****3889'
                '08123456789'   -> '0812****6789'
        """
        if not phone or len(str(phone).strip()) < 8:
            return phone

        clean_p = str(phone).strip()
        if clean_p.startswith("+62"):
            prefix = clean_p[:5]
            suffix = clean_p[-4:]
            return f"{prefix}****{suffix}"
        elif clean_p.startswith("62"):
            prefix = clean_p[:4]
            suffix = clean_p[-4:]
            return f"{prefix}****{suffix}"
        elif clean_p.startswith("08"):
            prefix = clean_p[:4]
            suffix = clean_p[-4:]
            return f"{prefix}****{suffix}"

        # General mask
        return clean_p[:3] + "****" + clean_p[-3:]

    @classmethod
    def mask_name(cls, name: str) -> str:
        """
        Menyensor nama pribadi dengan mempertahankan inisial nama depan dan gelar/nama belakang.
        Contoh: 'Asep Safrudin, S.Kom' -> 'A*** S*******, S.Kom'
        """
        if not name or len(name.strip()) <= 2:
            return name

        parts = name.strip().split(",")
        base_name = parts[0].strip()
        titles = f", {parts[1].strip()}" if len(parts) > 1 else ""

        words = base_name.split()
        masked_words = []
        for w in words:
            if len(w) <= 2:
                masked_words.append(w)
            else:
                masked_words.append(w[0] + "*" * (len(w) - 1))

        return " ".join(masked_words) + titles

    @classmethod
    def mask_email(cls, email: str) -> str:
        """
        Menyensor alamat email.
        Contoh: 'asep.safrudin@kemendagri.go.id' -> 'a***n@kemendagri.go.id'
        """
        if not email or "@" not in email:
            return email

        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]

        return f"{masked_local}@{domain}"

    @classmethod
    def mask_text(cls, text: str) -> str:
        """
        Mendeteksi dan menyensor secara otomatis entitas nomor telepon, email, dan NIK
        yang muncul di dalam teks bebas.
        """
        if not text:
            return text

        # 1. Mask Phone Numbers in text
        def replace_phone(match):
            raw = match.group(0)
            return cls.mask_phone(raw)

        text = cls.PHONE_PATTERN.sub(replace_phone, text)

        # 2. Mask Emails in text
        def replace_email(match):
            raw = match.group(0)
            return cls.mask_email(raw)

        text = cls.EMAIL_PATTERN.sub(replace_email, text)

        # 3. Mask 16-digit NIK
        text = cls.NIK_PATTERN.sub(lambda m: m.group(0)[:4] + "********" + m.group(0)[-4:], text)

        return text

    @classmethod
    def sanitize_log_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Melakukan rekursi sanitasi pada dictionary objek log sebelum diserialisasi ke JSON.
        """
        sanitized = {}
        for k, v in data.items():
            if k in ["user_phone", "phone_number", "proposed_phone", "sender_phone"]:
                sanitized[k] = cls.mask_phone(str(v))
            elif k in ["user_name", "full_name", "proposed_by", "submitted_by"]:
                sanitized[k] = cls.mask_name(str(v))
            elif k in ["email", "user_email"]:
                sanitized[k] = cls.mask_email(str(v))
            elif isinstance(v, dict):
                sanitized[k] = cls.sanitize_log_dict(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    cls.sanitize_log_dict(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                sanitized[k] = v
        return sanitized


# Singleton global
satria_pii_sanitizer = PIISanitizer()
