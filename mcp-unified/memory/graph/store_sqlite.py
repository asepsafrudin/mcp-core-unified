"""
SQLite Local Graph Store Adapter (TASK-122).
Provides ultra-fast local graph storage, recursive CTE traversal, and metadata filtering.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from .schema import GraphNode, GraphEdge, Triple, Subgraph

DEFAULT_DB_PATH = Path("/home/aseps/MCP/storage/databases/graph_memory.db")

class SQLiteGraphStore:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL DEFAULT 'default',
                entity_type TEXT NOT NULL DEFAULT 'concept',
                name TEXT NOT NULL,
                summary TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL DEFAULT 'default',
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(namespace, source_id, target_id, relation),
                FOREIGN KEY (source_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES graph_nodes(id) ON DELETE CASCADE
            )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sq_nodes_ns ON graph_nodes(namespace, entity_type)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sq_nodes_name ON graph_nodes(name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sq_edges_src ON graph_edges(source_id, relation)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sq_edges_tgt ON graph_edges(target_id, relation)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sq_edges_ns ON graph_edges(namespace)")
            conn.commit()

    def upsert_node(self, node: GraphNode) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO graph_nodes (id, namespace, entity_type, name, summary, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                namespace = excluded.namespace,
                entity_type = excluded.entity_type,
                name = excluded.name,
                summary = excluded.summary,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
            """, (
                node.id,
                node.namespace,
                node.entity_type,
                node.name,
                node.summary or "",
                json.dumps(node.metadata or {})
            ))
            conn.commit()

    def add_edge(self, edge: GraphEdge) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO graph_edges (namespace, source_id, target_id, relation, weight, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, source_id, target_id, relation) DO UPDATE SET
                weight = excluded.weight,
                metadata = excluded.metadata
            """, (
                edge.namespace,
                edge.source_id,
                edge.target_id,
                edge.relation,
                edge.weight,
                json.dumps(edge.metadata or {})
            ))
            conn.commit()

    def ingest_triple(self, triple: Triple, namespace: str = "default") -> None:
        src_node = GraphNode(
            id=triple.source_id,
            namespace=namespace,
            entity_type=triple.source_type,
            name=triple.source_name
        )
        tgt_node = GraphNode(
            id=triple.target_id,
            namespace=namespace,
            entity_type=triple.target_type,
            name=triple.target_name
        )
        self.upsert_node(src_node)
        self.upsert_node(tgt_node)
        
        edge = GraphEdge(
            namespace=namespace,
            source_id=triple.source_id,
            target_id=triple.target_id,
            relation=triple.relation,
            weight=triple.weight,
            metadata=triple.metadata
        )
        self.add_edge(edge)

    def get_node(self, node_id: str, namespace: Optional[str] = None) -> Optional[GraphNode]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            if namespace:
                cur.execute("SELECT * FROM graph_nodes WHERE id = ? AND namespace = ?", (node_id, namespace))
            else:
                cur.execute("SELECT * FROM graph_nodes WHERE id = ?", (node_id,))
            row = cur.fetchone()
            if not row:
                return None
            return GraphNode(
                id=row["id"],
                namespace=row["namespace"],
                entity_type=row["entity_type"],
                name=row["name"],
                summary=row["summary"],
                metadata=json.loads(row["metadata"] or "{}")
            )

    def get_neighbors(
        self, node_id: str, depth: int = 1, namespace: Optional[str] = None
    ) -> Subgraph:
        """
        Extract N-hop neighbors using Recursive Common Table Expression (CTE).
        """
        depth = max(1, min(depth, 4))
        nodes_dict: Dict[str, GraphNode] = {}
        edges_list: List[GraphEdge] = []
        
        query = """
        WITH RECURSIVE graph_traverse(node_id, depth) AS (
            SELECT ?, 0
            UNION
            SELECT 
                CASE WHEN e.source_id = gt.node_id THEN e.target_id ELSE e.source_id END,
                gt.depth + 1
            FROM graph_edges e
            JOIN graph_traverse gt ON e.source_id = gt.node_id OR e.target_id = gt.node_id
            WHERE gt.depth < ?
              AND (? IS NULL OR e.namespace = ?)
        )
        SELECT DISTINCT n.* FROM graph_nodes n
        JOIN graph_traverse gt ON n.id = gt.node_id;
        """
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (node_id, depth, namespace, namespace))
            rows = cur.fetchall()
            for r in rows:
                n = GraphNode(
                    id=r["id"],
                    namespace=r["namespace"],
                    entity_type=r["entity_type"],
                    name=r["name"],
                    summary=r["summary"],
                    metadata=json.loads(r["metadata"] or "{}")
                )
                nodes_dict[n.id] = n
                
            if nodes_dict:
                placeholders = ",".join(["?"] * len(nodes_dict))
                cur.execute(f"""
                SELECT * FROM graph_edges
                WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
                  AND (? IS NULL OR namespace = ?)
                """, list(nodes_dict.keys()) + list(nodes_dict.keys()) + [namespace, namespace])
                
                edge_rows = cur.fetchall()
                for er in edge_rows:
                    edges_list.append(GraphEdge(
                        id=er["id"],
                        namespace=er["namespace"],
                        source_id=er["source_id"],
                        target_id=er["target_id"],
                        relation=er["relation"],
                        weight=er["weight"],
                        metadata=json.loads(er["metadata"] or "{}")
                    ))

        return Subgraph(
            root_id=node_id,
            nodes=list(nodes_dict.values()),
            edges=edges_list,
            depth=depth
        )

    def find_path(self, source_id: str, target_id: str, max_hops: int = 3) -> Optional[List[Tuple[str, str, str]]]:
        """
        Find shortest relational path between source and target node.
        Returns list of (source, relation, target) tuples.
        """
        query = """
        WITH RECURSIVE path_finder(curr_node, path, depth) AS (
            SELECT ?, ? || '', 0
            UNION ALL
            SELECT 
                e.target_id,
                pf.path || ' -> [' || e.relation || '] -> ' || e.target_id,
                pf.depth + 1
            FROM graph_edges e
            JOIN path_finder pf ON e.source_id = pf.curr_node
            WHERE pf.depth < ? AND instr(pf.path, e.target_id) = 0
        )
        SELECT path FROM path_finder WHERE curr_node = ? ORDER BY depth ASC LIMIT 1;
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (source_id, source_id, max_hops, target_id))
            row = cur.fetchone()
            if row:
                return row["path"]
        return None

    def search_nodes_by_keyword(self, keyword: str, namespace: Optional[str] = None, limit: int = 10) -> List[GraphNode]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            like_pat = f"%{keyword}%"
            query = """
            SELECT * FROM graph_nodes
            WHERE (name LIKE ? OR summary LIKE ? OR id LIKE ?)
              AND (? IS NULL OR namespace = ?)
            LIMIT ?
            """
            cur.execute(query, (like_pat, like_pat, like_pat, namespace, namespace, limit))
            return [
                GraphNode(
                    id=r["id"],
                    namespace=r["namespace"],
                    entity_type=r["entity_type"],
                    name=r["name"],
                    summary=r["summary"],
                    metadata=json.loads(r["metadata"] or "{}")
                )
                for r in cur.fetchall()
            ]
