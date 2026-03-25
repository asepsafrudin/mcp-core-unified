"""
Healing Skills - Self-healing and error recovery capabilities

Migrated from intelligence/self_healing.py using adapter pattern.

Skills:
    - execute_with_healing: Execute function with automatic retries and healing

Usage:
    from skills.healing import execute_with_healing, self_healing
    
    result = await execute_with_healing(
        func=my_function,
        args=[arg1, arg2],
        kwargs={"key": "value"}
    )
"""

from .self_healing import (
    execute_with_healing,
    self_healing,
    PracticalSelfHealing,
    APPROVED_AUTO_INSTALL_PACKAGES,
)

__all__ = [
    "execute_with_healing",
    "self_healing",
    "PracticalSelfHealing",
    "APPROVED_AUTO_INSTALL_PACKAGES",
]
