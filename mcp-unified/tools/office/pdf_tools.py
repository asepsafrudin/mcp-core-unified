"""
PDF Tools for conversion and text extraction
"""
from pathlib import Path
from typing import Dict, Optional

from tools.base import register_tool


@register_tool
def convert_to_pdf(
    input_path: str,
    output_path: Optional[str] = None
) -> Dict:
    """
    Convert DOCX or XLSX to PDF
    Note: This requires external libraries like docx2pdf or LibreOffice
    
    Args:
        input_path: Path to input file (.docx or .xlsx)
        output_path: Path for output PDF (default: same name with .pdf)
        
    Returns:
        Success status and details
    """
    try:
        input_file = Path(input_path)
        
        if not input_file.exists():
            return {
                'success': False,
                'error': f'Input file not found: {input_path}'
            }
        
        # Set default output path
        if output_path is None:
            output_path = str(input_file.with_suffix('.pdf'))
        
        file_extension = input_file.suffix.lower()
        
        if file_extension == '.docx':
            # Try docx2pdf for DOCX conversion
            try:
                from docx2pdf import convert
                convert(input_path, output_path)
                return {
                    'success': True,
                    'input_path': input_path,
                    'output_path': output_path,
                    'conversion_type': 'DOCX to PDF',
                    'method': 'docx2pdf'
                }
            except ImportError:
                return {
                    'success': False,
                    'error': 'docx2pdf not installed. Install with: pip install docx2pdf',
                    'note': 'On Linux, docx2pdf may not work. Use LibreOffice instead.'
                }
                
        elif file_extension in ['.xlsx', '.xls']:
            # For Excel, we need external tools
            return {
                'success': False,
                'error': 'Excel to PDF conversion requires external tools',
                'solutions': [
                    'Use LibreOffice: libreoffice --headless --convert-to pdf',
                    'Use Microsoft Excel with COM automation',
                    'Use online conversion services'
                ]
            }
        else:
            return {
                'success': False,
                'error': f'Unsupported file format: {file_extension}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'input_path': input_path
        }


@register_tool
def extract_text_pdf(
    file_path: str,
    page_range: Optional[tuple] = None
) -> Dict:
    """
    Extract text from PDF file
    
    Args:
        file_path: Path to PDF file
        page_range: Optional tuple (start_page, end_page) - 1-based indexing
        
    Returns:
        Success status and extracted text
    """
    try:
        # Try PyPDF2 first
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(file_path)
            num_pages = len(reader.pages)
            
            # Determine page range
            start_page = page_range[0] - 1 if page_range else 0  # Convert to 0-based
            end_page = page_range[1] if page_range else num_pages
            
            start_page = max(0, start_page)
            end_page = min(num_pages, end_page)
            
            # Extract text
            extracted_text = []
            for page_num in range(start_page, end_page):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text:
                    extracted_text.append(f'--- Page {page_num + 1} ---\n{text}')
            
            full_text = '\n\n'.join(extracted_text)
            
            return {
                'success': True,
                'file_path': file_path,
                'total_pages': num_pages,
                'pages_extracted': end_page - start_page,
                'text': full_text,
                'method': 'PyPDF2'
            }
            
        except ImportError:
            # Fallback to pdfplumber
            try:
                import pdfplumber
                
                with pdfplumber.open(file_path) as pdf:
                    num_pages = len(pdf.pages)
                    
                    start_page = page_range[0] - 1 if page_range else 0
                    end_page = page_range[1] if page_range else num_pages
                    
                    start_page = max(0, start_page)
                    end_page = min(num_pages, end_page)
                    
                    extracted_text = []
                    for page_num in range(start_page, end_page):
                        page = pdf.pages[page_num]
                        text = page.extract_text()
                        if text:
                            extracted_text.append(f'--- Page {page_num + 1} ---\n{text}')
                    
                    full_text = '\n\n'.join(extracted_text)
                    
                    return {
                        'success': True,
                        'file_path': file_path,
                        'total_pages': num_pages,
                        'pages_extracted': end_page - start_page,
                        'text': full_text,
                        'method': 'pdfplumber'
                    }
                    
            except ImportError:
                return {
                    'success': False,
                    'error': 'PDF libraries not installed. Install with: pip install PyPDF2 pdfplumber'
                }
                
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'file_path': file_path
        }


@register_tool
def get_pdf_info(file_path: str) -> Dict:
    """
    Get information about a PDF file
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        PDF metadata and information
    """
    try:
        from PyPDF2 import PdfReader
        
        reader = PdfReader(file_path)
        
        # Get metadata
        metadata = reader.metadata
        
        info = {
            'success': True,
            'file_path': file_path,
            'num_pages': len(reader.pages),
            'metadata': {
                'title': metadata.title if metadata else None,
                'author': metadata.author if metadata else None,
                'subject': metadata.subject if metadata else None,
                'creator': metadata.creator if metadata else None,
                'producer': metadata.producer if metadata else None,
                'creation_date': metadata.creation_date if metadata else None,
                'modification_date': metadata.modification_date if metadata else None,
            },
            'is_encrypted': reader.is_encrypted
        }
        
        return info
        
    except ImportError:
        return {
            'success': False,
            'error': 'PyPDF2 not installed. Install with: pip install PyPDF2'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'file_path': file_path
        }
