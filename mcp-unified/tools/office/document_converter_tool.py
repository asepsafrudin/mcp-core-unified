"""
Document Converter Tool — Fase 1: Pengonversi Semantik Dokumen

Tool ini mengonversi dokumen Office mentah (.docx, .xlsx) menjadi
Clean Markdown yang terstruktur dan ramah LLM.

╔══════════════════════════════════════════════════════════════════════╗
║  PENTING — PERBEDAAN DENGAN extract_text_docx():                   ║
║                                                                     ║
║  • extract_text_docx() → Mengembalikan teks mentah (plain text)    ║
║    tanpa format apapun. Cocok untuk pencarian kata atau indexing.   ║
║                                                                     ║
║  • convert_docx_to_markdown() → Menghasilkan Markdown terstruktur  ║
║    dengan heading hierarchy, tabel, list, bold/italic. Cocok       ║
║    untuk dikonsumsi oleh LLM sebagai konteks dokumen yang utuh.    ║
║                                                                     ║
║  Gunakan tool INI jika tujuan Anda adalah memberikan dokumen       ║
║  sebagai konteks ke AI/LLM. Gunakan extract_text_docx() jika      ║
║  Anda hanya membutuhkan teks datar untuk search/grep/indexing.     ║
╚══════════════════════════════════════════════════════════════════════╝

Skema Input:  Dokumen .docx / .xlsx mentah (path ke file).
Skema Output: Clean Markdown dengan XML tag yang sudah dide-fragmentasi.

Dependensi:
    - mammoth>=1.8.0  (konversi DOCX → HTML sederhana)
    - lxml>=5.0.0     (parser/defragmenter XML OOXML)
    - openpyxl>=3.1.0 (sudah ada, pembaca XLSX)
"""
import re
import html
from pathlib import Path
from typing import Dict, List, Optional, Any
from zipfile import ZipFile

from tools.base import register_tool


# ---------------------------------------------------------------------------
# Internal: HTML → Markdown converter (ringan, tanpa dependensi eksternal)
# ---------------------------------------------------------------------------

def _html_to_markdown(html_content: str) -> str:
    """
    Konversi HTML sederhana hasil mammoth ke Markdown.

    Mammoth menghasilkan HTML yang sangat bersih (hanya tag semantik),
    sehingga konversi ini cukup ringan tanpa memerlukan full HTML parser.
    """
    md = html_content

    # Heading: <h1>…</h1> → # …
    for level in range(1, 7):
        prefix = "#" * level
        md = re.sub(
            rf'<h{level}[^>]*>(.*?)</h{level}>',
            rf'\n{prefix} \1\n',
            md,
            flags=re.DOTALL
        )

    # Bold: <strong>…</strong> → **…**
    md = re.sub(r'<strong>(.*?)</strong>', r'**\1**', md, flags=re.DOTALL)

    # Italic: <em>…</em> → *…*
    md = re.sub(r'<em>(.*?)</em>', r'*\1*', md, flags=re.DOTALL)

    # Unordered list items: <li>…</li> dalam <ul> → - …
    md = re.sub(r'<ul[^>]*>', '', md)
    md = re.sub(r'</ul>', '\n', md)

    # Ordered list items: <li>…</li> dalam <ol> → numbered
    # Perlu penanganan khusus untuk penomoran
    def _replace_ol(match: re.Match) -> str:
        items = re.findall(r'<li[^>]*>(.*?)</li>', match.group(0), re.DOTALL)
        lines = []
        for i, item in enumerate(items, 1):
            clean = re.sub(r'<[^>]+>', '', item).strip()
            lines.append(f"{i}. {clean}")
        return '\n'.join(lines) + '\n'

    md = re.sub(r'<ol[^>]*>.*?</ol>', _replace_ol, md, flags=re.DOTALL)

    # List items yang tersisa (dari <ul>)
    md = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', md, flags=re.DOTALL)

    # Table: konversi <table> ke Markdown table
    def _table_to_md(match: re.Match) -> str:
        table_html = match.group(0)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        if not rows:
            return ''

        md_rows = []
        for i, row in enumerate(rows):
            cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
            clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            md_rows.append('| ' + ' | '.join(clean_cells) + ' |')

            # Separator setelah header (baris pertama)
            if i == 0:
                md_rows.append('| ' + ' | '.join(['---'] * len(clean_cells)) + ' |')

        return '\n' + '\n'.join(md_rows) + '\n'

    md = re.sub(r'<table[^>]*>.*?</table>', _table_to_md, md, flags=re.DOTALL)

    # Paragraph: <p>…</p> → teks dengan newline
    md = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', md, flags=re.DOTALL)

    # Line break
    md = re.sub(r'<br\s*/?>', '\n', md)

    # Hapus sisa tag HTML
    md = re.sub(r'<[^>]+>', '', md)

    # Decode HTML entities
    md = html.unescape(md)

    # Bersihkan whitespace berlebih
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = md.strip()

    return md


