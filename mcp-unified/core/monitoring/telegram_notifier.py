import logging
import os
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.credentials_path = os.getenv("TELEGRAM_CREDENTIALS_PATH")
        self._load_from_file()

    def _load_from_file(self) -> None:
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            return
        try:
            with open(self.credentials_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip() or line.strip().startswith("#"):
                        continue
                    key, _, value = line.strip().partition("=")
                    if key == "TELEGRAM_BOT_TOKEN" and not self.bot_token:
                        self.bot_token = value
                    if key == "TELEGRAM_CHAT_ID" and not self.chat_id:
                        self.chat_id = value
        except Exception as exc:
            logger.warning("Failed to read Telegram credentials file: %s", exc)

    def _is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not self._is_configured():
            logger.warning("Telegram notifier not configured")
            return {"ok": False, "error": "Telegram notifier not configured"}

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if metadata:
            payload.update(metadata)

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            return {"ok": True, "status_code": response.status_code}
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return {"ok": False, "error": str(exc)}