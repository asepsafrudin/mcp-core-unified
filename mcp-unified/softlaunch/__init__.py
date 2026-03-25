"""
Soft Launch Infrastructure

Canary deployments, feature flags, and gradual rollout capabilities.
Part of TASK-029: Phase 8 - Soft Launch Preparation
"""

from .feature_flags import (
    FeatureFlagManager,
    FeatureFlag,
    UserContext,
    RolloutStrategy,
    FeatureStatus,
    get_feature_flag_manager,
    is_feature_enabled,
)
from .canary import (
    CanaryDeploymentManager,
    CanaryDeployment,
    CanaryConfig,
    CanaryStatus,
    get_canary_manager,
)

__all__ = [
    # Feature Flags
    "FeatureFlagManager",
    "FeatureFlag",
    "UserContext",
    "RolloutStrategy",
    "FeatureStatus",
    "get_feature_flag_manager",
    "is_feature_enabled",
    # Canary
    "CanaryDeploymentManager",
    "CanaryDeployment",
    "CanaryConfig",
    "CanaryStatus",
    "get_canary_manager",
]