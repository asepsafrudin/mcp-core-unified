"""
Template processing tools using docxtpl
"""
import os
from typing import Dict, Any, List
from pathlib import Path
from docxtpl import DocxTemplate
from tools.base import register_tool


def validate_path(path_str: str, allowed_prefixes: List[str] = None) -> Path:
    """
    Validate path to prevent path traversal.
    Only allows paths that are within the allowed prefixes.
    
    Args:
        path_str: The path to validate
        allowed_prefixes: Directories where file access is allowed.
                          Defaults to ['/home/aseps/MCP', '/tmp']
                          
    Returns:
        Path object of the resolved absolute path
        
    Raises:
        PermissionError: If path lies outside the allowed prefixes
    """
    if allowed_prefixes is None:
        allowed_prefixes = ["/home/aseps/MCP", "/tmp"]
        
    path = Path(path_str).expanduser().resolve()
    path_str_abs = str(path)
    
    is_allowed = False
    for prefix in allowed_prefixes:
        prefix_abs = str(Path(prefix).expanduser().resolve())
        # Append path separator to prefix to ensure exact directory match
        if not prefix_abs.endswith(os.sep):
            prefix_abs += os.sep
            
        # Allowed if the path starts with prefix, or is exactly the prefix itself (minus trailing slash)
        if path_str_abs.startswith(prefix_abs) or path_str_abs == prefix_abs[:-1]:
            is_allowed = True
            break
            
    if not is_allowed:
        raise PermissionError(
            f"Access to path '{path_str}' is denied. "
            f"Path must be within one of: {allowed_prefixes}"
        )
        
    return path


@register_tool
def render_docx_template(
    template_path: str,
    output_path: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Render a DOCX template using docxtpl with context data.
    
    Args:
        template_path: Path to the template .docx file
        output_path: Path where the rendered file will be saved
        context: Dict containing template variables
        
    Returns:
        Dict indicating success status, output file path, and messages
    """
    try:
        # Validate paths
        t_path = validate_path(template_path)
        o_path = validate_path(output_path)
        
        # Check if template exists
        if not t_path.exists():
            return {
                'success': False,
                'error': f"Template file not found at: {template_path}"
            }
            
        # Ensure parent directory of output path exists
        o_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Render template
        doc = DocxTemplate(str(t_path))
        doc.render(context)
        doc.save(str(o_path))
        
        return {
            'success': True,
            'template_path': str(t_path),
            'output_path': str(o_path),
            'message': "Template rendered and saved successfully"
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'template_path': template_path,
            'output_path': output_path
        }
