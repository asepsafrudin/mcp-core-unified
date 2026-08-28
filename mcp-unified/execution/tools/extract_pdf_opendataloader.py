import os
import tempfile
from execution.registry import registry

try:
    import opendataloader_pdf
except ImportError:
    opendataloader_pdf = None

@registry.register
def extract_pdf_opendataloader(file_path: str) -> str:
    """
    Ekstrak struktur dokumen (Teks, Heading, Tabel) dari PDF menggunakan OpenDataLoader.
    Membutuhkan Java 11+ terinstal di sistem. Berjalan 100% lokal.
    """
    if opendataloader_pdf is None:
        return "Error: Pustaka 'opendataloader-pdf' belum terinstal. Silakan jalankan 'pip install opendataloader-pdf'."
    
    if not os.path.exists(file_path):
        return f"Error: File tidak ditemukan pada path {file_path}"
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Panggil engine opendataloader
            opendataloader_pdf.convert(
                input_path=[file_path],
                output_dir=temp_dir,
                format="markdown"
            )
            
            # Cari file markdown hasil konversi
            md_files = [f for f in os.listdir(temp_dir) if f.endswith('.md')]
            if not md_files:
                return "Error: Konversi selesai tetapi tidak ada file Markdown yang dihasilkan."
            
            # Ambil konten file pertama
            md_path = os.path.join(temp_dir, md_files[0])
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
            
    except Exception as e:
        return f"Error saat mengekstrak PDF dengan OpenDataLoader: {str(e)}"
