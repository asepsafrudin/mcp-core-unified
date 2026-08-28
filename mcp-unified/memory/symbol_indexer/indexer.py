"""
Library Symbol Indexer for Graph Memory (TASK-123 & Advanced Database Expansion).
Indexes: Pydantic v2, FastMCP, LangGraph, HTTPX, Psycopg, SQLAlchemy 2.0, pgvector, sqlite-vec, Alembic.
"""

import sys
import importlib
import logging
from typing import List, Dict, Any, Optional

from memory.graph.store_sqlite import SQLiteGraphStore
from memory.graph.schema import Triple
from memory.symbol_indexer.extractor import SymbolExtractor
from memory.symbol_indexer.schema import SymbolType, SymbolRelation

logger = logging.getLogger(__name__)


class LibrarySymbolIndexer:
    """
    Orchestrates extraction and storage of library symbols into Graph Memory.
    """

    def __init__(self, store: Optional[SQLiteGraphStore] = None, namespace: str = "code_symbols"):
        self.store = store or SQLiteGraphStore()
        self.namespace = namespace

    def index_library(self, library_name: str, submodules: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generic automatic indexer for any installed Python library.
        """
        lib_key = library_name.lower().strip()
        if lib_key == "pydantic":
            return self.index_pydantic_v2()
        elif lib_key == "fastmcp":
            return self.index_fastmcp()
        elif lib_key == "langgraph":
            return self.index_langgraph()
        elif lib_key == "httpx":
            return self.index_httpx()
        elif lib_key in ("psycopg", "psycopg3"):
            return self.index_psycopg()
        elif lib_key == "sqlalchemy":
            return self.index_sqlalchemy()
        elif lib_key == "pgvector":
            return self.index_pgvector()
        elif lib_key in ("sqlite_vec", "sqlite-vec"):
            return self.index_sqlite_vec()
        elif lib_key == "alembic":
            return self.index_alembic()

        # Generic library indexing via AST & Reflection
        extractor = SymbolExtractor(library_name=library_name, namespace=self.namespace)
        total_ingested = 0

        try:
            mod = importlib.import_module(library_name)
            triples = extractor.extract_from_module(mod)
            for t in triples:
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1

            if submodules:
                for submod_name in submodules:
                    try:
                        submod = importlib.import_module(submod_name)
                        for t in extractor.extract_from_module(submod):
                            self.store.ingest_triple(t, namespace=self.namespace)
                            total_ingested += 1
                    except Exception as e:
                        logger.warning(f"Could not extract submodule {submod_name}: {e}")

        except ImportError as e:
            return {"status": "error", "message": f"Library '{library_name}' is not installed: {e}"}

        return {
            "library": library_name,
            "namespace": self.namespace,
            "triples_ingested": total_ingested,
            "status": "success"
        }

    def index_pydantic_v2(self) -> Dict[str, Any]:
        """Extracts and indexes core Pydantic v2 symbols, signatures, and relations."""
        extractor = SymbolExtractor(library_name="pydantic", namespace=self.namespace)
        total_ingested = 0

        try:
            import pydantic
            for t in extractor.extract_from_module(pydantic):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1

            for submod_name in ("pydantic.main", "pydantic.fields", "pydantic.config", "pydantic.functional_validators"):
                try:
                    submod = importlib.import_module(submod_name)
                    for t in extractor.extract_from_module(submod):
                        self.store.ingest_triple(t, namespace=self.namespace)
                        total_ingested += 1
                except Exception as e:
                    logger.warning(f"Could not extract submodule {submod_name}: {e}")
        except ImportError as e:
            logger.warning(f"Pydantic not imported directly: {e}")

        canonical_triples = [
            Triple(
                source_id="class:pydantic.BaseModel",
                source_name="BaseModel",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.CONFIGURES.value,
                target_id="type:pydantic.ConfigDict",
                target_name="ConfigDict",
                target_type=SymbolType.CONFIG.value,
                metadata={"usage": "model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')"}
            ),
            Triple(
                source_id="decorator:pydantic.field_validator",
                source_name="field_validator",
                source_type=SymbolType.DECORATOR.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:pydantic.BaseModel",
                target_name="BaseModel",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "@field_validator('field_name', mode='after')\ndef validate_func(cls, v): return v"}
            ),
            Triple(
                source_id="decorator:pydantic.model_validator",
                source_name="model_validator",
                source_type=SymbolType.DECORATOR.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:pydantic.BaseModel",
                target_name="BaseModel",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "@model_validator(mode='after')\ndef validate_all(self): return self"}
            ),
            Triple(
                source_id="function:pydantic.Field",
                source_name="Field",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:pydantic.BaseModel",
                target_name="BaseModel",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "field_name: str = Field(..., description='Description', min_length=1)"}
            ),
            Triple(
                source_id="class:pydantic.BaseModel",
                source_name="BaseModel",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:pydantic.BaseModel.model_dump",
                target_name="model_dump",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "model_dump(self, *, mode='python', include=None, exclude=None, exclude_unset=False, exclude_defaults=False, exclude_none=False) -> dict"}
            ),
            Triple(
                source_id="class:pydantic.BaseModel",
                source_name="BaseModel",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:pydantic.BaseModel.model_validate",
                target_name="model_validate",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "model_validate(cls, obj: Any, *, strict=None, from_attributes=None, context=None) -> Model"}
            ),
        ]

        for t in canonical_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "pydantic", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_fastmcp(self) -> Dict[str, Any]:
        """Indexes FastMCP server patterns and decorators."""
        extractor = SymbolExtractor(library_name="fastmcp", namespace=self.namespace)
        total_ingested = 0

        try:
            import fastmcp
            for t in extractor.extract_from_module(fastmcp):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1
        except ImportError as e:
            logger.warning(f"FastMCP reflection error: {e}")

        fastmcp_triples = [
            Triple(
                source_id="class:fastmcp.FastMCP",
                source_name="FastMCP",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:fastmcp.FastMCP.tool",
                target_name="tool",
                target_type=SymbolType.DECORATOR.value,
                metadata={"usage": "@mcp.tool(name='custom_tool', description='Deskripsi')\ndef tool_func(arg: str) -> str: return arg"}
            ),
            Triple(
                source_id="class:fastmcp.FastMCP",
                source_name="FastMCP",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:fastmcp.FastMCP.run",
                target_name="run",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "run(self, transport='stdio' | 'sse') -> None"}
            ),
            Triple(
                source_id="class:fastmcp.Context",
                source_name="Context",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:fastmcp.FastMCP",
                target_name="FastMCP",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "async def tool_func(param: str, ctx: Context) -> str: ctx.info('Processing...'); return 'Done'"}
            )
        ]

        for t in fastmcp_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "fastmcp", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_langgraph(self) -> Dict[str, Any]:
        """Indexes LangGraph StateGraph, ReAct agent patterns, and transitions."""
        extractor = SymbolExtractor(library_name="langgraph", namespace=self.namespace)
        total_ingested = 0

        try:
            import langgraph
            for t in extractor.extract_from_module(langgraph):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1
        except ImportError as e:
            logger.warning(f"LangGraph reflection error: {e}")

        langgraph_triples = [
            Triple(
                source_id="class:langgraph.graph.StateGraph",
                source_name="StateGraph",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:langgraph.graph.StateGraph.add_node",
                target_name="add_node",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "add_node(self, node: str, action: Callable[..., Any]) -> Self"}
            ),
            Triple(
                source_id="class:langgraph.graph.StateGraph",
                source_name="StateGraph",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:langgraph.graph.StateGraph.add_edge",
                target_name="add_edge",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "add_edge(self, start_key: str, end_key: str) -> Self"}
            ),
            Triple(
                source_id="class:langgraph.graph.StateGraph",
                source_name="StateGraph",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:langgraph.graph.StateGraph.add_conditional_edges",
                target_name="add_conditional_edges",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "add_conditional_edges(self, source: str, path: Callable, path_map: dict | list) -> Self"}
            ),
            Triple(
                source_id="function:langgraph.prebuilt.create_react_agent",
                source_name="create_react_agent",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:langgraph.graph.StateGraph",
                target_name="StateGraph",
                target_type=SymbolType.CLASS.value,
                metadata={"signature": "create_react_agent(model: BaseChatModel, tools: Sequence[BaseTool], checkpointer: BaseCheckpointSaver = None) -> CompiledGraph"}
            )
        ]

        for t in langgraph_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "langgraph", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_httpx(self) -> Dict[str, Any]:
        """Indexes HTTPX async client, streaming, and response models."""
        extractor = SymbolExtractor(library_name="httpx", namespace=self.namespace)
        total_ingested = 0

        try:
            import httpx
            for t in extractor.extract_from_module(httpx):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1
        except ImportError as e:
            logger.warning(f"HTTPX reflection error: {e}")

        httpx_triples = [
            Triple(
                source_id="class:httpx.AsyncClient",
                source_name="AsyncClient",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:httpx.AsyncClient.stream",
                target_name="stream",
                target_type=SymbolType.METHOD.value,
                metadata={"usage": "async with httpx.AsyncClient(timeout=30.0) as client:\n    async with client.stream('GET', url) as response:\n        async for line in response.aiter_lines(): ..."}
            ),
            Triple(
                source_id="class:httpx.AsyncClient",
                source_name="AsyncClient",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:httpx.AsyncClient.post",
                target_name="post",
                target_type=SymbolType.METHOD.value,
                metadata={"signature": "post(self, url, *, content=None, data=None, files=None, json=None, params=None, headers=None, timeout=None) -> Response"}
            ),
        ]

        for t in httpx_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "httpx", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_psycopg(self) -> Dict[str, Any]:
        """Indexes Psycopg v3 PostgreSQL connection, cursors, and pool."""
        extractor = SymbolExtractor(library_name="psycopg", namespace=self.namespace)
        total_ingested = 0

        try:
            import psycopg
            for t in extractor.extract_from_module(psycopg):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1
        except ImportError as e:
            logger.warning(f"Psycopg reflection error: {e}")

        psycopg_triples = [
            Triple(
                source_id="function:psycopg.connect",
                source_name="connect",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.RETURNS_TYPE.value,
                target_id="class:psycopg.Connection",
                target_name="Connection",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "with psycopg.connect('host=localhost port=5432 dbname=mcp_knowledge user=postgres password=...') as conn:\n    with conn.cursor() as cur:\n        cur.execute('SELECT * FROM table WHERE id = %s', (id_val,))"}
            ),
            Triple(
                source_id="class:psycopg.AsyncConnection",
                source_name="AsyncConnection",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id="method:psycopg.AsyncConnection.cursor",
                target_name="cursor",
                target_type=SymbolType.METHOD.value,
                metadata={"usage": "async with await psycopg.AsyncConnection.connect(conn_str) as aconn:\n    async with aconn.cursor() as acur:\n        await acur.execute('SELECT 1')"}
            ),
        ]

        for t in psycopg_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "psycopg", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_sqlalchemy(self) -> Dict[str, Any]:
        """Indexes SQLAlchemy v2.0 Declarative Base, Mapped Columns, and Session queries."""
        total_ingested = 0

        sqla_triples = [
            Triple(
                source_id="class:sqlalchemy.orm.DeclarativeBase",
                source_name="DeclarativeBase",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.INHERITS_FROM.value,
                target_id="class:sqlalchemy.orm.Mapped",
                target_name="Mapped",
                target_type=SymbolType.TYPE_ALIAS.value,
                metadata={"usage": "class Base(DeclarativeBase):\n    pass\n\nclass User(Base):\n    __tablename__ = 'users'\n    id: Mapped[int] = mapped_column(primary_key=True)\n    name: Mapped[str] = mapped_column(String(50))"}
            ),
            Triple(
                source_id="function:sqlalchemy.select",
                source_name="select",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:sqlalchemy.orm.Session",
                target_name="Session",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "stmt = select(User).where(User.name == 'Admin')\nresults = session.scalars(stmt).all()"}
            ),
            Triple(
                source_id="function:sqlalchemy.orm.mapped_column",
                source_name="mapped_column",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.CONFIGURES.value,
                target_id="class:sqlalchemy.orm.Mapped",
                target_name="Mapped",
                target_type=SymbolType.TYPE_ALIAS.value,
                metadata={"signature": "mapped_column(*columns, init=True, primary_key=False, nullable=None, default=None, index=None)"}
            ),
            Triple(
                source_id="function:sqlalchemy.create_engine",
                source_name="create_engine",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.RETURNS_TYPE.value,
                target_id="class:sqlalchemy.Engine",
                target_name="Engine",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "engine = create_engine('postgresql+psycopg://user:pass@localhost/dbname', pool_size=10, max_overflow=20)"}
            ),
        ]

        for t in sqla_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "sqlalchemy", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_pgvector(self) -> Dict[str, Any]:
        """Indexes pgvector extension registration, distance operators, and vector types."""
        extractor = SymbolExtractor(library_name="pgvector", namespace=self.namespace)
        total_ingested = 0

        try:
            import pgvector
            for t in extractor.extract_from_module(pgvector):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1
        except ImportError as e:
            logger.warning(f"pgvector reflection error: {e}")

        pgvec_triples = [
            Triple(
                source_id="function:pgvector.psycopg.register_vector",
                source_name="register_vector",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.CONFIGURES.value,
                target_id="class:psycopg.Connection",
                target_name="Connection",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "from pgvector.psycopg import register_vector\nwith psycopg.connect(...) as conn:\n    register_vector(conn)"}
            ),
            Triple(
                source_id="class:pgvector.sqlalchemy.Vector",
                source_name="Vector",
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.CONFIGURES.value,
                target_id="class:sqlalchemy.orm.Mapped",
                target_name="Mapped",
                target_type=SymbolType.TYPE_ALIAS.value,
                metadata={"usage": "embedding: Mapped[list[float]] = mapped_column(Vector(768))"}
            ),
            Triple(
                source_id="concept:pgvector.distance_operators",
                source_name="Distance Operators",
                source_type=SymbolType.CONFIG.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:pgvector.sqlalchemy.Vector",
                target_name="Vector",
                target_type=SymbolType.CLASS.value,
                metadata={
                    "cosine_distance": "<=> (Cosine similarity: 1 - cosine_distance)",
                    "l2_distance": "<-> (Euclidean L2 distance)",
                    "inner_product": "<#> (Negative inner product)",
                    "hnsw_index_ddl": "CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
                }
            ),
        ]

        for t in pgvec_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "pgvector", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_sqlite_vec(self) -> Dict[str, Any]:
        """Indexes sqlite-vec extension loading and vector search SQL syntax."""
        sqlite_vec_triples = [
            Triple(
                source_id="function:sqlite_vec.load",
                source_name="load",
                source_type=SymbolType.FUNCTION.value,
                relation=SymbolRelation.CONFIGURES.value,
                target_id="class:sqlite3.Connection",
                target_name="Connection",
                target_type=SymbolType.CLASS.value,
                metadata={"usage": "import sqlite3, sqlite_vec\ndb = sqlite3.connect('memory.db')\ndb.enable_load_extension(True)\nsqlite_vec.load(db)\ndb.enable_load_extension(False)"}
            ),
            Triple(
                source_id="concept:sqlite_vec.vec0_virtual_table",
                source_name="vec0 Virtual Table",
                source_type=SymbolType.CONFIG.value,
                relation=SymbolRelation.REFERENCES.value,
                target_id="class:sqlite3.Connection",
                target_name="Connection",
                target_type=SymbolType.CLASS.value,
                metadata={"ddl": "CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[768]);\nSELECT rowid, distance FROM vec_items WHERE embedding MATCH ? ORDER BY distance LIMIT 5;"}
            ),
        ]

        total_ingested = 0
        for t in sqlite_vec_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "sqlite-vec", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}

    def index_alembic(self) -> Dict[str, Any]:
        """Indexes Alembic migration directives (op.create_table, op.add_column, etc.)."""
        extractor = SymbolExtractor(library_name="alembic", namespace=self.namespace)
        total_ingested = 0

        try:
            import alembic
            for t in extractor.extract_from_module(alembic):
                self.store.ingest_triple(t, namespace=self.namespace)
                total_ingested += 1
        except ImportError as e:
            logger.warning(f"Alembic reflection error: {e}")

        alembic_triples = [
            Triple(
                source_id="module:alembic.op",
                source_name="op",
                source_type=SymbolType.MODULE.value,
                relation=SymbolRelation.CONTAINS.value,
                target_id="function:alembic.op.create_table",
                target_name="create_table",
                target_type=SymbolType.FUNCTION.value,
                metadata={"usage": "op.create_table('new_table',\n    sa.Column('id', sa.Integer(), primary_key=True),\n    sa.Column('title', sa.String(length=100), nullable=False)\n)"}
            ),
            Triple(
                source_id="module:alembic.op",
                source_name="op",
                source_type=SymbolType.MODULE.value,
                relation=SymbolRelation.CONTAINS.value,
                target_id="function:alembic.op.add_column",
                target_name="add_column",
                target_type=SymbolType.FUNCTION.value,
                metadata={"usage": "op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))"}
            ),
            Triple(
                source_id="module:alembic.op",
                source_name="op",
                source_type=SymbolType.MODULE.value,
                relation=SymbolRelation.CONTAINS.value,
                target_id="function:alembic.op.create_index",
                target_name="create_index",
                target_type=SymbolType.FUNCTION.value,
                metadata={"usage": "op.create_index('idx_users_email', 'users', ['email'], unique=True)"}
            ),
        ]

        for t in alembic_triples:
            self.store.ingest_triple(t, namespace=self.namespace)
            total_ingested += 1

        return {"library": "alembic", "namespace": self.namespace, "triples_ingested": total_ingested, "status": "success"}