# ---------------------------------------------------------------------------
# Tool 1: Defragmentasi XML OOXML
# ---------------------------------------------------------------------------

@register_tool
def defragment_docx_xml(file_path: str) -> Dict:
    """
    Membersihkan XML internal dokumen .docx dari split runs yang terfragmentasi.

    Microsoft Word sering memecah satu kata ke dalam beberapa tag <w:r><w:t>
    (disebut "split runs"). Ini menyebabkan LLM membaca teks secara terfragmentasi.
    Tool ini menggabungkan kembali tag-tag tersebut menjadi teks kohesif.

    CATATAN: Tool ini MEMODIFIKASI file .docx asli. Buat backup sebelum
    menjalankan jika diperlukan.

    Args:
        file_path: Path absolut ke file .docx

    Returns:
        Dict berisi:
            - success (bool)
            - fragments_merged (int): jumlah fragmen yang digabung
            - paragraphs_cleaned (int): jumlah paragraf yang dibersihkan
            - file_path (str)
    """
    try:
        from lxml import etree

        input_path = Path(file_path)
        if not input_path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if input_path.suffix.lower() != '.docx':
            return {'success': False, 'error': 'Only .docx files are supported'}

        # TODO(security): Validasi bahwa file_path berada dalam direktori yang diizinkan.
        # Saat ini tool ini menerima path absolut apapun.

        # Namespace OOXML
        W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        nsmap = {'w': W_NS}

        fragments_merged = 0
        paragraphs_cleaned = 0

        # Baca dan proses document.xml di dalam .docx (ZIP)
        import zipfile
        import shutil
        import tempfile
        import os

        # Buat temporary copy untuk safety
        temp_dir = tempfile.mkdtemp()
        temp_docx = os.path.join(temp_dir, 'temp.docx')
        shutil.copy2(file_path, temp_docx)

        try:
            with zipfile.ZipFile(temp_docx, 'r') as zin:
                doc_xml = zin.read('word/document.xml')
                other_files = {}
                for item in zin.namelist():
                    if item != 'word/document.xml':
                        other_files[item] = zin.read(item)

            # Parse XML
            # TODO(security): Menggunakan lxml dengan hardened parser settings
            # untuk mencegah XXE (XML External Entity) attacks.
            parser = etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                dtd_validation=False,
                load_dtd=False
            )
            root = etree.fromstring(doc_xml, parser=parser)

            # Cari semua paragraf
            for para in root.iter(f'{{{W_NS}}}p'):
                runs = para.findall(f'{{{W_NS}}}r', nsmap)
                if len(runs) < 2:
                    continue

                # Identifikasi run berturut-turut yang bisa digabung
                # (sama formatting properties-nya)
                i = 0
                merged_in_para = False
                while i < len(runs) - 1:
                    current_run = runs[i]
                    next_run = runs[i + 1]

                    # Ambil run properties (rPr)
                    current_rpr = current_run.find(f'{{{W_NS}}}rPr', nsmap)
                    next_rpr = next_run.find(f'{{{W_NS}}}rPr', nsmap)

                    # Bandingkan formatting
                    current_rpr_str = etree.tostring(current_rpr) if current_rpr is not None else b''
                    next_rpr_str = etree.tostring(next_rpr) if next_rpr is not None else b''

                    if current_rpr_str == next_rpr_str:
                        # Gabungkan teks
                        current_t = current_run.find(f'{{{W_NS}}}t', nsmap)
                        next_t = next_run.find(f'{{{W_NS}}}t', nsmap)

                        if current_t is not None and next_t is not None:
                            current_text = current_t.text or ''
                            next_text = next_t.text or ''
                            current_t.text = current_text + next_text

                            # Preserve space
                            current_t.set(
                                '{http://www.w3.org/XML/1998/namespace}space',
                                'preserve'
                            )

                            # Hapus run yang sudah digabung
                            para.remove(next_run)
                            fragments_merged += 1
                            merged_in_para = True

                            # Refresh runs list
                            runs = para.findall(f'{{{W_NS}}}r', nsmap)
                            continue  # jangan increment i

                    i += 1

                if merged_in_para:
                    paragraphs_cleaned += 1

            # Tulis kembali ke docx
            modified_xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                zout.writestr('word/document.xml', modified_xml)
                for name, data in other_files.items():
                    zout.writestr(name, data)

        finally:
            # Cleanup temp
            shutil.rmtree(temp_dir, ignore_errors=True)

        return {
            'success': True,
            'file_path': file_path,
            'fragments_merged': fragments_merged,
            'paragraphs_cleaned': paragraphs_cleaned,
            'message': f'Defragmented {fragments_merged} split runs across {paragraphs_cleaned} paragraphs'
        }

    except ImportError:
        return {
            'success': False,
            'error': 'lxml not installed. Install with: pip install lxml>=5.0.0'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'file_path': file_path
        }


