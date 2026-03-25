"""
Semantic Text Chunker

Memecah teks panjang menjadi chunks yang lebih kecil
dengan mempertahankan konteks semantic.
"""

import re
from typing import List, Dict, Any, Optional


class SemanticChunker:
    """
    Chunker yang memecah teks berdasarkan:
    - Paragraph boundaries
    - Section headers
    - Fixed size dengan overlap
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target ukuran chunk (dalam karakter)
            chunk_overlap: Overlap antar chunks (dalam karakter)
            min_chunk_size: Minimum ukuran chunk yang valid
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk text menjadi pieces yang lebih kecil.
        
        Args:
            text: Text yang akan di-chunk
            metadata: Metadata untuk ditambahkan ke setiap chunk
            
        Returns:
            List of chunks dengan format:
            {
                "content": str,
                "index": int,
                "metadata": dict
            }
        """
        if not text or not text.strip():
            return []
        
        # Preprocess text
        text = self._preprocess_text(text)
        
        # Split berdasarkan semantic boundaries (paragraphs, headers)
        paragraphs = self._split_by_semantic_boundaries(text)
        
        # Combine paragraphs into chunks
        chunks = self._combine_into_chunks(paragraphs)
        
        # Format output dengan metadata
        result = []
        for i, chunk_text in enumerate(chunks):
            if len(chunk_text.strip()) >= self.min_chunk_size:
                chunk_metadata = {
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "char_count": len(chunk_text),
                    **(metadata or {})
                }
                
                result.append({
                    "content": chunk_text.strip(),
                    "index": i,
                    "metadata": chunk_metadata
                })
        
        return result
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text sebelum chunking.
        
        - Normalize whitespace
        - Remove excessive newlines
        """
        # Normalize newlines
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Normalize whitespace tapi preserve paragraph breaks
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def _split_by_semantic_boundaries(self, text: str) -> List[str]:
        """
        Split text berdasarkan semantic boundaries.
        
        Priorities:
        1. Section headers (## Header, === Header)
        2. Paragraph breaks
        3. Sentence boundaries
        """
        # Pattern untuk section headers
        header_patterns = [
            r'\n##+ .+\n',  # Markdown headers
            r'\n===.+===\n',  # Sheet headers
            r'\n--- .+ ---\n',  # Page markers
        ]
        
        # Coba split berdasarkan headers dulu
        for pattern in header_patterns:
            if re.search(pattern, text):
                parts = re.split(f'({pattern})', text)
                # Recombine header dengan content-nya
                combined = []
                i = 0
                while i < len(parts):
                    if i + 1 < len(parts) and re.match(pattern, parts[i]):
                        combined.append(parts[i] + parts[i + 1])
                        i += 2
                    else:
                        combined.append(parts[i])
                        i += 1
                return [p.strip() for p in combined if p.strip()]
        
        # Split berdasarkan paragraph breaks
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Jika paragraph terlalu panjang, split lebih lanjut
        result = []
        for para in paragraphs:
            if len(para) > self.chunk_size * 1.5:
                # Split by sentences
                sentences = self._split_by_sentences(para)
                result.extend(sentences)
            else:
                result.append(para)
        
        return result
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """Split text berdasarkan sentence boundaries."""
        # Simple sentence splitting (Indonesian + English)
        sentence_endings = r'[.!?。！？]+\s+'
        sentences = re.split(f'({sentence_endings})', text)
        
        # Recombine sentences dengan ending-nya
        result = []
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and re.match(sentence_endings, sentences[i + 1]):
                result.append(sentences[i] + sentences[i + 1])
                i += 2
            else:
                if sentences[i].strip():
                    result.append(sentences[i])
                i += 1
        
        return [s.strip() for s in result if s.strip()]
    
    def _combine_into_chunks(self, paragraphs: List[str]) -> List[str]:
        """
        Combine paragraphs into chunks dengan ukuran yang sesuai.
        
        Strategy:
        - Coba maintain paragraph boundaries
        - Jika paragraph terlalu panjang, split
        - Add overlap antar chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # Jika paragraph sendiri sudah terlalu panjang
            if para_size > self.chunk_size:
                # Save current chunk jika ada
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split paragraph
                para_chunks = self._split_long_paragraph(para)
                chunks.extend(para_chunks)
                continue
            
            # Cek jika adding paragraph akan melebihi chunk_size
            new_size = current_size + para_size + 2  # +2 for '\n\n'
            
            if new_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append('\n\n'.join(current_chunk))
                
                # Start new chunk dengan overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_size = len(overlap_text) + para_size + 2 if overlap_text else para_size
            else:
                current_chunk.append(para)
                current_size = new_size
        
        # Don't forget last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def _split_long_paragraph(self, para: str) -> List[str]:
        """Split paragraph yang terlalu panjang."""
        chunks = []
        start = 0
        
        while start < len(para):
            end = start + self.chunk_size
            
            if end >= len(para):
                chunks.append(para[start:])
                break
            
            # Coba break di word boundary
            while end > start and para[end] not in ' \n':
                end -= 1
            
            if end == start:
                # Force break
                end = start + self.chunk_size
            
            chunks.append(para[start:end].strip())
            
            # Move start dengan overlap
            start = end - self.chunk_overlap
            if start < 0:
                start = 0
        
        return chunks
    
    def _get_overlap_text(self, chunks: List[str]) -> str:
        """Get overlap text dari chunks sebelumnya."""
        if not chunks:
            return ""
        
        # Ambil text dari chunks terakhir untuk overlap
        last_chunk = chunks[-1]
        
        if len(last_chunk) <= self.chunk_overlap:
            return last_chunk
        
        # Ambil bagian akhir
        overlap = last_chunk[-self.chunk_overlap:]
        
        # Coba start dari word boundary
        if ' ' in overlap:
            overlap = overlap[overlap.find(' '):].strip()
        
        return overlap