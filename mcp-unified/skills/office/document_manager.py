"""
Document Manager Skill for Office Document Operations
"""
from typing import Dict, List, Optional, Any
from skills.base import BaseSkill, register_skill
from tools.office.docx_tools import read_docx, write_docx, extract_text_docx, edit_docx
from tools.office.xlsx_tools import read_xlsx, write_xlsx, extract_data_xlsx, edit_xlsx, format_xlsx


@register_skill
class DocumentManagerSkill(BaseSkill):
    """
    Skill for managing Office documents (DOCX, XLSX)
    Provides high-level operations for document creation, modification, and analysis
    """
    
    skill_name = "document_manager"
    skill_description = "Manage and manipulate Office documents (Word and Excel)"
    skill_complexity = "medium"
    
    def __init__(self):
        super().__init__()
        self.supported_formats = ['.docx', '.xlsx']
    
    async def create_document(
        self,
        file_path: str,
        content: List[Dict],
        title: Optional[str] = None,
        author: Optional[str] = None
    ) -> Dict:
        """
        Create a new Office document
        
        Args:
            file_path: Path where document will be saved
            content: List of content items
            title: Document title
            author: Document author
            
        Returns:
            Operation result
        """
        if file_path.endswith('.docx'):
            return write_docx(file_path, content, title, author)
        elif file_path.endswith('.xlsx'):
            # Convert content to sheet data format
            sheet_data = {}
            for item in content:
                if item.get('type') == 'table':
                    sheet_name = item.get('sheet_name', 'Sheet1')
                    sheet_data[sheet_name] = item.get('data', [])
            return write_xlsx(file_path, sheet_data)
        else:
            return {
                'success': False,
                'error': f'Unsupported format. Use: {self.supported_formats}'
            }
    
    async def read_document(self, file_path: str, **options) -> Dict:
        """
        Read and parse an Office document
        
        Args:
            file_path: Path to document
            **options: Format-specific options
            
        Returns:
            Document content and metadata
        """
        if file_path.endswith('.docx'):
            return read_docx(file_path)
        elif file_path.endswith('.xlsx'):
            sheet_name = options.get('sheet_name')
            return read_xlsx(file_path, sheet_name)
        else:
            return {
                'success': False,
                'error': f'Unsupported format. Use: {self.supported_formats}'
            }
    
    async def extract_text(self, file_path: str, **options) -> Dict:
        """
        Extract text content from document
        
        Args:
            file_path: Path to document
            **options: Extraction options
            
        Returns:
            Extracted text and statistics
        """
        if file_path.endswith('.docx'):
            include_tables = options.get('include_tables', True)
            return extract_text_docx(file_path, include_tables)
        elif file_path.endswith('.xlsx'):
            return extract_data_xlsx(
                file_path,
                sheet_name=options.get('sheet_name'),
                has_headers=options.get('has_headers', True)
            )
        else:
            return {
                'success': False,
                'error': f'Unsupported format. Use: {self.supported_formats}'
            }
    
    async def edit_document(self, file_path: str, edits: List[Dict]) -> Dict:
        """
        Edit an existing document
        
        Args:
            file_path: Path to document
            edits: List of edit operations
            
        Returns:
            Edit result
        """
        if file_path.endswith('.docx'):
            return edit_docx(file_path, edits)
        elif file_path.endswith('.xlsx'):
            return edit_xlsx(file_path, edits)
        else:
            return {
                'success': False,
                'error': f'Unsupported format. Use: {self.supported_formats}'
            }
    
    async def analyze_document(self, file_path: str) -> Dict:
        """
        Analyze document structure and content
        
        Args:
            file_path: Path to document
            
        Returns:
            Document analysis
        """
        result = await self.read_document(file_path)
        
        if not result.get('success'):
            return result
        
        analysis = {
            'file_path': file_path,
            'file_type': 'docx' if file_path.endswith('.docx') else 'xlsx',
            'success': True
        }
        
        if file_path.endswith('.docx'):
            paragraphs = result.get('paragraphs', [])
            tables = result.get('tables', [])
            metadata = result.get('metadata', {})
            
            # Calculate statistics
            total_words = sum(len(p['text'].split()) for p in paragraphs)
            total_chars = sum(len(p['text']) for p in paragraphs)
            
            analysis.update({
                'document_stats': {
                    'paragraph_count': len(paragraphs),
                    'table_count': len(tables),
                    'total_words': total_words,
                    'total_characters': total_chars,
                    'average_words_per_paragraph': total_words / len(paragraphs) if paragraphs else 0
                },
                'structure': {
                    'has_title': any(p['style'] == 'Title' for p in paragraphs),
                    'has_headings': any('Heading' in p['style'] for p in paragraphs),
                    'heading_count': sum(1 for p in paragraphs if 'Heading' in p['style'])
                },
                'metadata': metadata.get('core_properties', {})
            })
            
        elif file_path.endswith('.xlsx'):
            sheets = result.get('sheets', {})
            sheet_names = result.get('sheet_names', [])
            
            total_rows = sum(s['max_row'] for s in sheets.values())
            total_cells = sum(s['max_row'] * s['max_column'] for s in sheets.values())
            
            analysis.update({
                'workbook_stats': {
                    'sheet_count': len(sheet_names),
                    'total_rows': total_rows,
                    'total_cells': total_cells,
                    'sheets': {
                        name: {
                            'rows': s['max_row'],
                            'columns': s['max_column'],
                            'has_headers': len(s['rows']) > 0
                        }
                        for name, s in sheets.items()
                    }
                }
            })
        
        return analysis
    
    async def compare_documents(self, file_path1: str, file_path2: str) -> Dict:
        """
        Compare two documents and identify differences
        
        Args:
            file_path1: Path to first document
            file_path2: Path to second document
            
        Returns:
            Comparison results
        """
        doc1 = await self.extract_text(file_path1)
        doc2 = await self.extract_text(file_path2)
        
        if not doc1.get('success') or not doc2.get('success'):
            return {
                'success': False,
                'error': 'Failed to read one or both documents'
            }
        
        text1 = doc1.get('text', '').split('\n')
        text2 = doc2.get('text', '').split('\n')
        
        # Simple line-by-line comparison
        added = []
        removed = []
        
        # Find removed lines
        for line in text1:
            if line not in text2:
                removed.append(line)
        
        # Find added lines
        for line in text2:
            if line not in text1:
                added.append(line)
        
        return {
            'success': True,
            'file1': file_path1,
            'file2': file_path2,
            'comparison': {
                'lines_removed': removed,
                'lines_added': added,
                'removed_count': len(removed),
                'added_count': len(added),
                'has_changes': len(added) > 0 or len(removed) > 0
            },
            'statistics': {
                'file1_word_count': doc1.get('total_words', 0),
                'file2_word_count': doc2.get('total_words', 0),
                'word_difference': doc2.get('total_words', 0) - doc1.get('total_words', 0)
            }
        }
    
    async def batch_process(
        self,
        file_paths: List[str],
        operation: str,
        **kwargs
    ) -> Dict:
        """
        Process multiple documents with same operation
        
        Args:
            file_paths: List of document paths
            operation: Operation to perform ('read', 'extract', 'analyze')
            **kwargs: Operation-specific arguments
            
        Returns:
            Batch processing results
        """
        results = []
        errors = []
        
        for file_path in file_paths:
            try:
                if operation == 'read':
                    result = await self.read_document(file_path, **kwargs)
                elif operation == 'extract':
                    result = await self.extract_text(file_path, **kwargs)
                elif operation == 'analyze':
                    result = await self.analyze_document(file_path)
                else:
                    result = {'success': False, 'error': f'Unknown operation: {operation}'}
                
                results.append({
                    'file_path': file_path,
                    'result': result,
                    'success': result.get('success', False)
                })
            except Exception as e:
                errors.append({
                    'file_path': file_path,
                    'error': str(e)
                })
        
        successful = sum(1 for r in results if r['success'])
        
        return {
            'success': True,
            'operation': operation,
            'total_files': len(file_paths),
            'successful': successful,
            'failed': len(file_paths) - successful,
            'results': results,
            'errors': errors
        }
