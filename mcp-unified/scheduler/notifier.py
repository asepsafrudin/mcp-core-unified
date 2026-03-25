"""
Notification System untuk MCP Autonomous Task Scheduler.

Integrasi dengan:
- Telegram Bot
- VS Code Webhook
- Notification templates
- Rate limiting
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from scheduler.database import log_notification, update_notification_status
from observability.logger import logger

# Try to import existing integrations
try:
    from integrations.telegram.telegram_tool import telegram_notifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("notifier_telegram_not_available")


@dataclass
class NotificationConfig:
    """Configuration untuk notification."""
    channels: List[str]  # telegram, vscode, webhook
    on_start: bool = False
    on_success: bool = True
    on_failure: bool = True
    on_recovery: bool = True


class NotificationManager:
    """
    Manages notifications untuk scheduler events.
    
    Features:
    - Multi-channel (Telegram, VS Code)
    - Template-based messages
    - Rate limiting
    - Notification history
    """
    
    def __init__(self):
        self.rate_limits: Dict[str, datetime] = {}  # channel -> last_sent
        self.min_interval_seconds = 60  # Minimum interval between notifications
        
    async def notify_job_start(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        execution_id: str,
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """Send job started notification."""
        if not channels:
            channels = ["telegram"]
        
        message = f"🚀 Job Started\n\n" \
                  f"Name: {job_name}\n" \
                  f"Type: {job_type}\n" \
                  f"Execution ID: {execution_id[:8]}...\n" \
                  f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return await self._send_notification(
            job_id=job_id,
            execution_id=execution_id,
            channels=channels,
            notification_type="start",
            message=message,
            content={"job_name": job_name, "job_type": job_type}
        )
    
    async def notify_job_success(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        execution_id: str,
        duration_ms: int,
        results: List[Dict],
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """Send job success notification."""
        if not channels:
            channels = ["telegram"]
        
        # Calculate success rate
        success_count = sum(1 for r in results if r.get("success"))
        total_count = len(results)
        
        duration_str = self._format_duration(duration_ms)
        
        message = f"✅ Job Completed Successfully\n\n" \
                  f"Name: {job_name}\n" \
                  f"Type: {job_type}\n" \
                  f"Duration: {duration_str}\n" \
                  f"Steps: {success_count}/{total_count} successful\n" \
                  f"Completed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return await self._send_notification(
            job_id=job_id,
            execution_id=execution_id,
            channels=channels,
            notification_type="success",
            message=message,
            content={
                "job_name": job_name,
                "job_type": job_type,
                "duration_ms": duration_ms,
                "success_rate": f"{success_count}/{total_count}"
            }
        )
    
    async def notify_job_failure(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        execution_id: str,
        error_message: str,
        retry_count: int = 0,
        max_retries: int = 3,
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """Send job failure notification."""
        if not channels:
            channels = ["telegram", "vscode"]
        
        # Truncate error message jika terlalu panjang
        error_preview = error_message[:200] + "..." if len(error_message) > 200 else error_message
        
        retry_info = f"\nRetry: {retry_count}/{max_retries}" if retry_count > 0 else ""
        
        message = f"❌ Job Failed\n\n" \
                  f"Name: {job_name}\n" \
                  f"Type: {job_type}\n" \
                  f"Error: {error_preview}" \
                  f"{retry_info}\n" \
                  f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return await self._send_notification(
            job_id=job_id,
            execution_id=execution_id,
            channels=channels,
            notification_type="failure",
            message=message,
            content={
                "job_name": job_name,
                "job_type": job_type,
                "error": error_message,
                "retry_count": retry_count
            },
            priority="high"
        )
    
    async def notify_recovery(
        self,
        job_id: str,
        job_name: str,
        old_execution_id: str,
        new_execution_id: str,
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """Send recovery notification."""
        if not channels:
            channels = ["telegram", "vscode"]
        
        message = f"🔄 Job Recovered After Crash\n\n" \
                  f"Name: {job_name}\n" \
                  f"Old Execution: {old_execution_id[:8]}...\n" \
                  f"New Execution: {new_execution_id[:8]}...\n" \
                  f"Recovered: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return await self._send_notification(
            job_id=job_id,
            execution_id=new_execution_id,
            channels=channels,
            notification_type="recovery",
            message=message,
            content={
                "job_name": job_name,
                "old_execution_id": old_execution_id,
                "new_execution_id": new_execution_id
            },
            priority="high"
        )
    
    async def _send_notification(
        self,
        job_id: str,
        execution_id: str,
        channels: List[str],
        notification_type: str,
        message: str,
        content: Dict[str, Any],
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Send notification ke multiple channels.
        
        Args:
            job_id: Job ID
            execution_id: Execution ID
            channels: List of channels (telegram, vscode)
            notification_type: start, success, failure, recovery
            message: Message content
            content: Structured content untuk logging
            priority: normal atau high
        """
        results = {}
        
        for channel in channels:
            # Check rate limit
            if not self._check_rate_limit(channel):
                logger.warning("notification_rate_limited",
                             channel=channel,
                             job_id=job_id)
                results[channel] = {"success": False, "error": "Rate limited"}
                continue
            
            # Log notification attempt
            log_result = await log_notification(
                job_id=job_id,
                execution_id=execution_id,
                channel=channel,
                notification_type=notification_type,
                content=content
            )
            
            notification_id = log_result.get("notification_id")
            
            # Send based on channel
            try:
                if channel == "telegram" and TELEGRAM_AVAILABLE:
                    success = await self._send_telegram(message, priority)
                elif channel == "vscode":
                    success = await self._send_vscode_webhook(job_id, execution_id, message, notification_type)
                else:
                    # Channel not available, mark as failed
                    success = False
                    logger.warning("notification_channel_not_available",
                                 channel=channel)
                
                # Update log status
                status = "sent" if success else "failed"
                await update_notification_status(notification_id, status)
                
                results[channel] = {"success": success}
                
                if success:
                    self._update_rate_limit(channel)
                
            except Exception as e:
                logger.error("notification_send_failed",
                           channel=channel,
                           error=str(e))
                await update_notification_status(notification_id, "failed", str(e))
                results[channel] = {"success": False, "error": str(e)}
        
        # Overall success if at least one channel succeeded
        any_success = any(r.get("success") for r in results.values())
        
        return {
            "success": any_success,
            "channels": results,
            "notification_id": notification_id
        }
    
    async def _send_telegram(self, message: str, priority: str = "normal") -> bool:
        """
        Send notification via Telegram Bot API.
        
        Requires environment variables:
        - TELEGRAM_BOT_TOKEN: Bot token dari BotFather
        - TELEGRAM_CHAT_ID: Chat ID untuk menerima notifikasi
        """
        import os
        import aiohttp
        
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            # Try to use telegram_tool jika tersedia
            if TELEGRAM_AVAILABLE and telegram_notifier:
                try:
                    await telegram_notifier.send_message(message)
                    logger.info("telegram_notification_sent_via_tool", priority=priority)
                    return True
                except Exception as e:
                    logger.error("telegram_tool_send_failed", error=str(e))
                    return False
            else:
                logger.warning("telegram_not_configured",
                             has_token=bool(bot_token),
                             has_chat_id=bool(chat_id))
                return False
        
        try:
            # Build Telegram API URL
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            # Format message dengan priority indicator
            if priority == "high":
                formatted_message = f"🔴 *HIGH PRIORITY*\n\n{message}"
            else:
                formatted_message = message
            
            payload = {
                "chat_id": chat_id,
                "text": formatted_message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            logger.info("telegram_notification_sent",
                                      priority=priority,
                                      message_id=result.get("result", {}).get("message_id"))
                            return True
                        else:
                            logger.error("telegram_api_error",
                                       error=result.get("description"))
                            return False
                    else:
                        logger.error("telegram_http_error",
                                   status=response.status,
                                   body=await response.text())
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("telegram_send_timeout")
            return False
        except Exception as e:
            logger.error("telegram_send_failed", error=str(e))
            return False
    
    async def _send_vscode_webhook(
        self,
        job_id: str,
        execution_id: str,
        message: str,
        notification_type: str
    ) -> bool:
        """Send notification via VS Code webhook."""
        try:
            # VS Code webhook implementation
            # This would send ke VS Code extension listening pada port tertentu
            
            import aiohttp
            
            webhook_url = "http://localhost:3000/mcp-scheduler/webhook"
            
            payload = {
                "type": notification_type,
                "job_id": job_id,
                "execution_id": execution_id,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    success = response.status == 200
                    
                    if success:
                        logger.info("vscode_webhook_sent")
                    else:
                        logger.warning("vscode_webhook_failed",
                                     status=response.status)
                    
                    return success
                    
        except Exception as e:
            logger.error("vscode_webhook_error", error=str(e))
            return False
    
    def _check_rate_limit(self, channel: str) -> bool:
        """Check if channel is rate limited."""
        last_sent = self.rate_limits.get(channel)
        
        if not last_sent:
            return True
        
        elapsed = (datetime.now(timezone.utc) - last_sent).total_seconds()
        return elapsed >= self.min_interval_seconds
    
    def _update_rate_limit(self, channel: str):
        """Update last sent time untuk channel."""
        self.rate_limits[channel] = datetime.now(timezone.utc)
    
    def _format_duration(self, duration_ms: int) -> str:
        """Format duration milliseconds ke human readable."""
        if duration_ms < 1000:
            return f"{duration_ms}ms"
        elif duration_ms < 60000:
            return f"{duration_ms / 1000:.1f}s"
        else:
            minutes = duration_ms / 60000
            return f"{minutes:.1f}m"


# Global instance
notification_manager = NotificationManager()


# Convenience functions
async def notify_job_start(*args, **kwargs) -> Dict[str, Any]:
    """Global notify job start."""
    return await notification_manager.notify_job_start(*args, **kwargs)


async def notify_job_success(*args, **kwargs) -> Dict[str, Any]:
    """Global notify job success."""
    return await notification_manager.notify_job_success(*args, **kwargs)


async def notify_job_failure(*args, **kwargs) -> Dict[str, Any]:
    """Global notify job failure."""
    return await notification_manager.notify_job_failure(*args, **kwargs)


async def notify_recovery(*args, **kwargs) -> Dict[str, Any]:
    """Global notify recovery."""
    return await notification_manager.notify_recovery(*args, **kwargs)
