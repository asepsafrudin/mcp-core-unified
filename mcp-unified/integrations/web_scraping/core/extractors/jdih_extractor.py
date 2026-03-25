"""
JDIH Extractor - Ekstrak peraturan hukum dari JDIH (Jaringan Dokumentasi dan Informasi Hukum).

Features:
- Extract metadata peraturan (nomor, tahun, jenis)
- Extract full text content
- Parse PDF links
- Handle multiple JDIH sources
"""

import re
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_extractor import BaseExtractor, ExtractedContent


class JDIHExtractor(BaseExtractor):
    """
    Extractor untuk JDIH (Jaringan Dokumentasi dan Informasi Hukum).
    
    Supports (berdasarkan ranking kualitas):
    1. Hukumonline.com - PDF konsolidasi, searchable, metadata lengkap
    2. peraturan.go.id (Kemenkumham) - PDF resmi, status berlaku
    3. peraturan.bpk.go.id (BPK) - PDF akurat, standar JDIH
    4. jdih.mahkamahagung.go.id - Putusan & peraturan terkait
    5. pusatdata.hukumonline.com - Koleksi lengkap (74k+)
    6. jdih.kemendagri.go.id
    7. jdih.setneg.go.id
    8. Generic JDIH sites
    """
    
    URL_PATTERNS = [
        "https://jdih.kemendagri.go.id/*",
        "https://peraturan.go.id/*",
        "https://jdih.setneg.go.id/*",
        "https://*.jdih.go.id/*",
        "https://www.hukumonline.com/*",
        "https://hukumonline.com/*",
        "https://peraturan.bpk.go.id/*",
        "https://jdih.mahkamahagung.go.id/*",
        "https://pusatdata.hukumonline.com/*",
    ]
    
    DOMAINS = [
        "jdih.kemendagri.go.id",
        "peraturan.go.id",
        "jdih.setneg.go.id",
        "jdih.go.id",
        "hukumonline.com",
        "www.hukumonline.com",
        "peraturan.bpk.go.id",
        "jdih.mahkamahagung.go.id",
        "pusatdata.hukumonline.com",
    ]
    
    # Mapping jenis peraturan
    JENIS_PERATURAN = {
        "uu": "Undang-Undang",
        "perpres": "Peraturan Presiden",
        "permen": "Peraturan Menteri",
        "perda": "Peraturan Daerah",
        "perbup": "Peraturan Bupati",
        "perwali": "Peraturan Wali Kota",
        "kepres": "Keputusan Presiden",
        "kepmen": "Keputusan Menteri",
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize JDIH extractor."""
        super().__init__(config)
    
    def can_handle(self, url: str) -> bool:
        """Check if URL is a JDIH page."""
        return self._match_url_pattern(url)
    
    async def extract(self, page) -> ExtractedContent:
        """
        Extract peraturan dari JDIH page.
        
        Args:
            page: Playwright page object
            
        Returns:
            ExtractedContent dengan metadata peraturan
        """
        url = page.url
        domain = self._get_domain(url)
        
        # Extract berdasarkan domain
        if "kemendagri" in domain:
            return await self._extract_kemendagri(page, url)
        elif "peraturan.go.id" in domain:
            return await self._extract_peraturan_go_id(page, url)
        else:
            return await self._extract_generic_jdih(page, url)
    
    async def _extract_kemendagri(self, page, url: str) -> ExtractedContent:
        """Extract dari jdih.kemendagri.go.id"""
        
        # Wait untuk content
        await self._wait_for_selector(page, ".detail-peraturan", timeout=10000)
        
        # Extract metadata
        metadata_script = """
            () => {
                const data = {};
                
                // Judul
                data.judul = document.querySelector('h1')?.innerText?.trim() || '';
                
                // Detail tabel
                const rows = document.querySelectorAll('.detail-peraturan table tr');
                rows.forEach(row => {
                    const label = row.querySelector('td:first-child')?.innerText?.trim();
                    const value = row.querySelector('td:last-child')?.innerText?.trim();
                    
                    if (label && value) {
                        const key = label.toLowerCase()
                            .replace(/[^a-z0-9]/g, '_')
                            .replace(/_+/g, '_')
                            .replace(/_$/, '');
                        data[key] = value;
                    }
                });
                
                // Konten/teks peraturan
                const kontenEl = document.querySelector('.isi-peraturan, .content-peraturan');
                data.konten = kontenEl?.innerText?.trim() || '';
                
                // PDF link
                const pdfLink = document.querySelector('a[href$=".pdf"]');
                data.pdf_url = pdfLink?.href || '';
                
                return data;
            }
        """
        
        data = await page.evaluate(metadata_script)
        
        # Parse metadata
        jenis = self._detect_jenis_peraturan(data.get('jenis', data.get('jenis_peraturan', '')))
        nomor = self._extract_nomor(data.get('nomor', data.get('nomor_peraturan', '')))
        tahun = self._extract_tahun(data.get('tahun', data.get('tahun_peraturan', '')))
        
        # Build title
        title = data.get('judul', '')
        if not title:
            title = f"{jenis} Nomor {nomor} Tahun {tahun}" if all([jenis, nomor, tahun]) else "Peraturan Hukum"
        
        # Build content
        content_text = f"""# {title}

## Metadata
- **Jenis:** {jenis}
- **Nomor:** {nomor}
- **Tahun:** {tahun}
- **Judul:** {data.get('judul', '-')}
- **Tentang:** {data.get('tentang', data.get('judul', '-'))}
- **Status:** {data.get('status', '-')}
- **Ditetapkan:** {data.get('ditetapkan', data.get('tanggal_ditetapkan', '-'))}
- **Diundangkan:** {data.get('diundangkan', data.get('tanggal_diundangkan', '-'))}

## Isi Peraturan
{data.get('konten', 'Konten tidak tersedia dalam HTML.')}

## Dokumen
- PDF: {data.get('pdf_url', 'Tidak tersedia')}
- Sumber: {url}
"""
        
        metadata = {
            "source_type": "jdih",
            "jdih_source": "kemendagri",
            "jenis_peraturan": jenis,
            "nomor": nomor,
            "tahun": tahun,
            "pdf_url": data.get('pdf_url'),
            "status": data.get('status'),
            "ditetapkan": data.get('ditetapkan'),
            "diundangkan": data.get('diundangkan'),
        }
        
        return ExtractedContent(
            url=url,
            title=title,
            content=self._clean_text(content_text),
            metadata=metadata,
            extracted_at=datetime.now()
        )
    
    async def _extract_peraturan_go_id(self, page, url: str) -> ExtractedContent:
        """Extract dari peraturan.go.id"""
        
        data = await page.evaluate("""
            () => {
                const data = {};
                
                // Judul
                data.judul = document.querySelector('h1, .judul-peraturan')?.innerText?.trim() || '';
                
                // Metadata dari table atau list
                const metaElements = document.querySelectorAll('.metadata-peraturan li, .detail-peraturan tr');
                metaElements.forEach(el => {
                    const text = el.innerText;
                    if (text.includes(':')) {
                        const [key, value] = text.split(':').map(s => s.trim());
                        if (key && value) {
                            data[key.toLowerCase().replace(/\\s+/g, '_')] = value;
                        }
                    }
                });
                
                // Konten
                const kontenEl = document.querySelector('.isi-peraturan, .content, article');
                data.konten = kontenEl?.innerText?.trim() || '';
                
                // PDF
                const pdfLink = document.querySelector('a[href$=".pdf"], .download-pdf a');
                data.pdf_url = pdfLink?.href || '';
                
                return data;
            }
        """)
        
        jenis = self._detect_jenis_peraturan(data.get('jenis', ''))
        nomor = self._extract_nomor(data.get('nomor', ''))
        tahun = self._extract_tahun(data.get('tahun', ''))
        
        title = data.get('judul') or f"{jenis} Nomor {nomor} Tahun {tahun}"
        
        content_text = f"""# {title}

## Metadata
- **Jenis:** {jenis}
- **Nomor:** {nomor}
- **Tahun:** {tahun}
- **Tentang:** {data.get('tentang', data.get('judul', '-'))}

## Isi
{data.get('konten', 'Konten tidak tersedia.')}

## Dokumen
- PDF: {data.get('pdf_url', 'Tidak tersedia')}
"""
        
        return ExtractedContent(
            url=url,
            title=title,
            content=self._clean_text(content_text),
            metadata={
                "source_type": "jdih",
                "jdih_source": "peraturan.go.id",
                "jenis_peraturan": jenis,
                "nomor": nomor,
                "tahun": tahun,
                "pdf_url": data.get('pdf_url'),
            },
            extracted_at=datetime.now()
        )
    
    async def _extract_generic_jdih(self, page, url: str) -> ExtractedContent:
        """Generic extraction untuk JDIH lainnya."""
        
        data = await page.evaluate("""
            () => {
                const data = {};
                
                // Try various selectors for title
                data.judul = document.querySelector('h1, .page-title, .judul')?.innerText?.trim() || '';
                
                // Get all text content
                data.full_text = document.body.innerText;
                
                // Look for PDF
                const pdfLink = document.querySelector('a[href$=".pdf"]');
                data.pdf_url = pdfLink?.href || '';
                
                return data;
            }
        """)
        
        title = data.get('judul', 'Dokumen JDIH')
        
        return ExtractedContent(
            url=url,
            title=title,
            content=data.get('full_text', '')[:5000],  # Limit content
            metadata={
                "source_type": "jdih",
                "jdih_source": "generic",
                "pdf_url": data.get('pdf_url'),
            },
            extracted_at=datetime.now()
        )
    
    def _detect_jenis_peraturan(self, text: str) -> str:
        """Detect jenis peraturan dari text."""
        text_lower = text.lower()
        
        for key, value in self.JENIS_PERATURAN.items():
            if key in text_lower or value.lower() in text_lower:
                return value
        
        return "Peraturan"
    
    def _extract_nomor(self, text: str) -> str:
        """Extract nomor peraturan."""
        if not text:
            return ""
        
        # Match number patterns
        match = re.search(r'(\d+)(?:\s*Tahun|\s*\/|\s*Tahun\s*\d{4})?', text)
        if match:
            return match.group(1)
        
        return text.strip()
    
    def _extract_tahun(self, text: str) -> str:
        """Extract tahun peraturan."""
        if not text:
            return ""
        
        # Match 4-digit year
        match = re.search(r'(\d{4})', text)
        if match:
            year = int(match.group(1))
            if 1945 <= year <= datetime.now().year + 1:
                return str(year)
        
        return text.strip()
    
    def validate(self, content: ExtractedContent) -> bool:
        """Validate JDIH content."""
        if not super().validate(content):
            return False
        
        # Check untuk metadata peraturan
        metadata = content.metadata
        if not metadata.get('jenis_peraturan') and not metadata.get('nomor'):
            # Allow generic extraction
            return True
        
        return True