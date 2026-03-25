"""
Job Templates untuk MCP Autonomous Task Scheduler.

Pre-defined job configurations untuk berbagai use cases.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class JobTemplate:
    """Template untuk scheduled job."""
    name: str
    category: str
    priority: int
    schedule_type: str
    schedule_expr: str
    description: str
    max_concurrent: int = 1
    exclusive_lock: bool = False
    worker_pool: str = "default"
    max_retries: int = 3
    retry_delay_seconds: int = 300
    task_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template ke dictionary."""
        return {
            "job_type": self.name,
            "category": self.category,
            "priority": self.priority,
            "schedule_type": self.schedule_type,
            "schedule_expr": self.schedule_expr,
            "description": self.description,
            "max_concurrent": self.max_concurrent,
            "exclusive_lock": self.exclusive_lock,
            "worker_pool": self.worker_pool,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "task_config": self.task_config
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 SYSTEM MAINTENANCE (Critical - High Priority)
# ═══════════════════════════════════════════════════════════════════════════════

JOB_TEMPLATES = {
    # ─────────────────────────────────────────────────────────────────────────
    # Backup Jobs
    # ─────────────────────────────────────────────────────────────────────────
    "backup_full": JobTemplate(
        name="backup_full",
        category="system_maintenance",
        priority=95,
        schedule_type="cron",
        schedule_expr="0 2 * * *",  # Daily at 02:00
        description="Full system backup - PostgreSQL, Redis, MCP files",
        max_concurrent=1,
        exclusive_lock=True,
        worker_pool="io",
        task_config={
            "steps": [
                {
                    "name": "backup_postgresql",
                    "tool": "run_shell",
                    "command": "pg_dump -h $POSTGRES_SERVER -U $POSTGRES_USER $POSTGRES_DB > /home/aseps/MCP/backups/db_$(date +%Y%m%d_%H%M%S).sql",
                    "timeout": 300
                },
                {
                    "name": "backup_redis",
                    "tool": "run_shell",
                    "command": "redis-cli SAVE && cp /var/lib/redis/dump.rdb /home/aseps/MCP/backups/redis_$(date +%Y%m%d_%H%M%S).rdb",
                    "timeout": 60
                },
                {
                    "name": "backup_mcp_files",
                    "tool": "run_shell",
                    "command": "tar -czf /home/aseps/MCP/backups/mcp_full_$(date +%Y%m%d_%H%M%S).tar.gz -C /home/aseps MCP --exclude='*.pyc' --exclude='__pycache__' --exclude='venv*' --exclude='.git'",
                    "timeout": 600
                },
                {
                    "name": "cleanup_old_backups",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP/backups -name '*.tar.gz' -mtime +7 -delete && find /home/aseps/MCP/backups -name '*.sql' -mtime +14 -delete",
                    "timeout": 30
                },
                {
                    "name": "save_backup_memory",
                    "tool": "memory_save",
                    "key": "backup:last_full",
                    "content": "Full backup completed at {timestamp}"
                }
            ],
            "notification": {
                "on_success": True,
                "on_failure": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    "backup_incremental": JobTemplate(
        name="backup_incremental",
        category="system_maintenance",
        priority=80,
        schedule_type="cron",
        schedule_expr="0 */6 * * *",  # Every 6 hours
        description="Incremental file backup dengan rsync",
        max_concurrent=1,
        exclusive_lock=True,
        worker_pool="io",
        task_config={
            "steps": [
                {
                    "name": "rsync_incremental",
                    "tool": "run_shell",
                    "command": "rsync -av --delete --link-dest=/home/aseps/MCP/backups/latest /home/aseps/MCP /home/aseps/MCP/backups/incremental/$(date +%Y%m%d_%H%M%S)/",
                    "timeout": 300
                },
                {
                    "name": "update_latest_symlink",
                    "tool": "run_shell",
                    "command": "ln -sfn /home/aseps/MCP/backups/incremental/$(date +%Y%m%d_%H%M%S) /home/aseps/MCP/backups/latest",
                    "timeout": 10
                }
            ],
            "notification": {
                "on_success": False,
                "on_failure": True
            }
        }
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # Database Maintenance
    # ─────────────────────────────────────────────────────────────────────────
    "db_vacuum": JobTemplate(
        name="db_vacuum",
        category="system_maintenance",
        priority=85,
        schedule_type="cron",
        schedule_expr="0 3 * * 0",  # Weekly Sunday 03:00
        description="PostgreSQL vacuum, analyze, dan reindex",
        max_concurrent=1,
        worker_pool="io",
        task_config={
            "steps": [
                {
                    "name": "vacuum_analyze",
                    "tool": "run_shell",
                    "command": "psql -h $POSTGRES_SERVER -U $POSTGRES_USER -d $POSTGRES_DB -c 'VACUUM ANALYZE;'",
                    "timeout": 1800
                },
                {
                    "name": "reindex_database",
                    "tool": "run_shell",
                    "command": "psql -h $POSTGRES_SERVER -U $POSTGRES_USER -d $POSTGRES_DB -c 'REINDEX DATABASE $POSTGRES_DB;'",
                    "timeout": 3600
                }
            ]
        }
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # Log Management
    # ─────────────────────────────────────────────────────────────────────────
    "log_rotate": JobTemplate(
        name="log_rotate",
        category="system_maintenance",
        priority=70,
        schedule_type="cron",
        schedule_expr="0 4 * * *",  # Daily 04:00
        description="Compress dan archive logs, cleanup old files",
        max_concurrent=1,
        worker_pool="io",
        task_config={
            "steps": [
                {
                    "name": "compress_old_logs",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP/logs -name '*.log' -mtime +1 -exec gzip {} \\;",
                    "timeout": 120
                },
                {
                    "name": "cleanup_archive_logs",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP/logs -name '*.gz' -mtime +30 -delete",
                    "timeout": 60
                },
                {
                    "name": "cleanup_temp_files",
                    "tool": "run_shell",
                    "command": "find /tmp -name 'mcp_*' -mtime +7 -delete",
                    "timeout": 60
                }
            ]
        }
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # Auto Cleanup
    # ─────────────────────────────────────────────────────────────────────────
    "disk_cleanup": JobTemplate(
        name="disk_cleanup",
        category="system_maintenance",
        priority=100,  # Highest - auto trigger when disk > 80%
        schedule_type="event",
        schedule_expr="disk_usage > 80",
        description="Auto cleanup when disk usage exceeds 80%",
        max_concurrent=1,
        worker_pool="io",
        task_config={
            "auto_trigger": True,
            "condition": {
                "type": "disk_usage",
                "threshold": 80,
                "path": "/"
            },
            "steps": [
                {
                    "name": "docker_cleanup",
                    "tool": "run_shell",
                    "command": "docker system prune -f --volumes",
                    "timeout": 300
                },
                {
                    "name": "cleanup_tmp",
                    "tool": "run_shell",
                    "command": "find /tmp -type f -atime +3 -delete",
                    "timeout": 60
                },
                {
                    "name": "cleanup_logs",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP/logs -name '*.gz' -mtime +7 -delete",
                    "timeout": 60
                },
                {
                    "name": "cleanup_cache",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true",
                    "timeout": 120
                }
            ],
            "notification": {
                "on_start": True,
                "on_success": True,
                "on_failure": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # SSL Certificate
    # ─────────────────────────────────────────────────────────────────────────
    "cert_renewal": JobTemplate(
        name="cert_renewal",
        category="system_maintenance",
        priority=90,
        schedule_type="cron",
        schedule_expr="0 2 1 * *",  # Monthly 1st at 02:00
        description="SSL certificate check dan renewal",
        max_concurrent=1,
        worker_pool="network",
        task_config={
            "steps": [
                {
                    "name": "check_cert_expiry",
                    "tool": "run_shell",
                    "command": "certbot certificates 2>/dev/null | grep -E 'Expiry|Domain' || echo 'No certbot certificates found'",
                    "timeout": 30
                },
                {
                    "name": "renew_certs",
                    "tool": "run_shell",
                    "command": "certbot renew --quiet --no-self-upgrade",
                    "timeout": 300
                },
                {
                    "name": "reload_nginx",
                    "tool": "run_shell",
                    "command": "sudo systemctl reload nginx || true",
                    "timeout": 30
                }
            ],
            "notification": {
                "on_success": True,
                "on_failure": True
            }
        }
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 📊 MONITORING & REPORTING (Scheduled - Medium Priority)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    "health_check": JobTemplate(
        name="health_check",
        category="monitoring",
        priority=60,
        schedule_type="cron",
        schedule_expr="*/15 * * * *",  # Every 15 minutes
        description="System health snapshot - MCP, Redis, PostgreSQL",
        max_concurrent=3,
        worker_pool="default",
        task_config={
            "steps": [
                {
                    "name": "check_mcp_server",
                    "tool": "run_shell",
                    "command": "curl -sf http://localhost:8000/health && echo 'MCP: OK' || echo 'MCP: DOWN'",
                    "timeout": 10
                },
                {
                    "name": "check_redis",
                    "tool": "run_shell",
                    "command": "redis-cli ping && echo 'Redis: OK' || echo 'Redis: DOWN'",
                    "timeout": 5
                },
                {
                    "name": "check_postgresql",
                    "tool": "run_shell",
                    "command": "pg_isready -h $POSTGRES_SERVER && echo 'PostgreSQL: OK' || echo 'PostgreSQL: DOWN'",
                    "timeout": 5
                },
                {
                    "name": "check_disk_space",
                    "tool": "run_shell",
                    "command": "df -h / | tail -1 | awk '{print \"Disk: \" $5 \" used\"}'",
                    "timeout": 5
                },
                {
                    "name": "check_memory",
                    "tool": "run_shell",
                    "command": "free -h | grep Mem | awk '{print \"Memory: \" $3 \"/\" $2 \" used\"}'",
                    "timeout": 5
                },
                {
                    "name": "save_health_memory",
                    "tool": "memory_save",
                    "key": "health:check:{timestamp}",
                    "content": "Health check completed at {timestamp}"
                }
            ],
            "notification": {
                "on_failure": True,
                "channels": ["telegram"]
            }
        }
    ),
    
    "compliance_scan": JobTemplate(
        name="compliance_scan",
        category="monitoring",
        priority=65,
        schedule_type="cron",
        schedule_expr="0 9 * * *",  # Daily 09:00
        description="Security audit dan compliance scan",
        max_concurrent=1,
        worker_pool="cpu",
        task_config={
            "steps": [
                {
                    "name": "check_world_writable",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP -type f -perm /o+w -ls 2>/dev/null | head -20 || echo 'No world-writable files found'",
                    "timeout": 60
                },
                {
                    "name": "check_env_permissions",
                    "tool": "run_shell",
                    "command": "find /home/aseps/MCP -name '.env*' -type f ! -perm 600 -ls 2>/dev/null || echo 'All .env files have correct permissions'",
                    "timeout": 30
                },
                {
                    "name": "check_ssh_keys",
                    "tool": "run_shell",
                    "command": "find /home/aseps -name 'id_*' -type f ! -perm 600 2>/dev/null | head -5 || echo 'SSH keys OK'",
                    "timeout": 30
                },
                {
                    "name": "check_sudoers",
                    "tool": "run_shell",
                    "command": "sudo -l -U aseps 2>/dev/null | head -10 || echo 'No sudo access'",
                    "timeout": 10
                }
            ],
            "notification": {
                "on_success": True,
                "on_failure": True
            }
        }
    ),
    
    "dependency_check": JobTemplate(
        name="dependency_check",
        category="monitoring",
        priority=55,
        schedule_type="cron",
        schedule_expr="0 10 * * 1",  # Weekly Monday 10:00
        description="Check outdated Python packages",
        max_concurrent=1,
        worker_pool="network",
        task_config={
            "steps": [
                {
                    "name": "check_outdated",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP/mcp-unified && pip list --outdated --format=columns 2>/dev/null | head -20 || echo 'Could not check outdated packages'",
                    "timeout": 120
                },
                {
                    "name": "check_security_advisories",
                    "tool": "run_shell",
                    "command": "pip audit --format=json 2>/dev/null | jq '.vulnerabilities | length' || echo 'pip audit not installed'",
                    "timeout": 180
                }
            ]
        }
    ),
    
    "performance_report": JobTemplate(
        name="performance_report",
        category="monitoring",
        priority=50,
        schedule_type="cron",
        schedule_expr="0 8 * * *",  # Daily 08:00
        description="Daily metrics summary report",
        max_concurrent=1,
        worker_pool="default",
        task_config={
            "steps": [
                {
                    "name": "system_load",
                    "tool": "run_shell",
                    "command": "uptime",
                    "timeout": 5
                },
                {
                    "name": "memory_usage",
                    "tool": "run_shell",
                    "command": "free -h",
                    "timeout": 5
                },
                {
                    "name": "disk_usage",
                    "tool": "run_shell",
                    "command": "df -h",
                    "timeout": 5
                },
                {
                    "name": "top_processes",
                    "tool": "run_shell",
                    "command": "ps aux --sort=-%cpu | head -10",
                    "timeout": 5
                },
                {
                    "name": "mcp_connections",
                    "tool": "run_shell",
                    "command": "netstat -an 2>/dev/null | grep ':8000' | wc -l || ss -an | grep ':8000' | wc -l",
                    "timeout": 5
                }
            ],
            "notification": {
                "on_success": True,
                "channels": ["telegram"]
            }
        }
    ),
    
    "cost_analysis": JobTemplate(
        name="cost_analysis",
        category="monitoring",
        priority=40,
        schedule_type="cron",
        schedule_expr="0 9 1 * *",  # Monthly 1st at 09:00
        description="Resource usage cost analysis",
        max_concurrent=1,
        worker_pool="default",
        task_config={
            "steps": [
                {
                    "name": "disk_usage_trend",
                    "tool": "run_shell",
                    "command": "du -sh /home/aseps/MCP/* 2>/dev/null | sort -hr | head -10",
                    "timeout": 60
                },
                {
                    "name": "db_size_analysis",
                    "tool": "run_shell",
                    "command": "psql -h $POSTGRES_SERVER -U $POSTGRES_USER -d $POSTGRES_DB -c \"SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;\" 2>/dev/null || echo 'Could not query DB size'",
                    "timeout": 30
                }
            ],
            "notification": {
                "on_success": True
            }
        }
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔄 SYNC & REPLICATION (Event-driven - Variable Priority)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    "mirror_repos": JobTemplate(
        name="mirror_repos",
        category="sync",
        priority=55,
        schedule_type="cron",
        schedule_expr="0 */4 * * *",  # Every 4 hours
        description="Mirror code repositories ke backup",
        max_concurrent=2,
        worker_pool="network",
        task_config={
            "steps": [
                {
                    "name": "fetch_all_remotes",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && git fetch --all --prune 2>&1 | head -20",
                    "timeout": 120
                },
                {
                    "name": "update_mirror",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && git push --mirror https://backup-server/mcp-mirror.git 2>&1 || echo 'Mirror push completed or no mirror configured'",
                    "timeout": 180
                }
            ],
            "notification": {
                "on_failure": True
            }
        }
    ),
    
    "ltm_sync_remote": JobTemplate(
        name="ltm_sync_remote",
        category="sync",
        priority=45,
        schedule_type="event",
        schedule_expr="on_ltm_change",
        description="Distributed LTM sync ke remote nodes",
        max_concurrent=1,
        worker_pool="network",
        task_config={
            "auto_trigger": True,
            "event_trigger": "ltm_change",
            "steps": [
                {
                    "name": "sync_ltm",
                    "tool": "run_shell",
                    "command": "rsync -avz /home/aseps/MCP/.ltm_memory.json backup-server:/home/aseps/MCP/.ltm_memory.json 2>&1 || echo 'LTM sync attempted'",
                    "timeout": 60
                }
            ]
        }
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🤖 AUTONOMOUS TASKS (AI-driven - Context Priority)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    "auto_heal_review": JobTemplate(
        name="auto_heal_review",
        category="autonomous",
        priority=75,
        schedule_type="event",
        schedule_expr="on_error",
        description="AI analysis dan auto-fix error patterns",
        max_concurrent=1,
        worker_pool="cpu",
        task_config={
            "auto_trigger": True,
            "event_trigger": "execution_failure",
            "use_planner": True,
            "use_self_healing": True,
            "prompt": """
            Analyze recent execution failures in logs.
            Identify patterns dan root causes.
            Suggest atau apply fixes untuk common issues.
            Focus on: syntax errors, missing dependencies, config issues.
            """,
            "steps": [
                {
                    "name": "analyze_errors",
                    "tool": "memory_search",
                    "query": "execution failed error",
                    "limit": 10
                },
                {
                    "name": "heal_and_fix",
                    "tool": "self_heal",
                    "mode": "auto"
                }
            ],
            "notification": {
                "on_start": True,
                "on_success": True,
                "on_failure": True
            }
        }
    ),
    
    "smart_cleanup": JobTemplate(
        name="smart_cleanup",
        category="autonomous",
        priority=40,
        schedule_type="cron",
        schedule_expr="0 3 * * 0",  # Weekly Sunday 03:00
        description="AI-suggested cleanup tasks berdasarkan usage patterns",
        max_concurrent=1,
        worker_pool="cpu",
        task_config={
            "use_planner": True,
            "prompt": """
            Review workspace dan identify cleanup opportunities:
            1. Large files yang tidak diakses dalam 30 hari
            2. Duplicate files
            3. Unused Python cache files
            4. Old temporary files
            5. Orphaned Docker images/volumes
            Generate cleanup plan dan execute safely.
            """,
            "steps": [
                {
                    "name": "analyze_workspace",
                    "tool": "memory_search",
                    "query": "workspace cleanup large files unused",
                    "limit": 5
                },
                {
                    "name": "create_cleanup_plan",
                    "tool": "create_plan",
                    "objective": "Analyze workspace and create safe cleanup plan"
                },
                {
                    "name": "execute_cleanup",
                    "tool": "execute_plan",
                    "dry_run": True  # Safety first
                }
            ]
        }
    ),
    
    "doc_auto_update": JobTemplate(
        name="doc_auto_update",
        category="autonomous",
        priority=35,
        schedule_type="event",
        schedule_expr="on_code_change",
        description="Auto-update dokumentasi pada code changes",
        max_concurrent=1,
        worker_pool="cpu",
        task_config={
            "auto_trigger": True,
            "event_trigger": "git_push",
            "use_planner": True,
            "prompt": """
            Check recent code changes dan update related documentation:
            1. Update API docs jika endpoints berubah
            2. Update README jika fitur baru ditambahkan
            3. Update CHANGELOG
            4. Generate docstrings untuk new functions
            """,
            "steps": [
                {
                    "name": "check_git_diff",
                    "tool": "run_shell",
                    "command": r"cd /home/aseps/MCP && git diff HEAD~5 --name-only | grep -E '\.(py|md)$' | head -20",
                    "timeout": 10
                },
                {
                    "name": "update_docs",
                    "tool": "create_plan",
                    "objective": "Update documentation based on recent code changes"
                }
            ]
        }
    ),
    
    "test_auto_gen": JobTemplate(
        name="test_auto_gen",
        category="autonomous",
        priority=35,
        schedule_type="event",
        schedule_expr="on_commit",
        description="Generate missing tests untuk new code",
        max_concurrent=1,
        worker_pool="cpu",
        task_config={
            "auto_trigger": True,
            "event_trigger": "git_commit",
            "use_planner": True,
            "prompt": """
            Identify new functions/classes tanpa tests dan generate test cases.
            Focus on: unit tests untuk business logic, integration tests untuk APIs.
            """,
            "steps": [
                {
                    "name": "find_untested_code",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && find . -name '*.py' -not -path './venv*' -not -path './.git*' | head -20",
                    "timeout": 30
                },
                {
                    "name": "generate_tests",
                    "tool": "create_plan",
                    "objective": "Generate missing test cases for recent code changes"
                }
            ]
        }
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🚨 ALERT & RESPONSE (Trigger-based - Highest Priority)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    "incident_response": JobTemplate(
        name="incident_response",
        category="alert",
        priority=100,
        schedule_type="event",
        schedule_expr="on_health_fail",
        description="Auto remediation pada system failure",
        max_concurrent=1,
        exclusive_lock=True,
        worker_pool="default",
        task_config={
            "auto_trigger": True,
            "event_trigger": "health_check_failure",
            "use_planner": True,
            "use_self_healing": True,
            "prompt": """
            Critical system failure detected. Execute immediate remediation:
            1. Restart failed services
            2. Clear stuck processes
            3. Free up resources jika necessary
            4. Escalate ke human jika auto-fix fails
            """,
            "steps": [
                {
                    "name": "diagnose_failure",
                    "tool": "run_shell",
                    "command": "systemctl status mcp-unified redis postgresql 2>&1 | head -30",
                    "timeout": 10
                },
                {
                    "name": "restart_services",
                    "tool": "run_shell",
                    "command": "sudo systemctl restart mcp-unified && echo 'MCP restarted' || echo 'Failed to restart MCP'",
                    "timeout": 60
                },
                {
                    "name": "verify_recovery",
                    "tool": "run_shell",
                    "command": "sleep 5 && curl -sf http://localhost:8000/health && echo 'Recovery successful' || echo 'Recovery failed'",
                    "timeout": 30
                }
            ],
            "notification": {
                "on_start": True,
                "on_success": True,
                "on_failure": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 📱 TELEGRAM INTEGRATION (Bridge for Human-in-the-Loop)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    "telegram_watcher": JobTemplate(
        name="telegram_watcher",
        category="alert",
        priority=75,
        schedule_type="cron",
        schedule_expr="*/5 * * * *",  # Every 5 minutes
        description="Check dan notify pesan Telegram yang menunggu respon dari Cline",
        max_concurrent=1,
        worker_pool="default",
        task_config={
            "steps": [
                {
                    "name": "check_telegram_messages",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP/mcp-unified/integrations/telegram && python3 cline_reader.py",
                    "timeout": 30
                },
                {
                    "name": "save_check_result",
                    "tool": "memory_save",
                    "key": "telegram:watcher:last_check",
                    "content": "Telegram watcher checked at {timestamp}"
                }
            ],
            "notification": {
                "on_success": False,
                "on_failure": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    "telegram_message_processor": JobTemplate(
        name="telegram_message_processor",
        category="autonomous",
        priority=70,
        schedule_type="event",
        schedule_expr="on_telegram_message",
        description="Process Telegram messages dengan AI analysis",
        max_concurrent=1,
        worker_pool="cpu",
        task_config={
            "auto_trigger": True,
            "event_trigger": "telegram_message_received",
            "use_planner": True,
            "prompt": """
            Analyze Telegram message dari user dan tentukan response strategy:
            1. Categorize: bug report, feature request, question, urgent
            2. Estimate complexity: simple, medium, complex
            3. Suggest response approach
            4. Generate draft response jika simple
            """,
            "steps": [
                {
                    "name": "read_messages",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP/mcp-unified/integrations/telegram && python3 -c 'from file_storage import storage; import json; msgs = storage.get_pending_messages(); print(json.dumps(msgs, default=str))'",
                    "timeout": 10
                },
                {
                    "name": "analyze_and_plan",
                    "tool": "create_plan",
                    "objective": "Analyze Telegram messages dan create response plan"
                },
                {
                    "name": "notify_cline",
                    "tool": "memory_save",
                    "key": "telegram:analysis:{timestamp}",
                    "content": "Message analysis completed. Check pending messages."
                }
            ],
            "notification": {
                "on_start": False,
                "on_success": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    "escalation_notify": JobTemplate(
        name="escalation_notify",
        category="alert",
        priority=95,
        schedule_type="event",
        schedule_expr="on_job_failure",
        description="Human escalation notification pada job failure",
        max_concurrent=5,
        worker_pool="network",
        task_config={
            "auto_trigger": True,
            "event_trigger": "job_failure",
            "steps": [
                {
                    "name": "format_escalation_message",
                    "tool": "run_shell",
                    "command": "echo 'Job {job_name} failed {retry_count} times. Manual intervention required.'",
                    "timeout": 5
                }
            ],
            "notification": {
                "on_start": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    "failover_trigger": JobTemplate(
        name="failover_trigger",
        category="alert",
        priority=98,
        schedule_type="event",
        schedule_expr="on_service_down",
        description="Trigger failover ke standby systems",
        max_concurrent=1,
        exclusive_lock=True,
        worker_pool="default",
        task_config={
            "auto_trigger": True,
            "event_trigger": "primary_service_down",
            "steps": [
                {
                    "name": "check_standby_status",
                    "tool": "run_shell",
                    "command": "curl -sf http://standby-server:8000/health && echo 'Standby ready' || echo 'Standby not available'",
                    "timeout": 10
                },
                {
                    "name": "trigger_failover",
                    "tool": "run_shell",
                    "command": "echo 'Failover triggered to standby'",
                    "timeout": 5
                }
            ],
            "notification": {
                "on_start": True,
                "on_success": True,
                "on_failure": True,
                "channels": ["telegram", "vscode"]
            }
        }
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🧠 LTM SYNC (Real-time Task Status Synchronization)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    "ltm_task_sync": JobTemplate(
        name="ltm_task_sync",
        category="autonomous",
        priority=60,
        schedule_type="cron",
        schedule_expr="0 * * * *",  # Every hour
        description="Sync task status dari tasks/ folder ke LTM database",
        max_concurrent=1,
        exclusive_lock=True,
        worker_pool="default",
        task_config={
            "steps": [
                {
                    "name": "scan_task_files",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && python3 scripts/sync_ltm_tasks.py --scan-only",
                    "timeout": 60
                },
                {
                    "name": "update_ltm_project_memories",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && python3 scripts/sync_ltm_tasks.py --update-project-memories",
                    "timeout": 30
                },
                {
                    "name": "update_ltm_memory",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && python3 scripts/sync_ltm_tasks.py --update-ltm-memory",
                    "timeout": 30
                },
                {
                    "name": "sync_memories",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && python3 scripts/sync_ltm_tasks.py --update-memories",
                    "timeout": 30
                },
                {
                    "name": "verify_sync",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && python3 scripts/sync_ltm_tasks.py --verify",
                    "timeout": 30
                }
            ],
            "notification": {
                "on_success": True,
                "on_failure": True,
                "channels": ["telegram"]
            }
        }
    ),
    
    "ltm_task_sync_on_change": JobTemplate(
        name="ltm_task_sync_on_change",
        category="autonomous",
        priority=70,
        schedule_type="event",
        schedule_expr="on_task_change",
        description="Real-time LTM sync saat task status berubah",
        max_concurrent=1,
        exclusive_lock=True,
        worker_pool="default",
        task_config={
            "auto_trigger": True,
            "event_trigger": "task_status_changed",
            "steps": [
                {
                    "name": "quick_sync",
                    "tool": "run_shell",
                    "command": "cd /home/aseps/MCP && python3 scripts/sync_ltm_tasks.py --quick-sync",
                    "timeout": 30
                }
            ],
            "notification": {
                "on_failure": True,
                "channels": ["vscode"]
            }
        }
    )
}


def get_template(name: str) -> Optional[JobTemplate]:
    """Get job template by name."""
    return JOB_TEMPLATES.get(name)


def list_templates(category: Optional[str] = None) -> Dict[str, JobTemplate]:
    """List templates dengan optional category filter."""
    if category:
        return {k: v for k, v in JOB_TEMPLATES.items() if v.category == category}
    return JOB_TEMPLATES


def get_categories() -> List[str]:
    """Get list of unique categories."""
    return sorted(list(set(t.category for t in JOB_TEMPLATES.values())))


def create_job_from_template(
    template_name: str,
    job_name: str,
    namespace: str = "default",
    custom_schedule: Optional[str] = None,
    custom_config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Create job configuration dari template.
    
    Args:
        template_name: Name of the template
        job_name: Unique name untuk job ini
        namespace: Job namespace
        custom_schedule: Override schedule expression (optional)
        custom_config: Override task config (optional)
    
    Returns:
        Dictionary ready untuk create_job()
    """
    template = get_template(template_name)
    if not template:
        return {"success": False, "error": f"Template '{template_name}' not found"}
    
    config = template.to_dict()
    config["name"] = job_name
    config["namespace"] = namespace
    
    if custom_schedule:
        config["schedule_expr"] = custom_schedule
    
    if custom_config:
        # Merge custom config dengan template config
        config["task_config"] = {**config["task_config"], **custom_config}
    
    return {"success": True, "config": config}


# Template aliases untuk convenience
TEMPLATES_BY_CATEGORY = {
    "system_maintenance": ["backup_full", "backup_incremental", "db_vacuum", "log_rotate", "disk_cleanup", "cert_renewal"],
    "monitoring": ["health_check", "compliance_scan", "dependency_check", "performance_report", "cost_analysis"],
    "sync": ["mirror_repos", "ltm_sync_remote"],
    "autonomous": ["auto_heal_review", "smart_cleanup", "doc_auto_update", "test_auto_gen", "telegram_message_processor", "ltm_task_sync", "ltm_task_sync_on_change"],
    "alert": ["incident_response", "escalation_notify", "failover_trigger", "telegram_watcher"]
}
