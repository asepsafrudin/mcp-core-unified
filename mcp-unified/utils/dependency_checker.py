"""
DependencyChecker - Pemeriksa Dependensi Lingkungan & OS Pre-flight untuk Tool MCP.

Menyediakan validasi proaktif terhadap utilitas sistem eksternal sebelum tool dijalankan,
sehingga agen menerima laporan diagnostik terstruktur jika binari OS/paket belum terpasang.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class DependencyStatus:
    name: str
    available: bool
    path: Optional[str]
    version: Optional[str]
    remediation_cmd: str
    details: str

    def to_dict(self) -> Dict:
        return asdict(self)


class DependencyChecker:
    """Validator dependensi sistem eksternal."""

    KNOWN_DEPENDENCIES = {
        "libreoffice": {
            "binaries": ["libreoffice", "soffice"],
            "version_arg": "--version",
            "remediation": "sudo apt-get install -y libreoffice-core libreoffice-writer libreoffice-calc",
            "purpose": "Konversi dokumen legacy .doc, .ppt, .odt, .rtf ke PDF/format modern",
        },
        "tesseract": {
            "binaries": ["tesseract"],
            "version_arg": "--version",
            "remediation": "sudo apt-get install -y tesseract-ocr tesseract-ocr-ind",
            "purpose": "Ekstraksi OCR lokal & deteksi orientasi naskah (OSD)",
        },
        "poppler": {
            "binaries": ["pdftoppm", "pdfinfo"],
            "version_arg": "-v",
            "remediation": "sudo apt-get install -y poppler-utils",
            "purpose": "Rasterisasi PDF ke gambar berkecepatan tinggi",
        },
        "ffmpeg": {
            "binaries": ["ffmpeg"],
            "version_arg": "-version",
            "remediation": "sudo apt-get install -y ffmpeg",
            "purpose": "Ekstraksi audio/video dan transkripsi media",
        },
    }

    @classmethod
    def check_binary(
        cls,
        name: str,
        binaries: Optional[List[str]] = None,
        version_arg: str = "--version",
        remediation: str = "",
        purpose: str = "",
    ) -> DependencyStatus:
        """Memeriksa apakah salah satu dari daftar biner tersedia di PATH sistem."""
        candidate_binaries = binaries or [name]
        found_path: Optional[str] = None

        for b in candidate_binaries:
            resolved = shutil.which(b)
            if resolved:
                found_path = resolved
                break

        if not found_path:
            return DependencyStatus(
                name=name,
                available=False,
                path=None,
                version=None,
                remediation_cmd=remediation or f"sudo apt-get install -y {name}",
                details=f"Binari '{name}' tidak ditemukan di PATH. {purpose}".strip(),
            )

        # Coba ambil versi
        version_str: Optional[str] = None
        try:
            res = subprocess.run(
                [found_path, version_arg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5.0,
            )
            raw = (res.stdout or res.stderr or "").strip().split("\n")[0]
            version_str = raw[:80] if raw else "unknown"
        except Exception:
            version_str = "terpasang (versi tidak dapat dibaca)"

        return DependencyStatus(
            name=name,
            available=True,
            path=found_path,
            version=version_str,
            remediation_cmd="",
            details=f"Binari '{name}' siap digunakan di {found_path}. {purpose}".strip(),
        )

    @classmethod
    def check(cls, name: str) -> DependencyStatus:
        """Memeriksa dependensi terdaftar dalam katalog KNOWN_DEPENDENCIES."""
        config = cls.KNOWN_DEPENDENCIES.get(name.lower())
        if config:
            return cls.check_binary(
                name=name,
                binaries=config.get("binaries"),
                version_arg=config.get("version_arg", "--version"),
                remediation=config.get("remediation", ""),
                purpose=config.get("purpose", ""),
            )
        return cls.check_binary(name=name)

    @classmethod
    def require(cls, names: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Memverifikasi daftar dependensi.
        Jika salah satu tidak tersedia, mengembalikan (False, json_error_str)
        yang berisi panduan remediasi yang rapi.
        """
        missing: List[DependencyStatus] = []
        for name in names:
            status = cls.check(name)
            if not status.available:
                missing.append(status)

        if not missing:
            return True, None

        payload = {
            "status": "DEPENDENCY_ERROR",
            "message": f"Dibutuhkan {len(missing)} dependensi sistem yang belum terpasang.",
            "missing_dependencies": [m.to_dict() for m in missing],
            "recommended_action": "Jalankan perintah instalasi berikut sebelum mengulang tool ini:\n"
            + "\n".join(f"  {m.remediation_cmd}" for m in missing if m.remediation_cmd),
        }
        return False, json.dumps(payload, indent=2, ensure_ascii=False)
