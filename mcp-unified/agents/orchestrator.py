"""
Agent Orchestrator - Multi-Agent Coordination System

Mengkoordinasikan multiple agents untuk menyelesaikan task kompleks.
Provides task decomposition, agent selection, dan result aggregation.

Usage:
    from agents.orchestrator import AgentOrchestrator, ComplexTask, SubTask
    
    orchestrator = AgentOrchestrator()
    
    task = ComplexTask(
        description="Analyze and refactor code",
        sub_tasks=[
            SubTask(type="analyze_code", agent_domain="coding"),
            SubTask(type="read_file", agent_domain="filesystem"),
        ]
    )
    
    result = await orchestrator.execute(task, strategy="sequential")
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult, TaskContext
from .base import BaseAgent, AgentProfile, agent_registry


class CoordinationStrategy(Enum):
    """Strategies untuk koordinasi multi-agent execution."""
    SEQUENTIAL = "sequential"      # Execute one after another
    PARALLEL = "parallel"          # Execute concurrently
    PIPELINE = "pipeline"          # Output of A → Input of B
    MAP_REDUCE = "map_reduce"      # Distribute work, aggregate results


@dataclass
class SubTask:
    """Single sub-task dalam complex workflow."""
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    agent_domain: Optional[str] = None
    agent_name: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    estimated_duration_ms: Optional[int] = None


@dataclass
class ComplexTask:
    """Task kompleks yang terdiri dari multiple sub-tasks."""
    description: str
    sub_tasks: List[SubTask]
    context: TaskContext = field(default_factory=lambda: TaskContext())
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    """Hasil dari orchestrated task execution."""
    success: bool
    description: str
    sub_results: List[TaskResult]
    aggregated_data: Dict[str, Any]
    execution_time_ms: float
    strategy: str
    errors: List[str] = field(default_factory=list)


class AgentOrchestrator:
    """
    Orchestrator untuk mengkoordinasikan multiple agents.
    
    Responsibilities:
    1. Task decomposition (jika diperlukan)
    2. Agent selection untuk setiap sub-task
    3. Execution coordination (sequential/parallel/pipeline)
    4. Result aggregation
    5. Error handling dan retry
    
    Example:
        orchestrator = AgentOrchestrator()
        
        # Sequential execution
        result = await orchestrator.execute(
            complex_task,
            strategy=CoordinationStrategy.SEQUENTIAL
        )
    """
    
    def __init__(self):
        self._registry = agent_registry
        self._execution_history: List[Dict[str, Any]] = []
    
    async def execute(
        self,
        task: ComplexTask,
        strategy: CoordinationStrategy = CoordinationStrategy.SEQUENTIAL,
        max_retries: int = 2
    ) -> OrchestrationResult:
        """
        Execute complex task dengan coordination strategy.
        
        Args:
            task: Complex task dengan sub-tasks
            strategy: Coordination strategy (sequential, parallel, pipeline)
            max_retries: Maximum retry attempts per sub-task
        
        Returns:
            OrchestrationResult dengan hasil aggregated
        """
        start_time = datetime.now()
        logger.info("orchestration_started",
                   description=task.description,
                   strategy=strategy.value,
                   sub_tasks=len(task.sub_tasks))
        
        try:
            # Select execution method based on strategy
            if strategy == CoordinationStrategy.SEQUENTIAL:
                sub_results = await self._execute_sequential(task, max_retries)
            elif strategy == CoordinationStrategy.PARALLEL:
                sub_results = await self._execute_parallel(task, max_retries)
            elif strategy == CoordinationStrategy.PIPELINE:
                sub_results = await self._execute_pipeline(task, max_retries)
            elif strategy == CoordinationStrategy.MAP_REDUCE:
                sub_results = await self._execute_map_reduce(task, max_retries)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")
            
            # Aggregate results
            aggregated = self._aggregate_results(sub_results)
            
            # Check for errors
            errors = [r.error for r in sub_results if not r.success]
            success = len(errors) == 0
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = OrchestrationResult(
                success=success,
                description=task.description,
                sub_results=sub_results,
                aggregated_data=aggregated,
                execution_time_ms=execution_time,
                strategy=strategy.value,
                errors=errors
            )
            
            logger.info("orchestration_completed",
                       success=success,
                       execution_time_ms=execution_time,
                       errors=len(errors))
            
            return result
            
        except Exception as e:
            logger.error("orchestration_failed", error=str(e))
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return OrchestrationResult(
                success=False,
                description=task.description,
                sub_results=[],
                aggregated_data={},
                execution_time_ms=execution_time,
                strategy=strategy.value,
                errors=[str(e)]
            )
    
    def _select_agent(self, sub_task: SubTask) -> Optional[BaseAgent]:
        """
        Select best agent untuk sub-task.
        
        Selection priority:
        1. By agent_name jika specified
        2. By agent_domain jika specified
        3. By task type matching
        4. Any available agent sebagai fallback
        """
        # Priority 1: By name
        if sub_task.agent_name:
            agent = self._registry.get_agent(sub_task.agent_name)
            if agent and agent.is_available():
                return agent
            logger.warning("specified_agent_unavailable", 
                          agent_name=sub_task.agent_name)
        
        # Priority 2: By domain
        if sub_task.agent_domain:
            agents = self._registry.get_agents_by_domain(sub_task.agent_domain)
            available = [a for a in agents if a.is_available()]
            if available:
                # Select least busy
                return min(available, key=lambda a: a._current_tasks)
            logger.warning("no_agent_available_for_domain", 
                          domain=sub_task.agent_domain)
        
        # Priority 3: By task type matching
        task = Task(type=sub_task.type, payload=sub_task.payload)
        agent = self._registry.find_agent_for_task(task)
        if agent and agent.is_available():
            return agent
        
        # Priority 4: Any available agent
        all_agents = [self._registry.get_agent(name) 
                     for name in self._registry.list_agents()]
        available = [a for a in all_agents if a and a.is_available()]
        if available:
            return min(available, key=lambda a: a._current_tasks)
        
        logger.error("no_agent_available", task_type=sub_task.type)
        return None
    
    async def _execute_sequential(
        self, 
        task: ComplexTask, 
        max_retries: int
    ) -> List[TaskResult]:
        """Execute sub-tasks satu per satu secara berurutan."""
        results = []
        
        for i, sub_task in enumerate(task.sub_tasks):
            logger.info("executing_sub_task_sequential",
                       step=i+1,
                       total=len(task.sub_tasks),
                       task_type=sub_task.type)
            
            result = await self._execute_sub_task(sub_task, task.context, max_retries)
            results.append(result)
            
            # Stop on failure (sequential dependency)
            if not result.success:
                logger.warning("sequential_execution_stopped",
                             failed_step=i+1,
                             error=result.error)
                break
        
        return results
    
    async def _execute_parallel(
        self, 
        task: ComplexTask, 
        max_retries: int
    ) -> List[TaskResult]:
        """Execute sub-tasks secara parallel/concurrent."""
        logger.info("executing_sub_tasks_parallel",
                   count=len(task.sub_tasks))
        
        # Create tasks
        coroutines = [
            self._execute_sub_task(sub_task, task.context, max_retries)
            for sub_task in task.sub_tasks
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TaskResult.failure_result(
                    task_id=f"subtask_{i}",
                    error=str(result),
                    error_code="EXECUTION_EXCEPTION"
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_pipeline(
        self, 
        task: ComplexTask, 
        max_retries: int
    ) -> List[TaskResult]:
        """Execute sub-tasks sebagai pipeline (output A → input B)."""
        results = []
        previous_output = {}
        
        for i, sub_task in enumerate(task.sub_tasks):
            logger.info("executing_pipeline_step",
                       step=i+1,
                       total=len(task.sub_tasks))
            
            # Merge previous output dengan current payload
            merged_payload = {**sub_task.payload, **previous_output}
            sub_task.payload = merged_payload
            
            result = await self._execute_sub_task(sub_task, task.context, max_retries)
            results.append(result)
            
            # Stop on failure
            if not result.success:
                logger.warning("pipeline_execution_stopped",
                             failed_step=i+1)
                break
            
            # Pass output ke next step
            if result.data:
                previous_output = result.data if isinstance(result.data, dict) else {"output": result.data}
        
        return results
    
    async def _execute_map_reduce(
        self, 
        task: ComplexTask, 
        max_retries: int
    ) -> List[TaskResult]:
        """Execute sub-tasks dengan map-reduce pattern."""
        logger.info("executing_map_reduce",
                   count=len(task.sub_tasks))
        
        # Map phase - execute all concurrently
        map_results = await self._execute_parallel(task, max_retries)
        
        # Reduce phase - aggregate results (simplified)
        # In real implementation, could apply reduce function
        success_count = sum(1 for r in map_results if r.success)
        
        logger.info("map_reduce_completed",
                   success_count=success_count,
                   total=len(map_results))
        
        return map_results
    
    async def _execute_sub_task(
        self,
        sub_task: SubTask,
        context: TaskContext,
        max_retries: int
    ) -> TaskResult:
        """Execute single sub-task dengan retry logic."""
        agent = self._select_agent(sub_task)
        
        if not agent:
            return TaskResult.failure_result(
                task_id=f"{sub_task.type}_{datetime.now().timestamp()}",
                error=f"No agent available for task type: {sub_task.type}",
                error_code="AGENT_NOT_FOUND"
            )
        
        task = Task(
            type=sub_task.type,
            payload=sub_task.payload,
            context=context,
            priority="normal"
        )
        
        # Execute dengan retry
        for attempt in range(max_retries + 1):
            try:
                result = await agent.execute(task)
                
                if result.success:
                    return result
                
                # Retry jika failed
                if attempt < max_retries:
                    logger.warning("sub_task_retry",
                                 task_type=sub_task.type,
                                 attempt=attempt+1,
                                 max_retries=max_retries)
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                logger.error("sub_task_execution_error",
                           task_type=sub_task.type,
                           error=str(e))
                if attempt >= max_retries:
                    return TaskResult.failure_result(
                        task_id=task.id,
                        error=str(e),
                        error_code="EXECUTION_ERROR"
                    )
        
        return TaskResult.failure_result(
            task_id=task.id,
            error="Max retries exceeded",
            error_code="MAX_RETRIES_EXCEEDED"
        )
    
    def _aggregate_results(self, results: List[TaskResult]) -> Dict[str, Any]:
        """Aggregate results dari multiple sub-tasks."""
        aggregated = {
            "total_tasks": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "outputs": []
        }
        
        for i, result in enumerate(results):
            if result.data:
                aggregated["outputs"].append({
                    "step": i + 1,
                    "success": result.success,
                    "data": result.data
                })
        
        return aggregated
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get history of orchestrated executions."""
        return self._execution_history.copy()
    
    def get_available_agents(self) -> Dict[str, Any]:
        """Get info tentang available agents."""
        agents = {}
        for name in self._registry.list_agents():
            agent = self._registry.get_agent(name)
            if agent:
                agents[name] = {
                    "domain": agent.profile.domain,
                    "available": agent.is_available(),
                    "current_tasks": agent._current_tasks,
                    "max_concurrent": agent.profile.max_concurrent_tasks
                }
        return agents


# Convenience function untuk quick orchestration
async def orchestrate(
    description: str,
    sub_tasks: List[SubTask],
    strategy: CoordinationStrategy = CoordinationStrategy.SEQUENTIAL,
    context: Optional[TaskContext] = None
) -> OrchestrationResult:
    """
    Quick helper untuk orchestrate tasks tanpa instantiate orchestrator.
    
    Args:
        description: Deskripsi task kompleks
        sub_tasks: List sub-tasks
        strategy: Coordination strategy
        context: Optional task context
    
    Returns:
        OrchestrationResult
    
    Example:
        result = await orchestrate(
            "Review code",
            [SubTask(type="analyze_code"), SubTask(type="read_file")],
            strategy=CoordinationStrategy.PIPELINE
        )
    """
    orchestrator = AgentOrchestrator()
    task = ComplexTask(
        description=description,
        sub_tasks=sub_tasks,
        context=context or TaskContext()
    )
    return await orchestrator.execute(task, strategy)
