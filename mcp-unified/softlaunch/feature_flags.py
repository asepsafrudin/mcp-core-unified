"""
Feature Flags System

Manage feature rollouts, A/B testing, and gradual enablement.
Part of TASK-029: Phase 8 - Soft Launch Infrastructure
"""

import asyncio
import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RolloutStrategy(Enum):
    """Feature rollout strategies"""
    ALL = "all"                    # Enable for everyone
    NONE = "none"                  # Disable for everyone
    PERCENTAGE = "percentage"      # Percentage of users
    USER_ID = "user_id"            # Specific user IDs
    GROUP = "group"                # User groups/segments
    RANDOM = "random"              # Random selection


class FeatureStatus(Enum):
    """Feature flag status"""
    DEVELOPMENT = "development"    # In development, internal only
    STAGING = "staging"            # Testing in staging
    CANARY = "canary"              # Canary rollout
    PRODUCTION = "production"      # Fully released
    DEPRECATED = "deprecated"      # Being phased out


@dataclass
class FeatureFlag:
    """A feature flag configuration"""
    name: str
    description: str
    
    # Rollout configuration
    strategy: RolloutStrategy = RolloutStrategy.NONE
    percentage: int = 0  # 0-100 for PERCENTAGE strategy
    allowed_user_ids: Set[str] = field(default_factory=set)
    allowed_groups: Set[str] = field(default_factory=set)
    
    # Status
    status: FeatureStatus = FeatureStatus.DEVELOPMENT
    enabled: bool = True
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "system"
    
    # Scheduling
    scheduled_enable_time: Optional[float] = None
    scheduled_disable_time: Optional[float] = None
    
    # A/B testing
    is_experiment: bool = False
    experiment_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "strategy": self.strategy.value,
            "percentage": self.percentage,
            "allowed_user_ids": list(self.allowed_user_ids),
            "allowed_groups": list(self.allowed_groups),
            "status": self.status.value,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "scheduled_enable_time": self.scheduled_enable_time,
            "scheduled_disable_time": self.scheduled_disable_time,
            "is_experiment": self.is_experiment,
            "experiment_id": self.experiment_id,
        }


@dataclass
class UserContext:
    """User context for feature flag evaluation"""
    user_id: str
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "groups": self.groups,
            "attributes": self.attributes,
            "session_id": self.session_id,
        }


