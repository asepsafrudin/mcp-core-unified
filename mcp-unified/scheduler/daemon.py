"""
MCP Autonomous Task Scheduler Daemon

Main daemon untuk menjalankan scheduled jobs dengan:
- Periodic job scanning dan execution
- Health monitoring dan heartbeat
- Graceful shutdown handling
- Recovery dari crash

Usage:
    python daemon.py              # Run daemon
    python daemon.py --status     # Check daemon status
    python daemon.py --stop       # Stop daemon gracefully
"""

import os
import sys
import json
import signal
import asyncio
import argparse
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add parent directory to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.logger import logger
from core.config import settings

# Scheduler components
from scheduler.database import init_schema, get_due_jobs
from scheduler.redis_queue import scheduler_queue
from scheduler.pools import pool_manager
from scheduler.executor import executor
from scheduler.recovery import recovery_manager
from scheduler.notifier import notification_manager as notifier


class SchedulerDaemon:
    """
    Main scheduler daemon dengan lifecycle management.
    
    Responsibilities:
    1. Initialize all scheduler components
    2. Run main loop untuk process due jobs
    3. Maintain heartbeat untuk health monitoring
    4. Handle graceful shutdown
    5. Recovery on startup
    """
    
    def __init__(self):
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._main_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.poll_interval = 30  # seconds between job scans
        self.heartbeat_interval = 30  # seconds between heartbeats
        self.stats_interval = 300  # seconds between stats logging
        
        # PID file untuk process management
        self.pid_file = Path("/tmp/mcp-scheduler.pid")
        
        logger.info("scheduler_daemon_initialized")
    
    # ═══════════════════════════════════════════════════════════════════
    # Lifecycle Methods
    # ═══════════════════════════════════════════════════════════════════
    
    async def initialize(self):
        """Initialize all scheduler components."""
        logger.info("scheduler_daemon_initializing")
        
        try:
            # 1. Initialize database schema
            schema_result = await init_schema()
            if not schema_result.get("success"):
                logger.error("schema_init_failed", error=schema_result.get("error"))
                raise RuntimeError(f"Failed to initialize schema: {schema_result.get('error')}")
            
            # 2. Connect to Redis queue
            await scheduler_queue.connect()
            
            # 3. Initialize executor
            pass # await executor.initialize()
            
            # 4. Initialize recovery manager
            pass # await recovery_manager.initialize()
            
            # 5. Initialize notifier
            pass # await notifier.initialize()
            
            # 6. Perform recovery (handle crashed jobs)
            recovery_result = await recovery_manager.check_and_recover()
            logger.info("recovery_completed", 
                       recovered=recovery_result.get("recovered_count", 0),
                       failed=recovery_result.get("failed_count", 0))
            
            logger.info("scheduler_daemon_ready")
            
        except Exception as e:
            logger.error("scheduler_daemon_init_failed", error=str(e))
            raise
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("scheduler_daemon_shutting_down")
        
        self._running = False
        self._shutdown_event.set()
        
        # Cancel background tasks
        tasks = [self._main_task, self._heartbeat_task, self._stats_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cleanup components
        try:
            pass # await executor.shutdown()
            await scheduler_queue.disconnect()
            pass # await recovery_manager.shutdown()
            pass # await notifier.shutdown()
        except Exception as e:
            logger.error("shutdown_cleanup_error", error=str(e))
        
        # Remove PID file
        if self.pid_file.exists():
            self.pid_file.unlink()
        
        logger.info("scheduler_daemon_shutdown_complete")
    
    async def run(self):
        """Main entry point untuk run daemon."""
        # Check if already running
        if self._is_already_running():
            logger.error("scheduler_daemon_already_running")
            print("❌ Scheduler daemon is already running")
            return 1
        
        # Write PID file
        self._write_pid()
        
        # Setup signal handlers
        self._setup_signals()
        
        try:
            # Initialize
            await self.initialize()
            
            self._running = True
            
            # Start background tasks
            self._main_task = asyncio.create_task(self._main_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._stats_task = asyncio.create_task(self._stats_loop())
            
            logger.info("scheduler_daemon_started")
            print("✅ MCP Scheduler Daemon started")
            print(f"   PID: {os.getpid()}")
            print(f"   Poll interval: {self.poll_interval}s")
            print(f"   Heartbeat interval: {self.heartbeat_interval}s")
            print(f"   Press Ctrl+C to stop")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
            return 0
            
        except Exception as e:
            logger.error("scheduler_daemon_run_error", error=str(e))
            traceback.print_exc()
            return 1
        finally:
            await self.shutdown()
    
    # ═══════════════════════════════════════════════════════════════════
    # Background Tasks
    # ═══════════════════════════════════════════════════════════════════
    
    async def _main_loop(self):
        """Main loop untuk scan dan execute due jobs."""
        logger.info("main_loop_started")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Process due jobs
                execution_ids = await executor.process_due_jobs()
                
                if execution_ids:
                    logger.info("jobs_processed", count=len(execution_ids))
                
                # Wait for next poll interval (dengan early exit jika shutdown)
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue loop
                
            except Exception as e:
                logger.error("main_loop_error", error=str(e))
                await asyncio.sleep(self.poll_interval)
        
        logger.info("main_loop_stopped")
    
    async def _heartbeat_loop(self):
        """Heartbeat loop untuk health monitoring."""
        logger.info("heartbeat_loop_started")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Update heartbeat
                await scheduler_queue.update_heartbeat(node_id="scheduler-main")
                
                # Wait for next heartbeat
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    pass
                
            except Exception as e:
                logger.error("heartbeat_loop_error", error=str(e))
                await asyncio.sleep(self.heartbeat_interval)
        
        logger.info("heartbeat_loop_stopped")
    
    async def _stats_loop(self):
        """Stats logging loop."""
        logger.info("stats_loop_started")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Get stats
                queue_stats = await scheduler_queue.get_queue_stats()
                pool_stats = pool_manager.get_stats()
                
                # Log stats
                logger.info("scheduler_stats",
                           pending=queue_stats.get("pending_jobs", 0),
                           running=queue_stats.get("running_jobs", 0),
                           available_slots=pool_stats.get("available_slots", 0))
                
                # Wait for next stats interval
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.stats_interval
                    )
                except asyncio.TimeoutError:
                    pass
                
            except Exception as e:
                logger.error("stats_loop_error", error=str(e))
                await asyncio.sleep(self.stats_interval)
        
        logger.info("stats_loop_stopped")
    
    # ═══════════════════════════════════════════════════════════════════
    # Signal Handling
    # ═══════════════════════════════════════════════════════════════════
    
    def _setup_signals(self):
        """Setup signal handlers untuk graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info("signal_received", signal=signum)
            self._shutdown_event.set()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    # ═══════════════════════════════════════════════════════════════════
    # PID File Management
    # ═══════════════════════════════════════════════════════════════════
    
    def _is_already_running(self) -> bool:
        """Check if daemon is already running."""
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            # PID file exists tapi process tidak ada
            self.pid_file.unlink()
            return False
    
    def _write_pid(self):
        """Write PID to file."""
        self.pid_file.write_text(str(os.getpid()))
    
    # ═══════════════════════════════════════════════════════════════════
    # CLI Commands
    # ═══════════════════════════════════════════════════════════════════
    
    def status(self) -> int:
        """Check daemon status."""
        if self._is_already_running():
            pid = int(self.pid_file.read_text().strip())
            print(f"✅ MCP Scheduler Daemon is running")
            print(f"   PID: {pid}")
            
            # Try to get health info dari Redis
            try:
                import redis
                r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                heartbeat = r.get("mcp:scheduler:heartbeat")
                if heartbeat:
                    data = json.loads(heartbeat)
                    print(f"   Last heartbeat: {data.get('timestamp', 'unknown')}")
                
                pending = r.zcard("mcp:scheduler:pending")
                running = r.hlen("mcp:scheduler:running")
                print(f"   Pending jobs: {pending}")
                print(f"   Running jobs: {running}")
                r.close()
            except Exception as e:
                print(f"   (Could not retrieve queue stats: {e})")
            
            return 0
        else:
            print("❌ MCP Scheduler Daemon is not running")
            return 1
    
    def stop(self) -> int:
        """Stop running daemon."""
        if not self._is_already_running():
            print("❌ Scheduler daemon is not running")
            return 1
        
        pid = int(self.pid_file.read_text().strip())
        print(f"🛑 Stopping MCP Scheduler Daemon (PID: {pid})...")
        
        try:
            os.kill(pid, signal.SIGTERM)
            print("✅ Stop signal sent")
            return 0
        except ProcessLookupError:
            print("⚠️  Process not found, cleaning up PID file")
            self.pid_file.unlink()
            return 1
        except Exception as e:
            print(f"❌ Error stopping daemon: {e}")
            return 1


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Autonomous Task Scheduler Daemon"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Check daemon status"
    )
    parser.add_argument(
        "--stop", "-x",
        action="store_true",
        help="Stop running daemon"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Job poll interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=30,
        help="Heartbeat interval in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    daemon = SchedulerDaemon()
    
    # Override config
    if args.poll_interval:
        daemon.poll_interval = args.poll_interval
    if args.heartbeat_interval:
        daemon.heartbeat_interval = args.heartbeat_interval
    
    # Handle commands
    if args.status:
        return daemon.status()
    elif args.stop:
        return daemon.stop()
    else:
        # Run daemon
        try:
            return asyncio.run(daemon.run())
        except KeyboardInterrupt:
            print("\n👋 Interrupted by user")
            return 0


if __name__ == "__main__":
    sys.exit(main())
