import logging
import ast
import shutil
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class AdvancedRefactoring:
    def __init__(self, semantic_analyzer: SemanticAnalyzer):
        self.semantic_analyzer = semantic_analyzer
        self.backup_dir = Path('refactoring_backups')
        self.backup_dir.mkdir(exist_ok=True)

    def extract_method(self, file_path: str, line_no: int, new_method_name: str) -> Dict:
        """
        Mengekstrak code block menjadi method baru
        """
        try:
            # Backup file
            self._backup_file(file_path)

            # Baca file
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            # Validasi line number
            if line_no < 1 or line_no > len(lines):
                return {'error': 'Line number out of range'}

            # Temukan code block untuk diekstrak
            code_block, start_line, end_line = self._find_code_block(lines, line_no)

            if not code_block:
                return {'error': 'Could not identify code block to extract'}

            # Generate new method
            new_method = self._generate_method(code_block, new_method_name)

            # Update original file
            updated_lines = self._update_original_file(lines, start_line, end_line, new_method_name)

            # Write updated file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(updated_lines)

            # Add new method to class or module
            self._add_new_method(file_path, new_method)

            return {
                'success': True,
                'method_name': new_method_name,
                'lines_extracted': end_line - start_line + 1,
                'new_method': new_method
            }
        except Exception as e:
            logger.error(f"Error in extract_method: {e}")
            return {'error': str(e)}

    def _find_code_block(self, lines: List[str], line_no: int) -> Tuple[List[str], int, int]:
        """
        Menemukan code block yang akan diekstrak
        """
        try:
            # Cari awal block (cari indentasi yang sama)
            target_line = lines[line_no - 1]
            target_indent = len(target_line) - len(target_line.lstrip())

            # Expand ke atas dan bawah untuk temukan complete block
            start_line = line_no - 1
            end_line = line_no - 1

            # Expand ke atas
            while start_line > 0:
                current_line = lines[start_line - 1]
                current_indent = len(current_line) - len(current_line.lstrip())
                if current_indent < target_indent:
                    break
                start_line -= 1

            # Expand ke bawah
            while end_line < len(lines) - 1:
                current_line = lines[end_line + 1]
                current_indent = len(current_line) - len(current_line.lstrip())
                if current_indent < target_indent:
                    break
                end_line += 1

            # Extract code block
            code_block = lines[start_line:end_line + 1]
            return code_block, start_line, end_line
        except Exception as e:
            logger.error(f"Error finding code block: {e}")
            return [], 0, 0

    def _generate_method(self, code_block: List[str], method_name: str) -> str:
        """
        Generate method baru dari code block
        """
        try:
            # Tentukan indentasi
            indent = '    '  # 4 spaces
            method_indent = indent

            # Generate method signature
            method_lines = [
                f"def {method_name}():",
                ""
            ]

            # Add code block with proper indentation
            for line in code_block:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    method_lines.append(indent + line)
                else:
                    method_lines.append(line)

            # Add return statement if needed
            if not any('return' in line for line in code_block):
                method_lines.append("")
                method_lines.append(indent + "return None")

            return '\n'.join(method_lines)
        except Exception as e:
            logger.error(f"Error generating method: {e}")
            return ''

    def _update_original_file(self, lines: List[str], start_line: int, end_line: int, new_method_name: str) -> List[str]:
        """
        Update file original dengan memanggil method baru
        """
        try:
            # Replace code block dengan method call
            indent = '    '  # 4 spaces
            method_call = f"{indent}{new_method_name}()"

            # Replace lines
            updated_lines = lines[:start_line] + [method_call + '\n'] + lines[end_line + 1:]

            return updated_lines
        except Exception as e:
            logger.error(f"Error updating original file: {e}")
            return lines

    def _add_new_method(self, file_path: str, new_method: str):
        """
        Add method baru ke class atau module
        """
        try:
            # Baca file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Tentukan dimana method akan ditambahkan
            if 'class' in content:
                # Tambahkan ke class
                self._add_to_class(file_path, new_method)
            else:
                # Tambahkan ke module level
                self._add_to_module(file_path, new_method)
        except Exception as e:
            logger.error(f"Error adding new method: {e}")

    def _add_to_class(self, file_path: str, new_method: str):
        """
        Add method ke class
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            # Temukan class
            class_line_no = None
            for i, line in enumerate(lines):
                if line.strip().startswith('class '):
                    class_line_no = i
                    break

            if class_line_no is not None:
                # Tambahkan method setelah class definition
                indent = '    '  # 4 spaces
                method_lines = new_method.split('\n')
                formatted_method = [indent + line if line.strip() else line for line in method_lines]

                # Insert method
                lines = lines[:class_line_no + 1] + ['\n'] + formatted_method + ['\n'] + lines[class_line_no + 1:]

                # Write updated file
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.writelines(lines)
        except Exception as e:
            logger.error(f"Error adding method to class: {e}")

    def _add_to_module(self, file_path: str, new_method: str):
        """
        Add method ke module level
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Tambahkan method di akhir file
            new_content = content + '\n\n' + new_method + '\n'

            # Write updated file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(new_content)
        except Exception as e:
            logger.error(f"Error adding method to module: {e}")

    def rename_variable(self, file_path: str, old_name: str, new_name: str) -> Dict:
        """
        Rename variable di seluruh file
        """
        try:
            # Backup file
            self._backup_file(file_path)

            # Baca file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Parse AST untuk rename variable
            tree = ast.parse(content)
            changed = False

            class VariableRenamer(ast.NodeTransformer):
                def visit_Name(self, node):
                    if node.id == old_name:
                        new_node = ast.copy_location(ast.Name(new_name, node.ctx), node)
                        return new_node
                    return node

            # Apply transformation
            new_tree = VariableRenamer().visit(tree)
            ast.fix_missing_locations(new_tree)

            # Generate new code
            new_content = ast.unparse(new_tree)
            changed = content != new_content

            if changed:
                # Write updated file
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(new_content)

            return {
                'success': True,
                'old_name': old_name,
                'new_name': new_name,
                'changed': changed
            }
        except Exception as e:
            logger.error(f"Error in rename_variable: {e}")
            return {'error': str(e)}

    def extract_class(self, file_path: str, class_name: str, new_class_name: str) -> Dict:
        """
        Mengekstrak class menjadi class baru
        """
        try:
            # Backup file
            self._backup_file(file_path)

            # Baca file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Parse AST untuk temukan class
            tree = ast.parse(content)
            class_node = None

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    class_node = node
                    break

            if not class_node:
                return {'error': f'Class {class_name} not found'}

            # Generate new class
            new_class = self._generate_new_class(class_node, new_class_name)

            # Update original file
            updated_content = self._update_class_extraction(content, class_node, new_class_name)

            # Write updated file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(updated_content)

            # Create new file for extracted class
            new_file_path = Path(file_path).parent / f"{new_class_name.lower()}.py"
            with open(new_file_path, 'w', encoding='utf-8') as file:
                file.write(new_class)

            return {
                'success': True,
                'original_class': class_name,
                'new_class': new_class_name,
                'new_file': str(new_file_path)
            }
        except Exception as e:
            logger.error(f"Error in extract_class: {e}")
            return {'error': str(e)}

    def _generate_new_class(self, class_node: ast.ClassDef, new_class_name: str) -> str:
        """
        Generate new class dari class node
        """
        try:
            # Create new class definition
            class_lines = [
                f"class {new_class_name}:",
                ""
            ]

            # Add methods
            for node in class_node.body:
                if isinstance(node, ast.FunctionDef):
                    class_lines.append(ast.unparse(node))

            return '\n'.join(class_lines)
        except Exception as e:
            logger.error(f"Error generating new class: {e}")
            return ''

    def _update_class_extraction(self, content: str, class_node: ast.ClassDef, new_class_name: str) -> str:
        """
        Update file original setelah class extraction
        """
        try:
            # Replace class definition dengan import
            import_statement = f"from {new_class_name.lower()} import {new_class_name}"
            class_lines = ast.unparse(class_node).split('\n')
            class_definition = class_lines[0]  # Hanya class definition line

            # Replace class definition dengan import
            new_content = content.replace(class_definition, import_statement)

            return new_content
        except Exception as e:
            logger.error(f"Error updating class extraction: {e}")
            return content

    def inline_method(self, file_path: str, method_name: str) -> Dict:
        """
        Inline method ke tempat pemanggilannya
        """
        try:
            # Backup file
            self._backup_file(file_path)

            # Baca file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Parse AST untuk temukan method
            tree = ast.parse(content)
            method_node = None

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == method_name:
                    method_node = node
                    break

            if not method_node:
                return {'error': f'Method {method_name} not found'}

            # Inline method
            new_content = self._inline_method(content, method_node)

            # Write updated file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            return {
                'success': True,
                'method_name': method_name,
                'inlined': True
            }
        except Exception as e:
            logger.error(f"Error in inline_method: {e}")
            return {'error': str(e)}

    def _inline_method(self, content: str, method_node: ast.FunctionDef) -> str:
        """
        Inline method ke tempat pemanggilannya
        """
        try:
            # Parse AST
            tree = ast.parse(content)

            # Find method calls
            class MethodInliner(ast.NodeTransformer):
                def visit_Call(self, node):
                    if isinstance(node.func, ast.Name) and node.func.id == method_node.name:
                        # Replace method call dengan method body
                        new_node = ast.copy_location(ast.Expr(value=ast.Constant(value='INLINED')), node)
                        return new_node
                    return node

            # Apply transformation
            new_tree = MethodInliner().visit(tree)
            ast.fix_missing_locations(new_tree)

            # Generate new code
            new_content = ast.unparse(new_tree)
            return new_content
        except Exception as e:
            logger.error(f"Error inlining method: {e}")
            return content

    def _backup_file(self, file_path: str):
        """
        Backup file sebelum refactoring
        """
        try:
            original_path = Path(file_path)
            backup_path = self.backup_dir / f"{original_path.name}.bak"
            shutil.copy2(original_path, backup_path)
        except Exception as e:
            logger.error(f"Error creating backup: {e}")

    def get_refactoring_suggestions(self, file_path: str) -> Dict:
        """
        Mendapatkan saran refactoring untuk file
        """
        try:
            # Analisis file
            analysis = self.semantic_analyzer.analyze_file(file_path)

            # Generate suggestions
            suggestions = []

            # Check for long methods
            if 'ast' in analysis:
                for func in analysis['ast'].get('functions', []):
                    if len(func.get('args', [])) > 3:
                        suggestions.append({
                            'type': 'extract_method',
                            'description': f'Method {func["name"]} has many arguments, consider extracting',
                            'priority': 'medium'
                        })

            # Check for duplicate code
            # (Simplified implementation)
            suggestions.append({
                'type': 'extract_method',
                'description': 'Found duplicate code patterns, consider extracting to method',
                'priority': 'high'
            })

            return {
                'file': file_path,
                'suggestions': suggestions,
                'count': len(suggestions)
            }
        except Exception as e:
            logger.error(f"Error getting refactoring suggestions: {e}")
            return {'error': str(e)}