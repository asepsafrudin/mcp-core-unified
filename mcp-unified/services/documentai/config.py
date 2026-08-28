"""
Konfigurasi GCP & Environment untuk Document AI Service.

Membaca environment variables:
  - GCP_PROJECT_ID
  - DOCAI_LOCATION (fallback ke GCP_LOCATION, default "us")
  - DOCAI_PROCESSOR_ID
  - GOOGLE_APPLICATION_CREDENTIALS (opsional, path ke service account JSON)

Dual-runtime: dapat digunakan di Colab maupun MCP server.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


# Mapping lokasi ke endpoint API Document AI.
# Ref: https://cloud.google.com/document-ai/docs/regions
# - "us"  → documentai.googleapis.com (default)
# - "eu"  → eu-documentai.googleapis.com
# - Regional (mis. asia-southeast1) → {location}-documentai.googleapis.com
def get_api_endpoint(location: str) -> str:
    """
    Get Document AI API endpoint untuk lokasi processor.

    Args:
        location: Lokasi processor ("us", "eu", "asia-southeast1", dst).

    Returns:
        API endpoint string.
    """
    loc = (location or "us").lower()
    if loc == "us":
        return "documentai.googleapis.com"
    if loc == "eu":
        return "eu-documentai.googleapis.com"
    # Regional location
    return f"{loc}-documentai.googleapis.com"


@dataclass
class DocumentAIConfig:
    """Configuration container untuk Document AI service."""
    project_id: str
    location: str = "us"
    processor_id: str = ""
    credentials_path: Optional[str] = None
    language_hints: Optional[list] = None

    @property
    def processor_name(self) -> str:
        """Build full processor resource name."""
        if not self.processor_id:
            raise ConfigError("DOCAI_PROCESSOR_ID is not set")
        return f"projects/{self.project_id}/locations/{self.location}/processors/{self.processor_id}"

    @property
    def api_endpoint(self) -> str:
        """Get API endpoint untuk lokasi processor."""
        return get_api_endpoint(self.location)

    def validate(self) -> None:
        """Validate required configuration."""
        if not self.project_id:
            raise ConfigError("GCP_PROJECT_ID is not set. Set it in environment or .env file.")
        if not self.processor_id:
            raise ConfigError("DOCAI_PROCESSOR_ID is not set. Set it in environment or .env file.")


def load_config() -> DocumentAIConfig:
    """
    Load configuration from environment variables.

    Urutan lokasi:
      1. DOCAI_LOCATION (khusus Document AI)
      2. GCP_LOCATION (fallback)
      3. "us" (default)

    Returns:
        DocumentAIConfig with values from env.

    Raises:
        ConfigError: Jika konfigurasi wajib tidak lengkap.
    """
    location = os.getenv("DOCAI_LOCATION") or os.getenv("GCP_LOCATION") or "us"

    # Language hints: baca dari env (comma-separated), default id+en
    lang_hints_raw = os.getenv("DOCAI_LANGUAGE_HINTS", "id,en")
    language_hints = [h.strip() for h in lang_hints_raw.split(",") if h.strip()] or ["id", "en"]

    return DocumentAIConfig(
        project_id=os.getenv("GCP_PROJECT_ID", ""),
        location=location,
        processor_id=os.getenv("DOCAI_PROCESSOR_ID", ""),
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        language_hints=language_hints,
    )


def is_configured() -> bool:
    """
    Check apakah konfigurasi GCP tersedia (tanpa raise).

    Returns:
        True jika project_id dan processor_id tersedia.
    """
    cfg = load_config()
    return bool(cfg.project_id and cfg.processor_id)
