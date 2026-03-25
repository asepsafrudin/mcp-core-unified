"""
Coordination Patterns for Multi-Agent System

Provides different coordination strategies untuk multi-agent execution:
- Sequential: Execute tasks one after another
- Parallel: Execute tasks concurrently
- Pipeline: Output of task A → Input of task B
- MapReduce: Distribute work, aggregate results

Usage:
    from agents.coordination import SequentialPattern, ParallelPattern
    
    pattern = SequentialPattern()
    results = await pattern.execute(sub_tasks, context)
"""

from .patterns import (
    SequentialPattern,
    ParallelPattern,
    PipelinePattern,
    MapReducePattern,
    CoordinationPattern,
)

__all__ = [
    "SequentialPattern",
    "ParallelPattern", 
    "PipelinePattern",
    "MapReducePattern",
    "CoordinationPattern",
]
