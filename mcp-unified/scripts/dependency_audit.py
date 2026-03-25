#!/usr/bin/env python3
"""
Dependency Architecture Audit Tool
TASK-025: Phase 1 - Generate dependency graph
"""

import os
import sys
import ast
from pathlib import Path
from collections import defaultdict

# Project root
PROJECT_ROOT = Path("/home/aseps/MCP/mcp-unified")
OUTPUT_DIR = Path("/home/aseps/MCP/docs/04-operations")

def find_python_files():
    """Find all Python files in the project."""
    python_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Skip __pycache__ and test directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.pytest_cache']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    return python_files

def extract_imports(file_path):
    """Extract all imports from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return [], []
    
    imports = []
    from_imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            names = [alias.name for alias in node.names]
            from_imports.append((module, names))
    
    return imports, from_imports

def categorize_import(import_path, source_file):
    """Categorize an import based on source and target."""
    # Internal imports (from mcp-unified)
    if import_path.startswith('mcp_unified') or import_path.startswith('.'):
        return 'internal'
    
    # External imports
    external_libs = ['fastapi', 'uvicorn', 'pydantic', 'sqlalchemy', 'asyncpg', 
                     'numpy', 'pandas', 'httpx', 'requests', 'jwt', 'bcrypt',
                     'psycopg2', 'pgvector', 'torch', 'transformers', 'openai',
                     'anthropic', 'google', 'bs4', 'yaml', 'toml', 'dotenv']
    
    for lib in external_libs:
        if import_path.startswith(lib):
            return 'external'
    
    # Standard library
    std_libs = ['os', 'sys', 'json', 're', 'time', 'datetime', 'pathlib', 
                'typing', 'abc', 'inspect', 'importlib', 'asyncio', 'uuid',
                'hashlib', 'base64', 'collections', 'functools', 'itertools']
    
    for lib in std_libs:
        if import_path.startswith(lib):
            return 'stdlib'
    
    return 'unknown'

def analyze_dependencies():
    """Main analysis function."""
    print("🔍 Starting Dependency Architecture Audit...")
    print("=" * 70)
    
    python_files = find_python_files()
    print(f"📁 Found {len(python_files)} Python files")
    
    # Layer detection
    layers = {
        'core': [],
        'tools': [],
        'skills': [],
        'agents': [],
        'adapters': [],
        'tests': [],
        'other': []
    }
    
    # Dependencies mapping
    deps = defaultdict(list)
    
    # Circular dependency candidates
    circular_candidates = []
    
    for file_path in python_files:
        rel_path = file_path.relative_to(PROJECT_ROOT)
        
        # Determine layer
        if 'tests/' in str(rel_path):
            layers['tests'].append(str(rel_path))
        elif 'core/' in str(rel_path):
            layers['core'].append(str(rel_path))
        elif 'tools/' in str(rel_path):
            layers['tools'].append(str(rel_path))
        elif 'skills/' in str(rel_path):
            layers['skills'].append(str(rel_path))
        elif 'agents/' in str(rel_path):
            layers['agents'].append(str(rel_path))
        elif 'adapters/' in str(rel_path) or 'execution/' in str(rel_path):
            layers['adapters'].append(str(rel_path))
        else:
            layers['other'].append(str(rel_path))
        
        # Extract imports
        imports, from_imports = extract_imports(file_path)
        
        for module, names in from_imports:
            # Skip relative imports for now
            if module.startswith('.'):
                continue
                
            # Check for cross-layer imports
            source_layer = get_layer(str(rel_path))
            target_layer = get_layer_from_import(module)
            
            if source_layer and target_layer and source_layer != target_layer:
                deps[source_layer].append({
                    'source': str(rel_path),
                    'target': target_layer,
                    'module': module,
                    'names': names
                })
                
                # Check for reverse dependency (circular)
                for existing in deps[target_layer]:
                    if existing['target'] == source_layer:
                        circular_candidates.append({
                            'a': str(rel_path),
                            'b': existing['source'],
                            'layer_a': source_layer,
                            'layer_b': target_layer
                        })
    
    # Print summary
    print("\n📊 Layer Distribution:")
    for layer, files in layers.items():
        if files:
            print(f"  {layer}: {len(files)} files")
    
    print("\n🔗 Cross-Layer Dependencies:")
    for layer, dependencies in deps.items():
        if dependencies:
            print(f"\n  {layer.upper()} imports from:")
            targets = defaultdict(list)
            for dep in dependencies:
                targets[dep['target']].append(dep['module'])
            
            for target, modules in targets.items():
                print(f"    → {target}: {len(set(modules))} unique modules")
    
    # Check architecture violations
    print("\n⚠️  Architecture Violations:")
    violations = []
    
    # Rule: Core should NOT import from other layers
    for dep in deps['core']:
        if dep['target'] in ['tools', 'skills', 'agents', 'adapters']:
            violations.append({
                'rule': 'Core imports from upper layers',
                'source': dep['source'],
                'target': dep['target'],
                'module': dep['module']
            })
    
    # Rule: Tools should NOT import from skills/agents/adapters
    for dep in deps['tools']:
        if dep['target'] in ['skills', 'agents', 'adapters']:
            violations.append({
                'rule': 'Tools imports from upper layers',
                'source': dep['source'],
                'target': dep['target'],
                'module': dep['module']
            })
    
    # Rule: Skills should NOT import from agents/adapters
    for dep in deps['skills']:
        if dep['target'] in ['agents', 'adapters']:
            violations.append({
                'rule': 'Skills imports from upper layers',
                'source': dep['source'],
                'target': dep['target'],
                'module': dep['module']
            })
    
    if violations:
        for v in violations[:10]:  # Show first 10
            print(f"  ❌ {v['rule']}")
            print(f"     {v['source']} → {v['target']} ({v['module']})")
        if len(violations) > 10:
            print(f"     ... and {len(violations) - 10} more")
    else:
        print("  ✅ No violations found")
    
    # Circular dependencies
    print("\n🔄 Circular Dependencies:")
    if circular_candidates:
        for c in circular_candidates[:5]:
            print(f"  ⚠️  {c['layer_a']} ↔ {c['layer_b']}")
            print(f"     {c['a']} <-> {c['b']}")
    else:
        print("  ✅ No circular dependencies detected")
    
    # Generate report
    generate_report(layers, deps, violations, circular_candidates)
    
    return layers, deps, violations

def get_layer(file_path):
    """Determine which layer a file belongs to."""
    if 'tests/' in file_path:
        return 'tests'
    elif 'core/' in file_path:
        return 'core'
    elif 'tools/' in file_path:
        return 'tools'
    elif 'skills/' in file_path:
        return 'skills'
    elif 'agents/' in file_path:
        return 'agents'
    elif 'adapters/' in file_path or 'execution/' in file_path:
        return 'adapters'
    return None

def get_layer_from_import(module):
    """Determine target layer from import module."""
    if module.startswith('core'):
        return 'core'
    elif module.startswith('tools'):
        return 'tools'
    elif module.startswith('skills'):
        return 'skills'
    elif module.startswith('agents'):
        return 'agents'
    elif module.startswith('adapters') or module.startswith('execution'):
        return 'adapters'
    return None

def generate_report(layers, deps, violations, circular):
    """Generate markdown report."""
    report_path = OUTPUT_DIR / 'dependency-audit-report.md'
    
    with open(report_path, 'w') as f:
        f.write("# Dependency Architecture Audit Report\n\n")
        f.write("**Task:** TASK-025\n")
        f.write("**Date:** Generated automatically\n")
        f.write("**Status:** Phase 1 - Audit\n\n")
        
        f.write("## 📊 Summary\n\n")
        f.write("### Layer Distribution\n\n")
        for layer, files in layers.items():
            if files:
                f.write(f"- **{layer}**: {len(files)} files\n")
        
        f.write("\n### Cross-Layer Dependencies\n\n")
        for layer, dependencies in deps.items():
            if dependencies:
                f.write(f"#### {layer.upper()} imports from:\n")
                targets = defaultdict(set)
                for dep in dependencies:
                    targets[dep['target']].add(dep['module'])
                
                for target, modules in targets.items():
                    f.write(f"- **{target}**: {len(modules)} modules\n")
                    for mod in list(modules)[:5]:
                        f.write(f"  - `{mod}`\n")
                    if len(modules) > 5:
                        f.write(f"  - ... and {len(modules) - 5} more\n")
                f.write("\n")
        
        f.write("## ⚠️ Architecture Violations\n\n")
        if violations:
            f.write(f"**Total:** {len(violations)} violations\n\n")
            for v in violations:
                f.write(f"- **{v['rule']}**\n")
                f.write(f"  - Source: `{v['source']}`\n")
                f.write(f"  - Target: `{v['target']}` ({v['module']})\n")
        else:
            f.write("✅ No violations found\n")
        
        f.write("\n## 🔄 Circular Dependencies\n\n")
        if circular:
            f.write(f"**Total:** {len(circular)} potential circular dependencies\n\n")
            for c in circular:
                f.write(f"- `{c['layer_a']}` ↔ `{c['layer_b']}`\n")
        else:
            f.write("✅ No circular dependencies detected\n")
        
        f.write("\n## 📝 Recommendations\n\n")
        f.write("Based on the audit results:\n\n")
        
        if violations:
            f.write("### Immediate Actions\n\n")
            f.write("1. Fix architecture violations listed above\n")
            f.write("2. Ensure one-way dependency flow: core → tools → skills → agents\n")
            f.write("3. Remove or reposition adapters layer\n\n")
        
        f.write("### Clean Architecture Target\n\n")
        f.write("```\n")
        f.write("agents/     → can import: skills, tools, core\n")
        f.write("skills/     → can import: tools, core\n")
        f.write("tools/      → can import: core only\n")
        f.write("core/       → no internal imports\n")
        f.write("adapters/   → TO BE REMOVED\n")
        f.write("```\n")
    
    print(f"\n📝 Report saved to: {report_path}")

if __name__ == "__main__":
    layers, deps, violations = analyze_dependencies()
    
    print("\n" + "=" * 70)
    print("✅ Dependency Audit Complete!")
    print("=" * 70)
    
    if violations:
        print(f"\n⚠️  Found {len(violations)} architecture violations")
        print("Next: Phase 2 - Define dependency rules")
    else:
        print("\n✅ No violations found - architecture is clean!")