class FeatureFlagManager:
    """
    Manages feature flags for soft launch and A/B testing.
    
    Features:
    - Multiple rollout strategies
    - User segmentation
    - Scheduled rollouts
    - A/B testing support
    - Real-time updates
    """
    
    def __init__(self):
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()
        self._listeners: List[Callable[[str, bool], None]] = []
        
        logger.info("FeatureFlagManager initialized")
    
    async def create_flag(
        self,
        name: str,
        description: str,
        strategy: RolloutStrategy = RolloutStrategy.NONE,
        **kwargs
    ) -> FeatureFlag:
        """Create a new feature flag"""
        async with self._lock:
            if name in self._flags:
                raise ValueError(f"Feature flag '{name}' already exists")
            
            flag = FeatureFlag(
                name=name,
                description=description,
                strategy=strategy,
                **kwargs
            )
            self._flags[name] = flag
            
            logger.info(f"Feature flag created: {name}")
            return flag
    
    async def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get a feature flag by name"""
        async with self._lock:
            return self._flags.get(name)
    
    async def update_flag(
        self,
        name: str,
        **updates
    ) -> Optional[FeatureFlag]:
        """Update a feature flag"""
        async with self._lock:
            if name not in self._flags:
                return None
            
            flag = self._flags[name]
            for key, value in updates.items():
                if hasattr(flag, key):
                    setattr(flag, key, value)
            
            flag.updated_at = time.time()
            
            # Notify listeners
            for listener in self._listeners:
                try:
                    listener(name, flag.enabled)
                except Exception as e:
                    logger.error(f"Listener error: {e}")
            
            logger.info(f"Feature flag updated: {name}")
            return flag
    
    async def delete_flag(self, name: str) -> bool:
        """Delete a feature flag"""
        async with self._lock:
            if name not in self._flags:
                return False
            
            del self._flags[name]
            logger.info(f"Feature flag deleted: {name}")
            return True
    
    async def list_flags(
        self,
        status: Optional[FeatureStatus] = None
    ) -> List[FeatureFlag]:
        """List all feature flags, optionally filtered by status"""
        async with self._lock:
            flags = list(self._flags.values())
            if status:
                flags = [f for f in flags if f.status == status]
            return flags
    
    def is_enabled(
        self,
        flag_name: str,
        user_context: Optional[UserContext] = None,
    ) -> bool:
        """
        Check if a feature is enabled for a user.
        
        Args:
            flag_name: Name of the feature flag
            user_context: User context for evaluation
        
        Returns:
            True if feature is enabled
        """
        flag = self._flags.get(flag_name)
        if not flag:
            return False
        
        # Check if flag is globally enabled
        if not flag.enabled:
            return False
        
        # Check scheduled times
        now = time.time()
        if flag.scheduled_disable_time and now > flag.scheduled_disable_time:
            return False
        if flag.scheduled_enable_time and now < flag.scheduled_enable_time:
            return False
        
        # Evaluate based on strategy
        return self._evaluate_strategy(flag, user_context)
    
    def _evaluate_strategy(
        self,
        flag: FeatureFlag,
        user_context: Optional[UserContext],
    ) -> bool:
        """Evaluate flag based on its strategy"""
        strategy = flag.strategy
        
        if strategy == RolloutStrategy.ALL:
            return True
        
        if strategy == RolloutStrategy.NONE:
            return False
        
        if not user_context:
            # Without user context, only ALL/NONE work
            return False
        
        if strategy == RolloutStrategy.USER_ID:
            return user_context.user_id in flag.allowed_user_ids
        
        if strategy == RolloutStrategy.GROUP:
            user_groups = set(user_context.groups)
            return bool(user_groups & flag.allowed_groups)
        
        if strategy == RolloutStrategy.PERCENTAGE:
            return self._is_in_percentage(
                user_context.user_id,
                flag.percentage,
                flag.name
            )
        
        if strategy == RolloutStrategy.RANDOM:
            return random.random() * 100 < flag.percentage
        
        return False
    
    def _is_in_percentage(
        self,
        user_id: str,
        percentage: int,
        salt: str,
    ) -> bool:
        """
        Deterministically check if user is in percentage rollout.
        Uses hash for consistency across requests.
        """
        # Create hash of user_id + salt
        hash_input = f"{user_id}:{salt}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        
        # Convert first 8 chars to integer (0-2^32)
        user_bucket = int(hash_value[:8], 16) % 100
        
        return user_bucket < percentage
    
    async def enable_for_user(
        self,
        flag_name: str,
        user_id: str,
    ) -> bool:
        """Enable a feature flag for a specific user"""
        async with self._lock:
            if flag_name not in self._flags:
                return False
            
            flag = self._flags[flag_name]
            flag.allowed_user_ids.add(user_id)
            flag.strategy = RolloutStrategy.USER_ID
            flag.updated_at = time.time()
            
            logger.info(f"Enabled {flag_name} for user {user_id}")
            return True
    
    async def enable_for_group(
        self,
        flag_name: str,
        group: str,
    ) -> bool:
        """Enable a feature flag for a group"""
        async with self._lock:
            if flag_name not in self._flags:
                return False
            
            flag = self._flags[flag_name]
            flag.allowed_groups.add(group)
            flag.strategy = RolloutStrategy.GROUP
            flag.updated_at = time.time()
            
            logger.info(f"Enabled {flag_name} for group {group}")
            return True
    
    async def rollout_percentage(
        self,
        flag_name: str,
        percentage: int,
    ) -> bool:
        """Set percentage rollout for a feature"""
        async with self._lock:
            if flag_name not in self._flags:
                return False
            
            flag = self._flags[flag_name]
            flag.percentage = max(0, min(100, percentage))
            flag.strategy = RolloutStrategy.PERCENTAGE
            flag.updated_at = time.time()
            
            logger.info(f"Set {flag_name} rollout to {flag.percentage}%")
            return True
    
    def get_enabled_features(
        self,
        user_context: Optional[UserContext] = None,
    ) -> List[str]:
        """Get list of enabled features for a user"""
        enabled = []
        for name, flag in self._flags.items():
            if self.is_enabled(name, user_context):
                enabled.append(name)
        return enabled
    
    def add_listener(self, callback: Callable[[str, bool], None]):
        """Add a listener for flag changes"""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[str, bool], None]):
        """Remove a listener"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def get_stats(self) -> dict:
        """Get feature flag statistics"""
        total = len(self._flags)
        by_status = {}
        by_strategy = {}
        
        for flag in self._flags.values():
            status = flag.status.value
            strategy = flag.strategy.value
            by_status[status] = by_status.get(status, 0) + 1
            by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
        
        return {
            "total_flags": total,
            "by_status": by_status,
            "by_strategy": by_strategy,
        }


# Global instance
_feature_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get or create global feature flag manager"""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureFlagManager()
    return _feature_manager


def is_feature_enabled(
    flag_name: str,
    user_id: Optional[str] = None,
    **kwargs
) -> bool:
    """
    Convenience function to check if a feature is enabled.
    
    Usage:
        if is_feature_enabled("new_tool", user_id="user123"):
            # Use new feature
    """
    manager = get_feature_flag_manager()
    
    user_context = None
    if user_id:
        user_context = UserContext(
            user_id=user_id,
            groups=kwargs.get("groups", []),
            attributes=kwargs.get("attributes", {}),
            session_id=kwargs.get("session_id"),
        )
    
    return manager.is_enabled(flag_name, user_context)
