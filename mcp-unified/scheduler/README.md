# MCP Autonomous Task Scheduler

Scheduled job execution system untuk MCP Unified Server.

## Overview

Scheduler ini memungkinkan eksekusi tugas terjadwal secara otomatis dengan:
- **20+ Job Types**: Backup, monitoring, sync, autonomous tasks, alerts
- **Two-Layer Storage**: Redis (hot queue) + PostgreSQL (cold storage)
- **Priority-Based Scheduling**: Preemption untuk critical jobs
- **Self-Healing**: Auto-fix pada execution failure
- **LTM Integration**: Context-aware execution

## Directory Structure

```
scheduler/
├── __init__.py              # Package init
├── config.py                # Configuration
├── database.py              # Database schema & operations
├── executor.py              # Job execution engine
├── manager.py               # Job CRUD & lifecycle
├── queue.py                 # Redis queue management
├── pools.py                 # Concurrency pool manager
├── daemon.py                # Main scheduler daemon
├── templates.py             # Job type definitions
├── notifier.py              # Notification system
├── recovery.py              # Crash recovery
└── tools.py                 # MCP tools for scheduler
```

## Quick Start

### 1. Setup Database
```bash
python -c "from scheduler.database import init_schema; init_schema()"
```

### 2. Start Scheduler Daemon
```bash
sudo systemctl start mcp-scheduler
```

### 3. Create Scheduled Job
```python
from scheduler.manager import SchedulerManager

manager = SchedulerManager()
job = await manager.create_job(
    name="daily_backup",
    template="backup_full",
    schedule="0 2 * * *"  # Daily at 2 AM
)
```

## Job Types

### System Maintenance
- `backup_full`: Full system backup
- `backup_incremental`: Incremental backup
- `db_vacuum`: PostgreSQL maintenance
- `log_rotate`: Log archiving
- `disk_cleanup`: Auto cleanup
- `cert_renewal`: SSL certificate renewal

### Monitoring
- `health_check`: System health check
- `compliance_scan`: Security audit
- `performance_report`: Metrics summary

### Autonomous
- `auto_heal_review`: Error pattern analysis
- `smart_cleanup`: AI-suggested cleanup

## Architecture

See [PROPOSAL/11-autonomous-task-scheduler.md](../../PROPOSAL/11-autonomous-task-scheduler.md)

## Integration

- **LTM**: `memory/longterm.py`
- **Planner**: `intelligence/planner.py`
- **Self-Healing**: `intelligence/self_healing.py`
- **Tools**: `execution/registry.py`

## License

Same as MCP Unified Server