# ---------------------------------------------------------------------------
# Tool 2: Konversi DOCX → Clean Markdown
# ---------------------------------------------------------------------------

@register_tool
def convert_docx_to_markdown(file_path: str) -> Dict:
    """
    Konversi dokumen .docx menjadi Clean Markdown yang ramah LLM.

    Tool ini menggunakan pustaka `mammoth` untuk mengekstrak konten semantik
    dari file DOCX, lalu mengonversinya ke format Markdown terstruktur yang
    mempertahankan heading hierarchy, tabel, list, bold, dan italic.

    ╔═══════════════════════════════════════════════════════════════════╗
    ║  BERBEDA dengan extract_text_docx() yang mengembalikan teks     ║
    ║  mentah tanpa format. Tool ini menghasilkan MARKDOWN TERSTRUKTUR║
    ║  yang mempertahankan hierarki semantik dokumen.                 ║
    ║                                                                  ║
    ║  Gunakan tool ini untuk: konteks LLM, analisis dokumen, RAG.   ║
    ║  Gunakan extract_text_docx() untuk: search, grep, indexing.    ║
    ╚═══════════════════════════════════════════════════════════════════╝

    Args:
        file_path: Path absolut ke file .docx

    Returns:
        Dict berisi:
            - success (bool)
            - markdown (str): konten dokumen dalam format Markdown
            - metadata (dict): judul, penulis, tanggal, dsb.
            - statistics (dict): jumlah paragraf, tabel, kata, karakter
            - file_path (str)
    """
    try:
        import mammoth

        input_path = Path(file_path)
        if not input_path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if input_path.suffix.lower() != '.docx':
            return {'success': False, 'error': 'Only .docx files are supported'}

        # TODO(security): Validasi bahwa file_path berada dalam direktori yang diizinkan.

        # Konversi DOCX → HTML menggunakan mammoth
        with open(file_path, 'rb') as f:
            result = mammoth.convert_to_html(f)

        html_content = result.value
        warnings = [str(w) for w in result.messages]

        # Konversi HTML → Markdown
        markdown_content = _html_to_markdown(html_content)

        # Ekstrak metadata menggunakan python-docx (sudah ada sebagai dep)
        metadata = {}
        try:
            from docx import Document
            doc = Document(file_path)
            cp = doc.core_properties
            metadata = {
                'title': cp.title or '',
                'author': cp.author or '',
                'created': str(cp.created) if cp.created else None,
                'modified': str(cp.modified) if cp.modified else None,
                'subject': cp.subject or '',
                'keywords': cp.keywords or '',
            }
        except Exception:
            metadata = {'note': 'Metadata extraction failed, content is still available'}

        # Hitung statistik
        word_count = len(markdown_content.split())
        char_count = len(markdown_content)
        heading_count = len(re.findall(r'^#{1,6}\s', markdown_content, re.MULTILINE))
        table_count = len(re.findall(r'^\|.*\|$', markdown_content, re.MULTILINE)) // 3  # approx
        list_count = len(re.findall(r'^[-\d]+[.)]\s', markdown_content, re.MULTILINE))

        return {
            'success': True,
            'file_path': file_path,
            'markdown': markdown_content,
            'metadata': metadata,
            'statistics': {
                'word_count': word_count,
                'character_count': char_count,
                'heading_count': heading_count,
                'table_count': max(table_count, 0),
                'list_item_count': list_count,
            },
            'warnings': warnings,
            'conversion_method': 'mammoth + html_to_markdown'
        }

    except ImportError:
        return {
            'success': False,
            'error': 'mammoth not installed. Install with: pip install mammoth>=1.8.0'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'file_path': file_path
        }


