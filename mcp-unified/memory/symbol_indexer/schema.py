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


# =====================================================================
# 3-Layer Redis & LTM Cache Schemas (TASK-125)
# =====================================================================

class SymbolIndexItem(BaseModel):
    """
    Layer 1: Core symbol structure for rapid LLM lookup without context dumping.
    Redis Key Pattern: lib:{library}:{version}:symbol:{symbol_path}
    """
    symbol_path: str = Field(..., description="Full symbol path (e.g. pydantic.BaseModel.model_validate)")
    kind: str = Field(..., description="Symbol kind: class | method | classmethod | function | decorator")
    signature: str = Field(..., description="Complete typed call signature")
    docstring_short: str = Field(..., description="One-to-two sentence brief summary for rapid AI decision")
    docstring_full: Optional[str] = Field(None, description="Full docstring (including Examples section) as a cheap middle-ground fallback")
    file_location: Optional[str] = Field(None, description="Pointer to source file and line (e.g. pydantic/main.py:L450)")

    parent_class: Optional[str] = Field(None, description="Enclosing class if method/classmethod")
    returns: Optional[str] = Field(None, description="Return type annotation")
    raises: List[str] = Field(default_factory=list, description="Common exceptions raised")
    tags: List[str] = Field(default_factory=list, description="Semantic capability tags")
    token_cost_cached: int = Field(0, description="Estimated token cost of this cached symbol item")


class SnippetReference(BaseModel):
    context: str = Field(..., description="Context of pattern (e.g. parsing API request body)")
    snippet_ref: str = Field(..., description="Key reference to snippet (e.g. snippet:pydantic:2.9:001)")
    frequency_rank: int = Field(1, description="Rank / popularity order")


class UsagePatternItem(BaseModel):
    """
    Layer 2A: Common usage patterns and related symbols.
    Redis Key Pattern: lib:{library}:{version}:usage:{symbol_path}
    """
    symbol_path: str
    common_patterns: List[SnippetReference] = Field(default_factory=list)
    related_symbols: List[str] = Field(default_factory=list)


class SnippetItem(BaseModel):
    """
    Layer 2B: Isolated code snippet referenced by multiple symbol usages.
    Redis Key Pattern: snippet:{library}:{version}:{snippet_id}
    """
    snippet_id: str
    code: str
    description: Optional[str] = None
    validated: bool = True


class LibraryMetaIndex(BaseModel):
    """
    Layer 3: Library-level metadata and staleness tracking.
    Redis Key Pattern: lib:{library}:{version}:meta
    """
    library: str
    version: str
    indexed_at: str
    indexer: str = "serena+ast"
    total_symbols: int = 0
    index_status: str = "complete"
    stale_after_days: int = 30
    source_commit: Optional[str] = None

