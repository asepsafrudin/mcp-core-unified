"""
Daily Report Service v2 - Multi-Channel Notifications (Telegram & WhatsApp).
"""

import sys
import os
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from integrations.telegram.services.daily_report_service import DailyReportService
from integrations.common.notifications import get_notification_service

async def run_daily_report_v2():
    """
    Generate daily report using existing logic but send via common notification service.
    """
    print(f"🚀 Memulai Daily Report v2 pada {datetime.now()}")
    
    # Use the existing analyzer logic from DailyReportService
    old_service = DailyReportService()
    
    # Generate the report content
    message, reports = await old_service.generate_report()
    
    # Save the JSON record (keep compatibility)
    old_service.save_report_json(reports)
    
    # Use unified notification service for multi-channel
    notifier = get_notification_service()
    
    print("📤 Mengirim ke semua channel...")
    results = await notifier.notify_all(message)
    
    for channel, success in results.items():
        status = "✅ BERHASIL" if success else "❌ GAGAL"
        print(f"   • {channel.capitalize()}: {status}")
        
    return all(results.values())

if __name__ == "__main__":
    success = asyncio.run(run_daily_report_v2())
    sys.exit(0 if success else 1)
