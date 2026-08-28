"""
Pydantic data models for Graph Memory & Hybrid GraphRAG (TASK-122).
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def _utcnow():
    return datetime.now(timezone.utc)

class GraphNode(BaseModel):
    id: str = Field(..., description="Unique entity ID (e.g. 'surat:000.2.2.4/038/PUU', 'pegawai:198303062008122001')")
    namespace: str = Field(default="default", description="Namespace isolation (e.g. 'korespondensi', 'dashtu_supd_ii', 'shared_legal')")
    entity_type: str = Field(default="concept", description="Entity category: 'surat', 'pegawai', 'instansi', 'regulasi', 'lokasi', 'topik'")
    name: str = Field(..., description="Human-readable entity name")
    summary: Optional[str] = Field(default="", description="Detailed summary or textual content of the entity")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Flexible key-value attributes")
    embedding: Optional[List[float]] = Field(default=None, description="768-dim vector embedding")
    created_at: Optional[datetime] = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(default_factory=_utcnow)

class GraphEdge(BaseModel):
    id: Optional[int] = Field(default=None, description="Edge ID")
    namespace: str = Field(default="default", description="Namespace isolation")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation: str = Field(..., description="Directed relationship predicate (e.g. 'ditandatangani_oleh', 'merujuk_ke', 'menjabat_sebagai')")
    weight: float = Field(default=1.0, description="Confidence or relationship weight (0.0 - 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual attributes of the relation")
    created_at: Optional[datetime] = Field(default_factory=_utcnow)

class Triple(BaseModel):
    source_id: str
    source_name: str
    source_type: str = "concept"
    relation: str
    target_id: str
    target_name: str
    target_type: str = "concept"
    weight: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class GraphPath(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    hop_count: int
    summary_path: str

class Subgraph(BaseModel):
    root_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    depth: int

class HybridSearchResult(BaseModel):
    node: GraphNode
    similarity_score: float
    neighbors: List[GraphNode] = Field(default_factory=list)
    connecting_edges: List[GraphEdge] = Field(default_factory=list)
    explanation: str = ""
