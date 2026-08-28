"""
Symbol Indexer Schemas for Code Knowledge Graph (TASK-123).
Defines structured entities and relations for code symbols extracted via AST/LSP.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    PARAMETER = "parameter"
    DECORATOR = "decorator"
    TYPE_ALIAS = "type_alias"
    CONFIG = "config"


class SymbolRelation(str, Enum):
    CONTAINS = "contains"
    INHERITS_FROM = "inherits_from"
    HAS_METHOD = "has_method"
    HAS_PARAMETER = "has_parameter"
    DECORATED_BY = "decorated_by"
    RETURNS_TYPE = "returns_type"
    CONFIGURES = "configures"
    REFERENCES = "references"


class ParameterInfo(BaseModel):
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_required: bool = True
    description: Optional[str] = None


class SymbolDefinition(BaseModel):
    symbol_id: str = Field(..., description="Unique symbol identifier (e.g. pydantic:BaseModel)")
    name: str
    symbol_type: SymbolType
    module: str
    library: str = "pydantic"
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parameters: List[ParameterInfo] = Field(default_factory=list)
    return_type: Optional[str] = None
    parent_classes: List[str] = Field(default_factory=list)
    decorators: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
