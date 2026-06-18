import re
import os
import aiohttp
import tempfile
import mimetypes
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Tuple

class GDriveFetcher:
    """
    Utility class untuk mengunduh dokumen dari tautan Google Drive / Google Docs.
    Mendukung deteksi MIME type untuk routing ke pipeline yang tepat (Mammoth vs docTR).
    """
    
    def __init__(self, service_account_json: Optional[str] = None):
        """
        Inisialisasi fetcher.
        :param service_account_json: Path ke file kredensial JSON jika diperlukan (untuk dokumen privat).
        """
        self.service_account_json = service_account_json
        # TODO: Setup Google API client if service_account_json is provided.
        # Untuk saat ini kita menggunakan ekspor tautan langsung (public/shared link).
        
    def _extract_file_id(self, url: str) -> Optional[str]:
        """Ekstrak ID file dari URL Google Drive atau Google Docs."""
        # Pola untuk docs.google.com/document/d/ID/...
        match_docs = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match_docs:
            return match_docs.group(1)
            
        # Pola untuk drive.google.com/file/d/ID/... atau drive.google.com/open?id=ID
        match_drive = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if match_drive:
            return match_drive.group(1)
            
        return None

    def _get_export_url(self, file_id: str, is_docs: bool) -> str:
        """Dapatkan URL ekspor langsung berdasarkan tipe (Docs vs Drive PDF)."""
        if is_docs:
            # Unduh Google Docs sebagai docx untuk dikirim ke Mammoth
            return f"https://docs.google.com/document/d/{file_id}/export?format=docx"
        else:
            # Unduh file Drive (biasanya PDF/Image) langsung
            return f"https://drive.google.com/uc?export=download&id={file_id}"

    async def fetch_and_detect_mime(self, url: str, dest_dir: str = "/tmp") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Mengunduh file dari URL GDrive dan mendeteksi tipe MIME-nya.
        
        :return: (success, filepath, mime_type)
        """
        file_id = self._extract_file_id(url)
        if not file_id:
            return False, None, None
            
        is_docs = "docs.google.com/document" in url
        export_url = self._get_export_url(file_id, is_docs)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(export_url) as response:
                    if response.status != 200:
                        # Gagal akses (mungkin privat)
                        return False, None, None
                        
                    content_type = response.headers.get("Content-Type", "")
                    content_disposition = response.headers.get("Content-Disposition", "")
                    
                    # Deteksi ekstensi file dari Content-Disposition jika ada
                    filename = f"gdrive_{file_id}"
                    ext = ".bin"
                    
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^"]+)"?', content_disposition)
                        if fn_match:
                            filename = fn_match.group(1)
                            ext = os.path.splitext(filename)[1]
                    else:
                        if "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type or is_docs:
                            ext = ".docx"
                            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        elif "application/pdf" in content_type:
                            ext = ".pdf"
                        elif "image/" in content_type:
                            ext = mimetypes.guess_extension(content_type) or ".jpg"
                            
                    filepath = os.path.join(dest_dir, f"{file_id}{ext}")
                    
                    with open(filepath, 'wb') as f:
                        f.write(await response.read())
                        
                    return True, filepath, content_type
                    
        except Exception as e:
            print(f"[GDriveFetcher] Error fetching {url}: {e}")
            return False, None, None