# ---------------------------------------------------------------------------
# Tool 3: Konversi XLSX → Clean Markdown (dengan mode sampling)
# ---------------------------------------------------------------------------

@register_tool
def convert_xlsx_to_markdown(
    file_path: str,
    sheet_name: Optional[str] = None,
    max_rows: int = 100,
    sampling_mode: str = 'head',
    chunk_index: int = 0,
    chunk_size: int = 100
) -> Dict:
    """
    Konversi spreadsheet .xlsx menjadi tabel Markdown yang ramah LLM.

    Untuk data besar (> max_rows), tool ini menggunakan MODE SAMPLING
    untuk mencegah membanjiri konteks LLM. Mode yang tersedia:

        - 'head'   : Tampilkan max_rows baris pertama (default).
        - 'tail'   : Tampilkan max_rows baris terakhir.
        - 'sample' : Tampilkan sampel acak sebanyak max_rows baris.
        - 'chunk'  : Tampilkan satu chunk (halaman) data. Gunakan parameter
                     chunk_index dan chunk_size untuk navigasi.
        - 'full'   : Tampilkan SELURUH data tanpa batasan. ⚠️ Hati-hati
                     untuk file besar, ini bisa membebani konteks LLM.

    ╔═══════════════════════════════════════════════════════════════════╗
    ║  STRATEGI CHUNKING:                                              ║
    ║  1. Panggil pertama dengan mode='head' untuk melihat preview.   ║
    ║  2. Jika data besar, periksa 'total_rows' di response.         ║
    ║  3. Minta konfirmasi user sebelum memproses seluruhnya.         ║
    ║  4. Gunakan mode='chunk' dengan chunk_index berurutan untuk     ║
    ║     mengiterasi seluruh data secara bertahap.                   ║
    ╚═══════════════════════════════════════════════════════════════════╝

    Args:
        file_path: Path absolut ke file .xlsx
        sheet_name: Nama sheet yang ingin dikonversi (None = sheet pertama)
        max_rows: Jumlah baris maksimum untuk mode head/tail/sample (default: 100)
        sampling_mode: Mode sampling: 'head', 'tail', 'sample', 'chunk', 'full'
        chunk_index: Index chunk saat mode='chunk' (0-based, default: 0)
        chunk_size: Ukuran chunk saat mode='chunk' (default: 100)

    Returns:
        Dict berisi:
            - success (bool)
            - markdown (str): tabel dalam format Markdown
            - statistics (dict): total_rows, total_columns, sheets, dll.
            - sampling_info (dict): mode yang digunakan, baris ditampilkan, dll.
            - chunking_info (dict): info navigasi chunk (jika mode='chunk')
            - requires_confirmation (bool): True jika data besar dan mode!='full'
            - file_path (str)
    """
    try:
        from openpyxl import load_workbook

        input_path = Path(file_path)
        if not input_path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if input_path.suffix.lower() not in ('.xlsx', '.xls'):
            return {'success': False, 'error': 'Only .xlsx/.xls files are supported'}

        # TODO(security): Validasi bahwa file_path berada dalam direktori yang diizinkan.

        wb = load_workbook(file_path, data_only=True, read_only=True)

        # Pilih sheet
        if sheet_name and sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            target_sheet = sheet_name
        else:
            ws = wb.active
            target_sheet = ws.title

        # Baca semua baris (openpyxl read_only mode efisien untuk file besar)
        all_rows: List[List[str]] = []
        for row in ws.iter_rows(values_only=True):
            all_rows.append([str(cell) if cell is not None else '' for cell in row])

        wb.close()

        total_rows = len(all_rows)
        total_columns = len(all_rows[0]) if all_rows else 0

        # Pisahkan header (baris pertama) dari data
        headers = all_rows[0] if all_rows else []
        data_rows = all_rows[1:] if all_rows else []
        data_count = len(data_rows)

        # Terapkan mode sampling
        is_truncated = False
        requires_confirmation = False
        displayed_rows: List[List[str]] = []
        sampling_detail = ''

        if sampling_mode == 'full':
            displayed_rows = data_rows
            sampling_detail = f'Menampilkan seluruh {data_count} baris data'

        elif sampling_mode == 'chunk':
            start_idx = chunk_index * chunk_size
            end_idx = min(start_idx + chunk_size, data_count)
            displayed_rows = data_rows[start_idx:end_idx]
            total_chunks = (data_count + chunk_size - 1) // chunk_size
            sampling_detail = (
                f'Chunk {chunk_index + 1}/{total_chunks} '
                f'(baris {start_idx + 1}–{end_idx} dari {data_count})'
            )
            is_truncated = end_idx < data_count

        elif sampling_mode == 'tail':
            if data_count > max_rows:
                displayed_rows = data_rows[-max_rows:]
                is_truncated = True
                requires_confirmation = True
                sampling_detail = f'Menampilkan {max_rows} baris terakhir dari {data_count}'
            else:
                displayed_rows = data_rows
                sampling_detail = f'Menampilkan seluruh {data_count} baris (< batas {max_rows})'

        elif sampling_mode == 'sample':
            import random
            if data_count > max_rows:
                indices = sorted(random.sample(range(data_count), max_rows))
                displayed_rows = [data_rows[i] for i in indices]
                is_truncated = True
                requires_confirmation = True
                sampling_detail = f'Menampilkan {max_rows} baris sampel acak dari {data_count}'
            else:
                displayed_rows = data_rows
                sampling_detail = f'Menampilkan seluruh {data_count} baris (< batas {max_rows})'

        else:  # 'head' (default)
            if data_count > max_rows:
                displayed_rows = data_rows[:max_rows]
                is_truncated = True
                requires_confirmation = True
                sampling_detail = f'Menampilkan {max_rows} baris pertama dari {data_count}'
            else:
                displayed_rows = data_rows
                sampling_detail = f'Menampilkan seluruh {data_count} baris (< batas {max_rows})'

        # Bangun Markdown tabel
        md_lines = []
        md_lines.append(f'## Sheet: {target_sheet}\n')
        md_lines.append(f'> Total baris: {data_count} | Kolom: {total_columns} | '
                        f'Mode: {sampling_mode}')

        if is_truncated:
            md_lines.append(f'> ⚠️ Data terpotong. {sampling_detail}')
            if sampling_mode != 'chunk':
                md_lines.append(
                    '> Gunakan mode `chunk` dengan `chunk_index` untuk navigasi data lengkap.'
                )

        md_lines.append('')

        if headers:
            md_lines.append('| ' + ' | '.join(headers) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')

        for row in displayed_rows:
            # Pad row jika kurang kolom
            padded = row + [''] * (len(headers) - len(row)) if len(row) < len(headers) else row[:len(headers)]
            md_lines.append('| ' + ' | '.join(padded) + ' |')

        markdown_content = '\n'.join(md_lines)

        # Info chunking
        chunking_info = None
        if sampling_mode == 'chunk':
            total_chunks = (data_count + chunk_size - 1) // chunk_size
            chunking_info = {
                'current_chunk': chunk_index,
                'total_chunks': total_chunks,
                'chunk_size': chunk_size,
                'has_next': chunk_index + 1 < total_chunks,
                'has_prev': chunk_index > 0,
                'next_chunk_index': chunk_index + 1 if chunk_index + 1 < total_chunks else None,
                'prev_chunk_index': chunk_index - 1 if chunk_index > 0 else None,
            }

        return {
            'success': True,
            'file_path': file_path,
            'markdown': markdown_content,
            'statistics': {
                'total_rows': data_count,
                'total_columns': total_columns,
                'displayed_rows': len(displayed_rows),
                'sheet_name': target_sheet,
                'all_sheets': list(load_workbook(file_path, read_only=True).sheetnames),
            },
            'sampling_info': {
                'mode': sampling_mode,
                'max_rows': max_rows,
                'is_truncated': is_truncated,
                'detail': sampling_detail,
            },
            'chunking_info': chunking_info,
            'requires_confirmation': requires_confirmation,
            'conversion_method': 'openpyxl + markdown_table_builder'
        }

    except ImportError:
        return {
            'success': False,
            'error': 'openpyxl not installed. Install with: pip install openpyxl>=3.1.0'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'file_path': file_path
        }


__all__ = [
    'convert_docx_to_markdown',
    'convert_xlsx_to_markdown',
    'defragment_docx_xml',
]
