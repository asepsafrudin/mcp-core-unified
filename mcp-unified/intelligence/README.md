# MCP Intelligence Module

## Planner Versions
- **v1** (`planner.py`): Simple heuristic + LTM recall
- **v2** (`planner_v2.py`): **Multi-integration** (>3 external services), dependency graph, parallel planning ✅ **TASK-033 Phase 4**

## V2 Features (TASK-033 Compliant)
- Detect Gmail/Calendar/WhatsApp/GDrive/LTM/Knowledge
- Build dependency graph (nx.DiGraph)
- Parallel execution groups
- Cross-domain linking via `/domains/`
- Namespace-scoped planning

**Usage**:
```python
from intelligence.planner_v2 import create_v2_plan
plan = await create_v2_plan("Send UU 23/2014 summary via Gmail + WhatsApp + Calendar scheduling")
```

