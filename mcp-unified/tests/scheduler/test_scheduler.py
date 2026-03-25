#!/usr/bin/env python3
"""
Test suite untuk MCP Autonomous Task Scheduler.

Usage:
    python test_scheduler.py
    python test_scheduler.py --verbose
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scheduler.database import (
    init_schema, create_job, get_job, list_jobs, update_job, delete_job,
    create_execution, update_execution, get_execution_history, get_due_jobs,
    get_running_executions, update_job_next_run
)
from scheduler.templates import (
    get_template, list_templates, get_categories, create_job_from_template,
    JOB_TEMPLATES
)
from scheduler.pools import pool_manager, PriorityLevel
from scheduler.queue import scheduler_queue


class TestScheduler:
    """Test suite untuk scheduler components."""
    
    def __init__(self):
        self.test_results = []
        self.verbose = '--verbose' in sys.argv
        
    def log(self, message: str, level: str = "INFO"):
        """Log test message."""
        if self.verbose or level in ["ERROR", "SUCCESS"]:
            prefix = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}.get(level, "ℹ️")
            print(f"{prefix} {message}")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*70)
        print("MCP AUTONOMOUS TASK SCHEDULER - TEST SUITE")
        print("="*70 + "\n")
        
        # Connect to Redis
        try:
            await scheduler_queue.connect()
            self.log("Connected to Redis", "SUCCESS")
        except Exception as e:
            self.log(f"Redis connection failed: {e}", "ERROR")
            return False
        
        # Run tests
        tests = [
            ("Database Schema", self.test_database_schema),
            ("Job Templates", self.test_job_templates),
            ("Job CRUD", self.test_job_crud),
            ("Execution Lifecycle", self.test_execution_lifecycle),
            ("Concurrency Pools", self.test_concurrency_pools),
            ("Redis Queue", self.test_redis_queue),
            ("Template Integration", self.test_template_integration),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n{'─'*70}")
            print(f"TEST: {test_name}")
            print('─'*70)
            
            try:
                result = await test_func()
                if result:
                    self.log(f"✓ {test_name} PASSED", "SUCCESS")
                    passed += 1
                else:
                    self.log(f"✗ {test_name} FAILED", "ERROR")
                    failed += 1
            except Exception as e:
                self.log(f"✗ {test_name} ERROR: {e}", "ERROR")
                failed += 1
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total: {passed + failed}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print("="*70 + "\n")
        
        # Cleanup
        await scheduler_queue.disconnect()
        
        return failed == 0
    
    # ═══════════════════════════════════════════════════════════════════════
    # Database Tests
    # ═══════════════════════════════════════════════════════════════════════
    
    async def test_database_schema(self) -> bool:
        """Test database schema initialization."""
        result = await init_schema()
        
        if result["success"]:
            self.log("Database schema initialized successfully")
            return True
        else:
            self.log(f"Schema init failed: {result.get('error')}", "ERROR")
            return False
    
    async def test_job_crud(self) -> bool:
        """Test job CRUD operations."""
        test_passed = True
        
        # Create job
        result = await create_job(
            name="test_job_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            job_type="health_check",
            category="monitoring",
            schedule_type="cron",
            schedule_expr="*/5 * * * *",
            task_config={"steps": [{"tool": "run_shell", "command": "echo test"}]},
            description="Test job",
            priority=50,
            namespace="test"
        )
        
        if not result["success"]:
            self.log(f"Create job failed: {result.get('error')}", "ERROR")
            return False
        
        job_id = result["job_id"]
        self.log(f"Created job: {job_id}")
        
        # Get job
        job = await get_job(job_id)
        if not job:
            self.log("Get job failed", "ERROR")
            test_passed = False
        else:
            self.log(f"Retrieved job: {job['name']}")
        
        # List jobs
        jobs = await list_jobs(namespace="test")
        if not jobs["success"]:
            self.log("List jobs failed", "ERROR")
            test_passed = False
        else:
            self.log(f"Listed {jobs['total']} jobs in test namespace")
        
        # Update job
        update_result = await update_job(job_id, {"priority": 60})
        if not update_result["success"]:
            self.log("Update job failed", "ERROR")
            test_passed = False
        else:
            self.log("Updated job priority to 60")
        
        # Delete job
        delete_result = await delete_job(job_id)
        if not delete_result["success"]:
            self.log("Delete job failed", "ERROR")
            test_passed = False
        else:
            self.log("Deleted job successfully")
        
        return test_passed
    
    async def test_execution_lifecycle(self) -> bool:
        """Test execution lifecycle."""
        test_passed = True
        
        # Create a test job
        job_result = await create_job(
            name="test_exec_job_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            job_type="health_check",
            category="monitoring",
            schedule_type="once",
            schedule_expr="now",
            task_config={"steps": []},
            namespace="test"
        )
        
        if not job_result["success"]:
            self.log("Create job for execution test failed", "ERROR")
            return False
        
        job_id = job_result["job_id"]
        
        # Create execution
        exec_result = await create_execution(
            job_id=job_id,
            job_name="test_exec_job",
            worker_node="test"
        )
        
        if not exec_result["success"]:
            self.log("Create execution failed", "ERROR")
            test_passed = False
        else:
            execution_id = exec_result["execution_id"]
            self.log(f"Created execution: {execution_id}")
            
            # Update to running
            update_result = await update_execution(execution_id, status="running")
            if update_result["success"]:
                self.log("Marked execution as running")
            
            # Update to success
            update_result = await update_execution(
                execution_id, 
                status="success",
                output={"result": "test completed"}
            )
            if update_result["success"]:
                self.log("Marked execution as success")
            
            # Get execution history
            history = await get_execution_history(job_id=job_id)
            if history["success"]:
                self.log(f"Execution history: {len(history['executions'])} entries")
        
        # Cleanup
        await delete_job(job_id)
        
        return test_passed
    
    # ═══════════════════════════════════════════════════════════════════════
    # Template Tests
    # ═══════════════════════════════════════════════════════════════════════
    
    async def test_job_templates(self) -> bool:
        """Test job templates."""
        test_passed = True
        
        # Test get all templates
        all_templates = list_templates()
        self.log(f"Total templates: {len(all_templates)}")
        
        if len(all_templates) < 20:
            self.log(f"Expected 20+ templates, got {len(all_templates)}", "ERROR")
            test_passed = False
        
        # Test categories
        categories = get_categories()
        self.log(f"Categories: {categories}")
        
        expected_categories = ["alert", "autonomous", "monitoring", "sync", "system_maintenance"]
        for cat in expected_categories:
            if cat not in categories:
                self.log(f"Missing category: {cat}", "ERROR")
                test_passed = False
        
        # Test get specific template
        template = get_template("backup_full")
        if not template:
            self.log("Failed to get backup_full template", "ERROR")
            test_passed = False
        else:
            self.log(f"backup_full template: priority={template.priority}, pool={template.worker_pool}")
        
        # Test filter by category
        monitoring_templates = list_templates(category="monitoring")
        self.log(f"Monitoring templates: {len(monitoring_templates)}")
        
        return test_passed
    
    async def test_template_integration(self) -> bool:
        """Test creating job from template."""
        result = create_job_from_template(
            template_name="health_check",
            job_name="test_from_template_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            namespace="test",
            custom_schedule="*/10 * * * *"
        )
        
        if not result["success"]:
            self.log(f"Create from template failed: {result.get('error')}", "ERROR")
            return False
        
        config = result["config"]
        self.log(f"Generated config for: {config['name']}")
        self.log(f"  - Type: {config['job_type']}")
        self.log(f"  - Priority: {config['priority']}")
        self.log(f"  - Schedule: {config['schedule_expr']}")
        
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # Pool Tests
    # ═══════════════════════════════════════════════════════════════════════
    
    async def test_concurrency_pools(self) -> bool:
        """Test concurrency pool manager."""
        test_passed = True
        
        # Test slot acquisition
        exec_id = "test_exec_001"
        
        success, reason = await pool_manager.acquire_slot(
            execution_id=exec_id,
            job_id="test_job_1",
            job_name="Test Job 1",
            job_type="health_check",
            priority=50,
            worker_pool="default"
        )
        
        if success:
            self.log(f"✓ Acquired slot for {exec_id}")
        else:
            self.log(f"✗ Failed to acquire slot: {reason}", "ERROR")
            test_passed = False
        
        # Test stats
        stats = pool_manager.get_stats()
        self.log(f"Pool stats: {stats['running_jobs']} running, {stats['available_slots']} available")
        
        # Test duplicate guard
        success2, reason2 = await pool_manager.acquire_slot(
            execution_id=exec_id,
            job_id="test_job_2",
            job_name="Test Job 2",
            job_type="health_check",
            priority=60
        )
        
        if success2:
            self.log("✗ Duplicate execution allowed (should be blocked)", "ERROR")
            test_passed = False
        else:
            self.log(f"✓ Duplicate correctly blocked: {reason2}")
        
        # Test priority levels
        for level in PriorityLevel:
            self.log(f"  - {level.name}: range {level.min_p}-{level.max_p}, max slots {level.max_slots}")
        
        # Release slot
        await pool_manager.release_slot(exec_id)
        self.log("✓ Released slot")
        
        return test_passed
    
    # ═══════════════════════════════════════════════════════════════════════
    # Queue Tests
    # ═══════════════════════════════════════════════════════════════════════
    
    async def test_redis_queue(self) -> bool:
        """Test Redis queue operations."""
        test_passed = True
        
        # Test enqueue
        job_id = "test_queue_job_" + datetime.now().strftime("%Y%m%d%H%M%S")
        
        success = await scheduler_queue.enqueue_job(
            job_id=job_id,
            job_name="Test Queue Job",
            job_type="health_check",
            priority=50
        )
        
        if success:
            self.log(f"✓ Enqueued job: {job_id}")
        else:
            self.log("✗ Failed to enqueue job", "ERROR")
            test_passed = False
        
        # Test pending count
        count = await scheduler_queue.get_pending_count()
        self.log(f"Pending jobs: {count}")
        
        # Test peek
        pending = await scheduler_queue.peek_pending(limit=5)
        self.log(f"Peeked {len(pending)} pending jobs")
        
        # Test mark running
        exec_id = "test_exec_queue_001"
        
        success = await scheduler_queue.mark_running(
            execution_id=exec_id,
            job_id=job_id,
            job_name="Test Queue Job",
            job_type="health_check",
            priority=50
        )
        
        if success:
            self.log(f"✓ Marked as running: {exec_id}")
        else:
            self.log("✗ Failed to mark running", "ERROR")
            test_passed = False
        
        # Test running count
        running_count = await scheduler_queue.get_running_count()
        self.log(f"Running jobs: {running_count}")
        
        # Test is running check
        is_running = await scheduler_queue.is_running(exec_id)
        self.log(f"Is running check: {is_running}")
        
        # Test lock
        lock_acquired = await scheduler_queue.acquire_lock("backup_full", exec_id, ttl_seconds=60)
        if lock_acquired:
            self.log("✓ Acquired exclusive lock for backup_full")
        else:
            self.log("Lock not acquired (might be already locked)", "WARN")
        
        # Check lock
        is_locked = await scheduler_queue.is_locked("backup_full")
        self.log(f"backup_full locked: {is_locked}")
        
        # Release lock
        if lock_acquired:
            await scheduler_queue.release_lock("backup_full", exec_id)
            self.log("✓ Released lock")
        
        # Test heartbeat
        await scheduler_queue.update_heartbeat(node_id="test-node")
        heartbeat = await scheduler_queue.get_heartbeat()
        if heartbeat:
            self.log(f"✓ Heartbeat updated: {heartbeat['timestamp']}")
        
        # Test stats
        stats = await scheduler_queue.get_queue_stats()
        self.log(f"Queue stats: {stats['pending_jobs']} pending, {stats['running_jobs']} running")
        
        # Cleanup
        await scheduler_queue.mark_completed(exec_id)
        await scheduler_queue.remove_from_pending(job_id)
        
        return test_passed


async def main():
    """Main entry point."""
    tester = TestScheduler()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 ALL TESTS PASSED! Scheduler ready for integration.\n")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED. Please review errors above.\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
