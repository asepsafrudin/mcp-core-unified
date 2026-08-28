"""
AST & Inspection-based Python Symbol Extractor for Knowledge Graph (TASK-123).
Extracts classes, methods, signatures, docstrings, and relationships into Knowledge Graph Triples.
"""

import ast
import inspect
import importlib
import types
from typing import List, Dict, Any, Optional, Tuple, Set

from memory.graph.schema import Triple
from memory.symbol_indexer.schema import SymbolType, SymbolRelation, SymbolDefinition, ParameterInfo


class SymbolExtractor:
    """
    Extracts structural code symbols and converts them to Graph Memory Triples.
    Can operate via runtime inspection or static AST parsing.
    """

    def __init__(self, library_name: str = "pydantic", namespace: str = "code_symbols"):
        self.library_name = library_name
        self.namespace = namespace

    def extract_from_module(self, module_obj: types.ModuleType, recursive_depth: int = 1) -> List[Triple]:
        """
        Extract symbols from a live imported module object.
        """
        triples: List[Triple] = []
        module_name = getattr(module_obj, "__name__", self.library_name)
        module_id = f"module:{module_name}"

        # 1. Module Root Triple
        triples.append(Triple(
            source_id=f"lib:{self.library_name}",
            source_name=self.library_name,
            source_type=SymbolType.MODULE.value,
            relation=SymbolRelation.CONTAINS.value,
            target_id=module_id,
            target_name=module_name,
            target_type=SymbolType.MODULE.value,
            metadata={"doc": inspect.getdoc(module_obj) or ""}
        ))

        # 2. Iterate members of the module
        for member_name, member in inspect.getmembers(module_obj):
            if member_name.startswith("_") and not member_name.startswith("__init__"):
                continue

            # A. Classes
            if inspect.isclass(member) and getattr(member, "__module__", "").startswith(self.library_name):
                class_triples = self._extract_class_symbols(member, module_id)
                triples.extend(class_triples)

            # B. Top-level Functions / Decorators
            elif (inspect.isfunction(member) or inspect.isbuiltin(member)) and getattr(member, "__module__", "").startswith(self.library_name):
                func_triples = self._extract_function_symbols(member, module_id)
                triples.extend(func_triples)

        return triples

    def _extract_class_symbols(self, cls: type, module_id: str) -> List[Triple]:
        """Extract a class, its inheritance, methods, and configurations."""
        triples: List[Triple] = []
        class_name = cls.__name__
        class_id = f"class:{cls.__module__}.{class_name}"
        docstring = inspect.getdoc(cls) or ""

        # Class definition triple (Module -> Class)
        triples.append(Triple(
            source_id=module_id,
            source_name=module_id.replace("module:", ""),
            source_type=SymbolType.MODULE.value,
            relation=SymbolRelation.CONTAINS.value,
            target_id=class_id,
            target_name=class_name,
            target_type=SymbolType.CLASS.value,
            metadata={"docstring": docstring[:500], "module": cls.__module__}
        ))

        # Base classes (Inheritance)
        for base in cls.__bases__:
            if base is object:
                continue
            base_id = f"class:{base.__module__}.{base.__name__}"
            triples.append(Triple(
                source_id=class_id,
                source_name=class_name,
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.INHERITS_FROM.value,
                target_id=base_id,
                target_name=base.__name__,
                target_type=SymbolType.CLASS.value
            ))

        # Methods inside Class
        for name, method in inspect.getmembers(cls, predicate=lambda m: inspect.isfunction(m) or inspect.ismethod(m)):
            if name.startswith("_") and name not in ("__init__", "__call__", "__repr__"):
                continue

            method_id = f"method:{cls.__module__}.{class_name}.{name}"
            sig_str = ""
            params_list = []
            try:
                sig = inspect.signature(method)
                sig_str = f"{name}{sig}"
                for p_name, param in sig.parameters.items():
                    if p_name in ("self", "cls"):
                        continue
                    p_type = str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any"
                    p_default = str(param.default) if param.default != inspect.Parameter.empty else None
                    params_list.append({
                        "name": p_name,
                        "type": p_type,
                        "default": p_default
                    })
            except Exception:
                sig_str = f"{name}(...)"

            method_doc = inspect.getdoc(method) or ""

            # Class -> Method
            triples.append(Triple(
                source_id=class_id,
                source_name=class_name,
                source_type=SymbolType.CLASS.value,
                relation=SymbolRelation.HAS_METHOD.value,
                target_id=method_id,
                target_name=name,
                target_type=SymbolType.METHOD.value,
                metadata={
                    "signature": sig_str,
                    "docstring": method_doc[:500],
                    "parameters": params_list
                }
            ))

        return triples

    def _extract_function_symbols(self, func: Any, module_id: str) -> List[Triple]:
        """Extract a standalone function or decorator."""
        triples: List[Triple] = []
        func_name = getattr(func, "__name__", str(func))
        func_id = f"function:{getattr(func, '__module__', self.library_name)}.{func_name}"
        docstring = inspect.getdoc(func) or ""

        sig_str = ""
        params_list = []
        try:
            sig = inspect.signature(func)
            sig_str = f"{func_name}{sig}"
            for p_name, param in sig.parameters.items():
                p_type = str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any"
                p_default = str(param.default) if param.default != inspect.Parameter.empty else None
                params_list.append({
                    "name": p_name,
                    "type": p_type,
                    "default": p_default
                })
        except Exception:
            sig_str = f"{func_name}(...)"

        triples.append(Triple(
            source_id=module_id,
            source_name=module_id.replace("module:", ""),
            source_type=SymbolType.MODULE.value,
            relation=SymbolRelation.CONTAINS.value,
            target_id=func_id,
            target_name=func_name,
            target_type=SymbolType.FUNCTION.value,
            metadata={
                "signature": sig_str,
                "docstring": docstring[:500],
                "parameters": params_list
            }
        ))

        return triples

    def extract_from_source_code(self, source_code: str, module_name: str = "custom_module") -> List[Triple]:
        """
        Static AST extraction without importing the module.
        Useful for raw source files or remote libraries.
        """
        triples: List[Triple] = []
        tree = ast.parse(source_code)
        module_id = f"module:{module_name}"

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_id = f"class:{module_name}.{node.name}"
                docstring = ast.get_docstring(node) or ""

                triples.append(Triple(
                    source_id=module_id,
                    source_name=module_name,
                    source_type=SymbolType.MODULE.value,
                    relation=SymbolRelation.CONTAINS.value,
                    target_id=class_id,
                    target_name=node.name,
                    target_type=SymbolType.CLASS.value,
                    metadata={"docstring": docstring[:500]}
                ))

                # Base classes
                for base in node.bases:
                    base_name = ast.unparse(base) if hasattr(ast, "unparse") else "Base"
                    triples.append(Triple(
                        source_id=class_id,
                        source_name=node.name,
                        source_type=SymbolType.CLASS.value,
                        relation=SymbolRelation.INHERITS_FROM.value,
                        target_id=f"class:{base_name}",
                        target_name=base_name,
                        target_type=SymbolType.CLASS.value
                    ))

                # Class Methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"method:{module_name}.{node.name}.{item.name}"
                        method_doc = ast.get_docstring(item) or ""
                        triples.append(Triple(
                            source_id=class_id,
                            source_name=node.name,
                            source_type=SymbolType.CLASS.value,
                            relation=SymbolRelation.HAS_METHOD.value,
                            target_id=method_id,
                            target_name=item.name,
                            target_type=SymbolType.METHOD.value,
                            metadata={"docstring": method_doc[:500]}
                        ))

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"function:{module_name}.{node.name}"
                func_doc = ast.get_docstring(node) or ""
                triples.append(Triple(
                    source_id=module_id,
                    source_name=module_name,
                    source_type=SymbolType.MODULE.value,
                    relation=SymbolRelation.CONTAINS.value,
                    target_id=func_id,
                    target_name=node.name,
                    target_type=SymbolType.FUNCTION.value,
                    metadata={"docstring": func_doc[:500]}
                ))

        return triples
